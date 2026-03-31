"""Gestor async de conexiones y ejecucion de consultas."""

from __future__ import annotations

import logging
import re

from collections.abc import Awaitable, Callable
from typing import Any, cast

from ..async_utils import maybe_await
from ..connection.close import AsyncCloseMode, normalize_close_mode
from ..connection.factory import ConnectionFactory
from ..database_exceptions import DatabaseOperationError, QueryError
from ..database_type_validator import get_database_validator, get_db_type_info, get_supported_db_types
from ..executors.async_query_executor import AsyncQueryExecutor
from ..factory.async_sqlalchemy_engine_factory import AsyncSQLAlchemyEngineFactory
from ..factory.pool_factory import PoolFactory
from ..metadata import (
    DatabaseMetadataCache,
    NormalizedColumnRow,
    NormalizedTableRow,
    RelationshipMetadataCache,
    Rows,
    normalize_column_rows,
    normalize_table_rows,
)
from ..metadata.mariadb import (
    MariaDBAsyncAdapter,
    build_public_mariadb_routine_parameter_rows,
    escape_mariadb_sql_literal,
    parse_mariadb_column_charset_collation_row,
    parse_mariadb_db_charset,
)
from ..results import ResultNormalizer, RowOrNone


class AsyncDatabaseManager:
    """Manager async-first para conexiones directas o con pool."""

    _PARAMETER_PATTERN = r"\{(\w+)\}"
    _ERROR_EXECUTOR_NOT_INITIALIZED = "AsyncQueryExecutor no inicializado"

    @staticmethod
    def _escape_sql_literal(value: str) -> str:
        return escape_mariadb_sql_literal(value)

    def _get_mariadb_adapter(self) -> MariaDBAsyncAdapter:
        adapter = getattr(self, "_mariadb_adapter", None)
        if adapter is None:
            adapter = MariaDBAsyncAdapter(self)
            self._mariadb_adapter = adapter
        return cast(MariaDBAsyncAdapter, adapter)

    async def _fetch_mariadb_routines_from_show_status(self, database: str) -> Rows:
        return await self._get_mariadb_adapter().fetch_routines_from_show_status(database)

    async def _get_mariadb_routines_detail_rows(self, context_database: str) -> list[dict[str, Any]]:
        return await self._get_mariadb_adapter().get_routines_detail_rows(context_database)

    async def _get_mariadb_routine_parameters_detail_rows(self, context_database: str) -> list[dict[str, Any]]:
        return await self._get_mariadb_adapter().get_routine_parameters_detail_rows(context_database)

    async def _fetch_mariadb_columns_safe(self, context_database: str, tabla: str) -> Rows:
        return await self._get_mariadb_adapter().fetch_columns_safe(context_database, tabla)

    async def _fetch_mariadb_view_from_information_schema(self, database: str, view_name: str) -> str:
        return await self._get_mariadb_adapter().fetch_view_from_information_schema(database, view_name)

    async def _fetch_mariadb_routine_from_information_schema(
        self, database: str, routine_name: str, routine_type: str
    ) -> str:
        return await self._get_mariadb_adapter().fetch_routine_from_information_schema(
            database, routine_name, routine_type
        )

    async def _fetch_mariadb_routine_parameters_detailed(
        self,
        *,
        database: str,
        routine_name: str,
        routine_type: str,
    ) -> list[dict[str, Any]]:
        return await self._get_mariadb_adapter().fetch_routine_parameters_detailed(
            database=database,
            routine_name=routine_name,
            routine_type=routine_type,
        )

    async def _fetch_mariadb_routine_parameters_public_rows(
        self, *, context_database: str, rutina: str, routine_type: str
    ) -> Rows:
        return build_public_mariadb_routine_parameter_rows(
            await self._fetch_mariadb_routine_parameters_detailed(
                database=context_database,
                routine_name=rutina,
                routine_type=routine_type,
            )
        )

    async def _build_mariadb_ddl_from_metadata(self, tabla: str) -> str:
        return await self._get_mariadb_adapter().build_table_ddl_from_metadata(tabla)

    async def _fetch_mariadb_routines(self, context_database: str) -> Rows:
        try:
            routine_rows = await self._get_mariadb_routines_detail_rows(context_database)
            if routine_rows:
                return cast(
                    Rows,
                    sorted(
                        [
                            (
                                str(row.get("routine_name") or ""),
                                str(row.get("routine_type") or ""),
                                str(row.get("routine_comment") or ""),
                            )
                            for row in routine_rows
                            if str(row.get("routine_name") or "").strip()
                        ],
                        key=lambda row: (str(row[1]), str(row[0])),
                    ),
                )
            self.logger.warning(
                "Fallback listado rutinas MariaDB vacío para %s. Reintentando con SHOW ... STATUS",
                context_database,
            )
        except DatabaseOperationError:
            self.logger.warning(
                "Fallback listado rutinas MariaDB por error para %s. Reintentando con SHOW ... STATUS",
                context_database,
            )
        return await self._fetch_mariadb_routines_from_show_status(context_database)

    def _get_routines_fetcher(self, context_database: str) -> Callable[[], Awaitable[Rows]]:
        if self.db_type == "mariadb":
            return lambda: self._fetch_mariadb_routines(context_database)
        return lambda: self._execute_metadata_many(
            "obtener_rutinas",
            params={"database": context_database},
            error_message="Error obteniendo rutinas",
        )

    def _get_table_ddl_fetcher(self, context_database: str, tabla: str) -> Callable[[], Awaitable[str]]:
        if self.db_type == "mariadb":
            return lambda: self._build_mariadb_ddl_from_metadata(tabla)

        async def _fetch() -> str:
            ddl_raw = await self._execute_metadata_one(
                "create_table",
                params=self._add_metadata_context_params({"tabla": tabla}, context_database),
                error_message="Error obteniendo DDL",
                table_name=tabla,
            )
            return self._normalize_ddl_result(ddl_raw)

        return _fetch

    def _get_view_ddl_fetcher(self, context_database: str, vista: str) -> Callable[[], Awaitable[str]]:
        if self.db_type == "mariadb":
            return lambda: self._fetch_mariadb_view_from_information_schema(context_database, vista)

        async def _fetch() -> str:
            ddl_raw = await self._execute_metadata_one(
                "create_view",
                params=self._add_metadata_context_params({"tabla": vista}, context_database),
                error_message="Error obteniendo DDL de vista",
                table_name=vista,
            )
            return self._normalize_ddl_result(ddl_raw)

        return _fetch

    def _get_columns_fetcher(self, context_database: str, tabla: str) -> Callable[[], Awaitable[Rows]]:
        if self.db_type == "mariadb":
            return lambda: self._fetch_mariadb_columns_safe(context_database, tabla)
        return lambda: self._execute_metadata_many(
            "columnas_tabla",
            params={"database": context_database, "tabla": tabla},
            error_message="Error obteniendo columnas",
            table_name=tabla,
        )

    def _get_routine_parameters_fetcher(
        self,
        context_database: str,
        rutina: str,
        routine_type: str,
    ) -> Callable[[], Awaitable[Rows]]:
        if self.db_type == "mariadb":
            return lambda: self._fetch_mariadb_routine_parameters_public_rows(
                context_database=context_database,
                rutina=rutina,
                routine_type=routine_type,
            )
        return lambda: self._execute_metadata_many(
            "parametros_rutina",
            params={
                "database": context_database,
                "rutina": rutina,
                "tipo_rutina": routine_type,
            },
            error_message="Error obteniendo parámetros de rutina",
            table_name=rutina,
        )

    def _get_routine_ddl_fetcher(
        self,
        context_database: str,
        rutina: str,
        routine_type: str,
    ) -> Callable[[], Awaitable[str]]:
        if self.db_type == "mariadb":
            return lambda: self._fetch_mariadb_routine_from_information_schema(context_database, rutina, routine_type)

        async def _fetch() -> str:
            params: dict[str, Any] = {
                "rutina": rutina,
                "tipo_rutina": routine_type,
            }
            params = self._add_metadata_context_params(params, context_database)
            ddl_raw = await self._execute_metadata_one(
                "create_rutina",
                params=params,
                error_message="Error obteniendo DDL de rutina",
                table_name=rutina,
            )
            return self._normalize_ddl_result(ddl_raw)

        return _fetch

    def _get_storage_inventory_handler(
        self,
    ) -> Callable[[str, str | None], Awaitable[dict[str, Any]]] | None:
        handlers: dict[str, Callable[[str, str | None], Awaitable[dict[str, Any]]]] = {
            "sqlserver": self._storage_inventory_sqlserver,
            "oracle": self._storage_inventory_oracle,
            "mariadb": self._storage_inventory_mariadb,
            "postgresql": self._storage_inventory_postgresql,
            "sqlite": self._storage_inventory_sqlite,
        }
        return handlers.get(self.db_type)

    async def _log_and_call_async(self, message: str, action: Callable[[], Awaitable[Any]]) -> Any:
        self.logger.debug(message)
        return await action()

    def __init__(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        use_pool: bool = True,
        connection_factory: Callable[..., Awaitable[Any]] | None = None,
        pool_factory: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.db_type: str = db_type.lower().strip()
        self.conn_params: dict[str, Any] = conn_params
        self.database: str = str(conn_params.get("database", "") or "").strip()
        self.use_pool: bool = use_pool
        self._connection_factory: Callable[..., Awaitable[Any]] = (
            connection_factory or ConnectionFactory.create_async_connection
        )
        self._pool_factory: Callable[..., Awaitable[Any]] = pool_factory or PoolFactory.create_async_pool

        self._initialized: bool = False
        self._connection: Any = None
        self.pool_connection: Any = None
        self.query_executor: AsyncQueryExecutor | None = None
        self.db_cache: DatabaseMetadataCache = DatabaseMetadataCache()
        self.relationship_cache: RelationshipMetadataCache = RelationshipMetadataCache(db_cache=self.db_cache)
        self.result_normalizer = ResultNormalizer()

    async def init(self) -> AsyncDatabaseManager:
        """Inicializa recursos async una única vez."""
        if self._initialized:
            return self

        if self.use_pool:
            try:
                self.pool_connection = await self._pool_factory(self.db_type, self.conn_params)
            except NotImplementedError:
                self.use_pool = False

        if not self.use_pool:
            self._connection = await self._connection_factory(self.db_type, self.conn_params)

        self.query_executor = AsyncQueryExecutor(
            connection_provider=self.get_connection,
            connection_releaser=self.release_connection,
        )
        self._initialized = True
        return self

    async def __aenter__(self) -> AsyncDatabaseManager:
        return await self.init()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close(mode="immediate")

    async def get_connection(self) -> Any:
        """Obtiene conexión del pool o directa."""
        if not self._initialized:
            await self.init()

        if self.pool_connection is not None:
            return await maybe_await(self.pool_connection.acquire())

        return self._connection

    async def release_connection(self, connection: Any) -> None:
        """Libera conexión al pool o no-op en conexión directa."""
        if self.pool_connection is None:
            return
        await maybe_await(self.pool_connection.release(connection))

    async def _ensure_initialized(self) -> None:
        """Garantiza inicialización perezosa del manager."""
        if not self._initialized:
            await self.init()

    async def _get_query_executor(self) -> AsyncQueryExecutor:
        """Retorna el executor async o lanza error de dominio."""
        await self._ensure_initialized()
        executor = self.query_executor
        if executor is None:
            self.logger.error("❌ AsyncQueryExecutor no inicializado")
            raise DatabaseOperationError(
                self._ERROR_EXECUTOR_NOT_INITIALIZED,
                operation="INIT",
                db_type=self.db_type,
            )
        return executor

    async def _run_manager_operation_async(
        self,
        action: Callable[[], Any | Awaitable[Any]],
        *,
        error_message: str,
        operation: str,
        table_name: str | None = None,
    ) -> Any:
        """Ejecuta operación del manager con passthrough de errores de dominio."""
        try:
            return await maybe_await(action())
        except (DatabaseOperationError, QueryError):
            raise
        except Exception as err:
            self.logger.error(f"❌ {error_message}: {err}")
            raise DatabaseOperationError(error_message, operation, table_name, self.db_type) from err

    async def _execute_registered_query(
        self,
        *,
        query_name: str,
        params: dict[str, Any],
        expect_one: bool,
    ) -> RowOrNone | Rows:
        executor = await self._get_query_executor()
        execute = executor.execute_query_one if expect_one else executor.execute_query_many
        result = await self._run_manager_operation_async(
            action=lambda: execute(
                query_name=query_name,
                db_type=self.db_type,
                params=params,
            ),
            error_message=f"Error ejecutando consulta: {query_name}",
            operation="SELECT",
        )
        return cast(RowOrNone | Rows, result)

    async def _execute_custom_sql(
        self,
        *,
        sql: str,
        params: Any | None,
        expect_one: bool,
    ) -> RowOrNone | Rows:
        executor = await self._get_query_executor()
        execute = executor.execute_custom_one if expect_one else executor.execute_custom_many
        result = await self._run_manager_operation_async(
            action=lambda: execute(sql=sql, params=params),
            error_message="Error ejecutando consulta SQL",
            operation="CUSTOM",
        )
        return cast(RowOrNone | Rows, result)

    async def execute_custom_many(
        self,
        sql: str,
        params: Any | None = None,
    ) -> Rows:
        """Ejecuta SQL custom y retorna múltiples filas."""
        result = await self._execute_custom_sql(
            sql=sql,
            params=params,
            expect_one=False,
        )
        return cast(Rows, result)

    async def execute_custom_one(
        self,
        sql: str,
        params: Any | None = None,
    ) -> RowOrNone:
        """Ejecuta SQL custom y retorna una única fila o None."""
        result = await self._execute_custom_sql(
            sql=sql,
            params=params,
            expect_one=True,
        )
        return cast(RowOrNone, result)

    async def execute_query_many(
        self,
        query_name: str,
        **params,
    ) -> Rows:
        """Ejecuta query registrada por nombre y retorna múltiples filas.

        Args:
            query_name: Nombre de la query registrada
            **params: Parámetros para la query

        Returns:
            Lista materializada de filas.

        Raises:
            QueryNotFoundError: Si la query no existe
            QueryValidationError: Si validación de parámetros falla
            DatabaseOperationError: Si falla la capa de manager/infraestructura.
        """
        result = await self._execute_registered_query(
            query_name=query_name,
            params=params,
            expect_one=False,
        )
        return cast(Rows, result)

    async def execute_query_one(
        self,
        query_name: str,
        **params,
    ) -> RowOrNone:
        """Ejecuta query registrada por nombre y retorna una única fila o None."""
        result = await self._execute_registered_query(
            query_name=query_name,
            params=params,
            expect_one=True,
        )
        return cast(RowOrNone, result)

    async def resolve_query(self, query_name: str, **params) -> Any:
        """Resuelve una query registrada y devuelve su SQL final y metadatos."""
        executor = await self._get_query_executor()
        return await self._run_manager_operation_async(
            action=lambda: executor.resolver.resolve(query_name, self.db_type, params),
            error_message=f"Error resolviendo consulta: {query_name}",
            operation="SELECT",
        )

    async def close(self, mode: AsyncCloseMode | str = "immediate") -> None:
        """Cierra pool o conexión directa con política explícita."""
        close_mode: AsyncCloseMode = normalize_close_mode(mode)
        pool_connection = self.pool_connection
        connection = self._connection
        try:
            if pool_connection is not None:
                await maybe_await(pool_connection.close(mode=close_mode))
            if connection is not None and hasattr(connection, "close"):
                await maybe_await(connection.close())
        finally:
            self.pool_connection = None
            self._connection = None
            self._initialized = False

    def _get_query_context_database(self) -> str:
        """Obtiene contexto schema/database para consultas de metadatos."""
        context_database: str = self.database
        if self.db_type == "oracle":
            oracle_user: str = str(self.conn_params.get("user", "")).strip()
            context_database = oracle_user or context_database
        elif self.db_type == "postgresql":
            explicit_schema: str = str(self.conn_params.get("schema", "")).strip()
            context_database = explicit_schema or context_database or "public"
        elif self.db_type == "hsqldb":
            explicit_schema = str(self.conn_params.get("schema", "")).strip()
            context_database = explicit_schema or context_database or "PUBLIC"
        elif self.db_type == "sqlserver":
            explicit_schema = str(self.conn_params.get("schema", "")).strip()
            context_database = explicit_schema or context_database or "dbo"
        return context_database

    def _add_metadata_context_params(self, params: dict[str, Any], context: str | None) -> dict[str, Any]:
        """Añade parámetros de contexto metadata según motor."""
        if not context or self.db_type == "mariadb":
            return params
        if self.db_type in {"oracle", "sqlserver"}:
            params["esquema"] = context
        if self.db_type in {"postgresql", "hsqldb", "sqlserver"}:
            params["database"] = context
        return params

    def _get_query_context_label(self) -> str:
        """Obtiene etiqueta descriptiva del contexto de metadatos."""
        return "owner/schema" if self.db_type == "oracle" else "database"

    def get_query_context_database(self) -> str:
        """Devuelve contexto efectivo schema/database para metadata."""
        return self._get_query_context_database()

    def _clear_all_caches(self) -> None:
        """Limpia completamente todas las cachés de metadatos."""
        self.db_cache.clear_all()
        self.relationship_cache.clear_all()
        self.logger.info("🧹 Todas las cachés de metadatos limpiadas completamente")

    def _clear_table_cache(self, context: str, table: str) -> None:
        """Limpia caché para una tabla/vista específica."""
        self.db_cache.clear_by_table(context, table)
        self.relationship_cache.clear_by_table(table)
        self.logger.info(f"🧹 Caché invalidada para tabla/vista {table} ({context})")

    def _clear_routine_cache(self, context: str, routine: str, routine_type: str | None = None) -> None:
        """Limpia caché para una rutina específica."""
        self.db_cache._routine_metadata_context_cache.pop(context, None)
        self.db_cache._routine_parameters_context_cache.pop(context, None)
        if routine_type:
            routine_key: tuple[str, str, str] = (context, routine, routine_type.upper())
            self.db_cache._routine_parameters_cache.pop(routine_key, None)
            self.db_cache._routine_ddl_cache.pop(routine_key, None)
        else:
            param_keys: list[tuple[str, str, str]] = [
                key for key in self.db_cache._routine_parameters_cache if key[0] == context and key[1] == routine
            ]
            ddl_keys: list[tuple[str, str, str]] = [
                key for key in self.db_cache._routine_ddl_cache if key[0] == context and key[1] == routine
            ]
            for key in param_keys:
                self.db_cache._routine_parameters_cache.pop(key, None)
            for key in ddl_keys:
                self.db_cache._routine_ddl_cache.pop(key, None)
        self.logger.info(f"🧹 Caché invalidada para rutina {routine} ({context})")

    @staticmethod
    def _clear_tuple_cache_by_context(cache: dict[tuple[Any, ...], Any], context: str) -> None:
        keys_to_remove: list[tuple[Any, ...]] = [key for key in cache if key and str(key[0]) == context]
        for cache_key in keys_to_remove:
            cache.pop(cache_key, None)

    def _clear_context_cache(self, context: str) -> None:
        """Limpia caché para un contexto/schema específico."""
        context_caches: tuple[dict[str, Any], ...] = (
            self.db_cache._tables_cache,
            self.db_cache._views_cache,
            self.db_cache._routines_cache,
            self.db_cache._routine_metadata_context_cache,
            self.db_cache._routine_parameters_context_cache,
        )
        for context_cache in context_caches:
            context_cache.pop(context, None)

        tuple_caches: tuple[dict[tuple[Any, ...], Any], ...] = (
            self.db_cache._primary_keys_cache,
            self.db_cache._indices_cache,
            self.db_cache._foreign_keys_cache,
            self.db_cache._unique_constraints_cache,
            self.db_cache._columns_cache,
            self.db_cache._ddl_cache,
            self.db_cache._view_ddl_cache,
            self.db_cache._routine_parameters_cache,
            self.db_cache._routine_ddl_cache,
        )
        for tuple_cache in tuple_caches:
            self._clear_tuple_cache_by_context(tuple_cache, context)

        self.logger.info(f"🧹 Caché invalidada para contexto: {context}")

    def clear_cache(
        self,
        context_database: str | None = None,
        table: str | None = None,
        routine: str | None = None,
        routine_type: str | None = None,
    ) -> None:
        """Limpia cachés de metadatos (global o selectiva)."""
        if context_database is None and table is None and routine is None and routine_type is None:
            self._clear_all_caches()
            return

        resolved_context: str = str(
            context_database if context_database is not None else self._get_query_context_database() or ""
        )

        if table:
            self._clear_table_cache(resolved_context, str(table))

        if routine:
            self._clear_routine_cache(resolved_context, str(routine), str(routine_type) if routine_type else None)

        if not table and not routine:
            self._clear_context_cache(resolved_context)

    @staticmethod
    def _cache_context_key(context_database: str) -> str:
        return str(context_database or "")

    def _cache_table_key(self, context_database: str, table_name: str) -> tuple[str, str]:
        return (self._cache_context_key(context_database), str(table_name or ""))

    def _cache_routine_key(self, context_database: str, routine_name: str, routine_type: str) -> tuple[str, str, str]:
        return (
            self._cache_context_key(context_database),
            str(routine_name or ""),
            str(routine_type or "").upper(),
        )

    async def _execute_metadata_many(
        self,
        query_name: str,
        *,
        params: dict[str, Any],
        error_message: str,
        table_name: str | None = None,
    ) -> Rows:
        executor = await self._get_query_executor()
        result = await self._run_manager_operation_async(
            action=lambda: executor.execute_query_many(
                query_name=query_name,
                db_type=self.db_type,
                params=params,
            ),
            error_message=error_message,
            operation="SELECT",
            table_name=table_name,
        )
        return cast(Rows, result)

    async def _execute_metadata_one(
        self,
        query_name: str,
        *,
        params: dict[str, Any],
        error_message: str,
        table_name: str | None = None,
    ) -> RowOrNone:
        executor = await self._get_query_executor()
        result = await self._run_manager_operation_async(
            action=lambda: executor.execute_query_one(
                query_name=query_name,
                db_type=self.db_type,
                params=params,
            ),
            error_message=error_message,
            operation="SELECT",
            table_name=table_name,
        )
        return cast(RowOrNone, result)

    async def _get_cached_rows_async(
        self,
        *,
        cache_lookup: Callable[[], list[Any] | None],
        cache_store: Callable[[list[Any]], None],
        fetch_rows: Callable[[], Awaitable[list[Any]]],
        cache_hit_message: str | None = None,
        success_message: str | None = None,
        fetch_debug_message: str | None = None,
    ) -> list[Any]:
        cached_rows = cache_lookup()
        if cached_rows is not None:
            if cache_hit_message:
                self.logger.debug(cache_hit_message)
            return list(cached_rows)
        if fetch_debug_message:
            self.logger.debug(fetch_debug_message)
        rows = list(await fetch_rows())
        cache_store(rows)
        if success_message:
            self.logger.info(success_message.format(count=len(rows)))
        return rows

    async def _get_cached_text_async(
        self,
        *,
        cache_lookup: Callable[[], str | None],
        cache_store: Callable[[str], None],
        fetch_text: Callable[[], Awaitable[str]],
        cache_hit_message: str | None = None,
        success_message: str | None = None,
    ) -> str:
        cached_text = cache_lookup()
        if cached_text is not None:
            if cache_hit_message:
                self.logger.debug(cache_hit_message)
            return cached_text
        text = await fetch_text()
        cache_store(text)
        if success_message:
            self.logger.info(success_message)
        return text

    def __parse_collation_only_row(self, row: tuple[Any, ...], column_name: str) -> tuple[str, str | None, str | None]:
        collation: str | None = str(row[2]) if len(row) > 2 else None
        return (column_name, None, collation)

    def __parse_empty_charset_collation_row(
        self, _row: tuple[Any, ...], column_name: str
    ) -> tuple[str, str | None, str | None]:
        return (column_name, None, None)

    def __parse_db_charset_oracle(self, result: tuple[Any, ...]) -> dict[str, Any]:
        if not result:
            return {}
        charset: str = str(result[0])
        if len(result) > 1:
            nchar_charset: str | None = str(result[1])
            return {"charset": charset, "nchar_charset": nchar_charset}
        return {"charset": charset}

    def __parse_db_charset_postgresql(self, result: tuple[Any, ...]) -> dict[str, Any]:
        if len(result) > 2:
            return {"encoding": str(result[0]), "collate": str(result[1]), "ctype": str(result[2])}
        if len(result) > 0:
            return {"encoding": str(result[0])}
        return {}

    def __parse_db_charset_single_field(self, result: tuple[Any, ...], field_name: str) -> dict[str, Any]:
        if len(result) == 0:
            return {}
        return {field_name: str(result[0])}

    def _parse_charset_collation_result(self, result: tuple[Any, ...] | None) -> dict[str, Any]:
        if not result:
            return {}

        parser_map: dict[str, Callable[[tuple[Any, ...]], dict[str, Any]]] = {
            "mariadb": parse_mariadb_db_charset,
            "oracle": self.__parse_db_charset_oracle,
            "postgresql": self.__parse_db_charset_postgresql,
            "sqlserver": lambda r: self.__parse_db_charset_single_field(r, "collation"),
            "hsqldb": lambda r: self.__parse_db_charset_single_field(r, "collation"),
            "sqlite": lambda r: self.__parse_db_charset_single_field(r, "encoding"),
        }

        parser: Callable[[tuple[Any, ...]], dict[str, Any]] = parser_map.get(self.db_type, lambda _: {})
        return parser(result)

    def _is_lob(self, value: Any) -> bool:
        return hasattr(value, "read") and callable(value.read)

    def _read_lob(self, value: Any) -> str:
        try:
            return str(value.read())
        except Exception:
            return str(value)

    def _contains_create(self, text: str) -> bool:
        return "CREATE " in text.upper()

    def _extract_preferred_ddl_candidate(self, value: Any) -> str:
        if value is None:
            return ""

        if self._is_lob(value):
            value = self._read_lob(value)

        if isinstance(value, (tuple, list)):
            nested_text = self._normalize_ddl_result(value)
            if self._contains_create(nested_text):
                return nested_text
            if nested_text.strip():
                return nested_text
            return ""

        text = str(value)
        if self._contains_create(text):
            return text
        return ""

    def _extract_any_text(self, value: Any) -> str:
        if value is None:
            return ""
        if self._is_lob(value):
            return self._read_lob(value)
        if isinstance(value, (tuple, list)):
            return self._normalize_ddl_result(value)
        text = str(value)
        return text if text.strip() else ""

    def _normalize_ddl_result(self, ddl: Any) -> str:
        if ddl is None:
            return ""
        if isinstance(ddl, str):
            return ddl
        if self._is_lob(ddl):
            return self._read_lob(ddl)
        if not isinstance(ddl, (tuple, list)):
            return str(ddl)

        preferred_positions = [2, 1, 0]
        for pos in preferred_positions:
            if len(ddl) <= pos:
                continue
            candidate = self._extract_preferred_ddl_candidate(ddl[pos])
            if candidate:
                return candidate

        for value in ddl:
            text = self._extract_any_text(value)
            if text:
                return text

        return ""

    def __parse_column_charset_collation_row(self, row: tuple[Any, ...]) -> tuple[str, str | None, str | None]:
        column_name: str = str(row[0]) if len(row) > 0 else ""
        parser_map: dict[str, Callable[[tuple[Any, ...], str], tuple[str, str | None, str | None]]] = {
            "mariadb": parse_mariadb_column_charset_collation_row,
            "oracle": self.__parse_collation_only_row,
            "postgresql": self.__parse_collation_only_row,
            "sqlserver": self.__parse_collation_only_row,
            "hsqldb": self.__parse_collation_only_row,
            "sqlite": self.__parse_empty_charset_collation_row,
        }
        parser = parser_map.get(self.db_type, self.__parse_empty_charset_collation_row)
        return parser(row, column_name)

    def _supports_columns_charset_collation(self) -> bool:
        """Indica si el motor expone metadata fiable de charset/collation por columna."""
        if self.db_type == "oracle":
            cached_support = getattr(self, "_oracle_column_collation_supported", None)
            if cached_support is not None:
                return bool(cached_support)
            return False

        return self.db_type != "sqlite"

    async def get_tables(self) -> Rows:
        context_database: str = self._get_query_context_database()
        cache_key = self._cache_context_key(context_database)
        context_label = self._get_query_context_label()
        rows = await self._get_cached_rows_async(
            cache_lookup=lambda: self.db_cache._tables_cache.get(cache_key),
            cache_store=lambda items: self.db_cache._tables_cache.__setitem__(cache_key, list(items)),
            fetch_rows=lambda: self._execute_metadata_many(
                "obtener_tablas",
                params={"database": context_database},
                error_message="Error obteniendo tablas",
            ),
            cache_hit_message=f"♻️  Usando tablas en caché para contexto: {context_database}",
            success_message=f"✅ {{count}} tablas obtenidas para {context_label}: {context_database}",
            fetch_debug_message=f"🔍 Obteniendo lista de tablas para {context_label}: {context_database}",
        )
        return cast(Rows, rows)

    async def get_views(self) -> Rows:
        context_database: str = self._get_query_context_database()
        cache_key = self._cache_context_key(context_database)
        context_label = self._get_query_context_label()
        rows = await self._get_cached_rows_async(
            cache_lookup=lambda: self.db_cache._views_cache.get(cache_key),
            cache_store=lambda items: self.db_cache._views_cache.__setitem__(cache_key, list(items)),
            fetch_rows=lambda: self._execute_metadata_many(
                "obtener_vistas",
                params={"database": context_database},
                error_message="Error obteniendo vistas",
            ),
            cache_hit_message=f"♻️  Usando vistas en caché para contexto: {context_database}",
            success_message=f"✅ {{count}} vistas obtenidas para {context_label}: {context_database}",
            fetch_debug_message=f"🔍 Obteniendo lista de vistas para {context_label}: {context_database}",
        )
        return cast(Rows, rows)

    async def get_routines(self) -> Rows:
        context_database: str = self._get_query_context_database()
        cache_key: str = self._cache_context_key(context_database)
        context_label: str = self._get_query_context_label()

        rows = await self._get_cached_rows_async(
            cache_lookup=lambda: self.db_cache._routines_cache.get(cache_key),
            cache_store=lambda items: self.db_cache._routines_cache.__setitem__(cache_key, list(items)),
            fetch_rows=self._get_routines_fetcher(context_database),
            cache_hit_message=f"♻️  Usando rutinas en caché para contexto: {context_database}",
            success_message=f"✅ {{count}} rutinas obtenidas para {context_label}: {context_database}",
            fetch_debug_message=f"🔍 Obteniendo lista de rutinas para {context_label}: {context_database}",
        )
        return cast(Rows, rows)

    async def get_ddl(self, tabla: str) -> str:
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)
        fetch_ddl = self._get_table_ddl_fetcher(context_database, tabla)

        return await self._get_cached_text_async(
            cache_lookup=lambda: self.db_cache._ddl_cache.get(cache_key),
            cache_store=lambda ddl: self.db_cache._ddl_cache.__setitem__(cache_key, ddl),
            fetch_text=lambda: self._log_and_call_async(
                f"🔍 Obteniendo DDL para tabla {tabla} ({context_label}: {context_database})",
                fetch_ddl,
            ),
            cache_hit_message=f"♻️  Usando DDL en caché para tabla {tabla}",
            success_message=f"✅ DDL obtenido para tabla {tabla}",
        )

    async def get_view_ddl(self, vista: str) -> str:
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, vista)
        fetch_ddl = self._get_view_ddl_fetcher(context_database, vista)

        return await self._get_cached_text_async(
            cache_lookup=lambda: self.db_cache._view_ddl_cache.get(cache_key),
            cache_store=lambda ddl: self.db_cache._view_ddl_cache.__setitem__(cache_key, ddl),
            fetch_text=lambda: self._log_and_call_async(
                f"🔍 Obteniendo DDL para vista {vista} ({context_label}: {context_database})",
                fetch_ddl,
            ),
            cache_hit_message=f"♻️  Usando DDL de vista en caché para {vista}",
            success_message=f"✅ DDL obtenido para vista {vista}",
        )

    async def get_columns(self, tabla: str) -> Rows:
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)
        rows = await self._get_cached_rows_async(
            cache_lookup=lambda: self.db_cache.get_columns(cache_key),
            cache_store=lambda items: self.db_cache.set_columns(cache_key, items),
            fetch_rows=self._get_columns_fetcher(context_database, tabla),
            cache_hit_message=f"♻️  Usando columnas en caché para tabla {tabla}",
            success_message=f"✅ {{count}} columnas obtenidas de {tabla} ({context_label}: {context_database})",
            fetch_debug_message=f"🔍 Obteniendo columnas de {tabla} ({context_label}: {context_database})",
        )
        return cast(Rows, rows)

    async def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> Rows:
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        routine_type = str(tipo_rutina or "").upper()
        cache_key = self._cache_routine_key(context_database, rutina, routine_type)
        rows = await self._get_cached_rows_async(
            cache_lookup=lambda: self.db_cache._routine_parameters_cache.get(cache_key),
            cache_store=lambda items: self.db_cache._routine_parameters_cache.__setitem__(cache_key, list(items)),
            fetch_rows=self._get_routine_parameters_fetcher(context_database, rutina, routine_type),
            cache_hit_message=f"♻️  Usando parámetros de rutina en caché para {routine_type} {rutina}",
            success_message=f"✅ {{count}} parámetros obtenidos de rutina {rutina} ({context_label}: {context_database})",
            fetch_debug_message=(
                f"🔍 Obteniendo parámetros de rutina {routine_type} {rutina} ({context_label}: {context_database})"
            ),
        )
        return cast(Rows, rows)

    async def get_routine_ddl(self, rutina: str, tipo_rutina: str) -> str:
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        routine_type = str(tipo_rutina or "").upper()
        cache_key = self._cache_routine_key(context_database, rutina, routine_type)
        fetch_ddl = self._get_routine_ddl_fetcher(context_database, rutina, routine_type)

        return await self._get_cached_text_async(
            cache_lookup=lambda: self.db_cache._routine_ddl_cache.get(cache_key),
            cache_store=lambda ddl: self.db_cache._routine_ddl_cache.__setitem__(cache_key, ddl),
            fetch_text=lambda: self._log_and_call_async(
                f"🔍 Obteniendo DDL para rutina {routine_type} {rutina} ({context_label}: {context_database})",
                fetch_ddl,
            ),
            cache_hit_message=f"♻️  Usando DDL de rutina en caché para {routine_type} {rutina}",
            success_message=f"✅ DDL obtenido para rutina {rutina}",
        )

    async def get_indices(self, tabla: str) -> Rows:
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)
        rows = await self._get_cached_rows_async(
            cache_lookup=lambda: self.db_cache.get_indices(cache_key),
            cache_store=lambda items: self.db_cache.set_indices(cache_key, items),
            fetch_rows=lambda: self._execute_metadata_many(
                "indices",
                params=self._add_metadata_context_params({"tabla": tabla}, context_database),
                error_message="Error obteniendo índices",
                table_name=tabla,
            ),
            cache_hit_message=f"♻️  Usando índices en caché para {tabla}",
            success_message=f"✅ {{count}} índices obtenidos de {tabla} ({context_label}: {context_database})",
            fetch_debug_message=f"🔍 Obteniendo índices de {tabla} ({context_label}: {context_database})",
        )
        return cast(Rows, rows)

    async def get_primary_keys(self, tabla: str) -> Rows:
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)
        rows = await self._get_cached_rows_async(
            cache_lookup=lambda: self.db_cache.get_primary_keys(cache_key),
            cache_store=lambda items: self.db_cache.set_primary_keys(cache_key, items),
            fetch_rows=lambda: self._execute_metadata_many(
                "claves_primarias",
                params=self._add_metadata_context_params({"tabla": tabla}, context_database),
                error_message="Error obteniendo claves primarias",
                table_name=tabla,
            ),
            cache_hit_message=f"♻️  Usando claves primarias en caché para {tabla}",
            success_message=f"✅ {{count}} claves primarias obtenidas de {tabla} ({context_label}: {context_database})",
            fetch_debug_message=f"🔍 Obteniendo claves primarias de {tabla} ({context_label}: {context_database})",
        )
        return cast(Rows, rows)

    async def get_foreign_keys(self, tabla: str) -> Rows:
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)
        rows = await self._get_cached_rows_async(
            cache_lookup=lambda: self.db_cache.get_foreign_keys(cache_key),
            cache_store=lambda items: self.db_cache.set_foreign_keys(cache_key, items),
            fetch_rows=lambda: self._execute_metadata_many(
                "claves_foraneas",
                params=self._add_metadata_context_params({"tabla": tabla}, context_database),
                error_message="Error obteniendo claves foráneas",
                table_name=tabla,
            ),
            cache_hit_message=f"♻️  Usando claves foráneas en caché para {tabla}",
            success_message=f"✅ {{count}} claves foráneas obtenidas de {tabla} ({context_label}: {context_database})",
            fetch_debug_message=f"🔍 Obteniendo claves foráneas de {tabla} ({context_label}: {context_database})",
        )
        return cast(Rows, rows)

    async def get_unique_constraints(self, tabla: str) -> Rows:
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)
        rows = await self._get_cached_rows_async(
            cache_lookup=lambda: self.db_cache.get_unique_constraints(cache_key),
            cache_store=lambda items: self.db_cache.set_unique_constraints(cache_key, items),
            fetch_rows=lambda: self._execute_metadata_many(
                "claves_unicas",
                params=self._add_metadata_context_params({"tabla": tabla}, context_database),
                error_message="Error obteniendo restricciones únicas",
                table_name=tabla,
            ),
            cache_hit_message=f"♻️  Usando restricciones únicas en caché para {tabla}",
            success_message=f"✅ {{count}} restricciones únicas obtenidas de {tabla} ({context_label}: {context_database})",
            fetch_debug_message=f"🔍 Obteniendo restricciones únicas de {tabla} ({context_label}: {context_database})",
        )
        return cast(Rows, rows)

    async def get_tables_normalized(self) -> list[NormalizedTableRow]:
        """Obtiene tablas en formato normalizado homogéneo."""
        rows: Rows = await self.get_tables()
        return normalize_table_rows(rows)

    async def get_columns_normalized(self, tabla: str) -> list[NormalizedColumnRow]:
        """Obtiene columnas en formato normalizado homogéneo."""
        rows: Rows = await self.get_columns(tabla)
        return normalize_column_rows(rows)

    async def _storage_inventory_sqlserver(self, _context_database: str, _tablespace: str | None) -> dict[str, Any]:
        return {
            "primary": await self.execute_query_many("ficheros_fisicos"),
            "temp_tablespaces": await self.execute_query_many("temp_tablespaces"),
        }

    async def _storage_inventory_oracle(self, _context_database: str, tablespace: str | None) -> dict[str, Any]:
        if not tablespace:
            raise ValueError("Para Oracle debe proporcionar 'tablespace'")
        return {
            "primary": await self.execute_query_many("ficheros_fisicos", tablespace=tablespace),
            "temp_tablespaces": await self.execute_query_many("temp_tablespaces", tablespace=tablespace),
        }

    async def _storage_inventory_mariadb(self, context_database: str, _tablespace: str | None) -> dict[str, Any]:
        return await self._get_mariadb_adapter().storage_inventory(context_database)

    async def _storage_inventory_postgresql(self, _context_database: str, tablespace: str | None) -> dict[str, Any]:
        if not tablespace:
            raise ValueError("Para PostgreSQL debe proporcionar 'tablespace'")
        return {
            "primary": await self.execute_query_many("ficheros_fisicos", tablespace=tablespace),
            "temp_tablespaces": await self.execute_query_many("temp_tablespaces"),
        }

    async def _storage_inventory_sqlite(self, _context_database: str, _tablespace: str | None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "primary": await self.execute_query_many("ficheros_fisicos"),
            "sqlite_file_summary": await self.execute_query_many("sqlite_file_summary"),
        }
        try:
            result["temp_tablespaces"] = await self.execute_query_many("temp_tablespaces")
        except Exception:
            result["temp_tablespaces"] = []
        return result

    async def get_storage_inventory(self, tablespace: str | None = None) -> dict[str, Any]:
        context_database: str = self._get_query_context_database()
        handler = self._get_storage_inventory_handler()
        if handler is None:
            return {"primary": []}
        result = await handler(context_database, tablespace)
        return result

    async def get_database_version(self) -> str:
        self.logger.debug(f"🔍 Obteniendo versión de la BD ({self.db_type})")
        row = self.result_normalizer.normalize_one(
            await self._execute_metadata_one(
                "database_version",
                params={},
                error_message="Error obteniendo versión",
                table_name="database_version",
            )
        )
        return str(row[0]) if row else "Unknown"

    async def get_database_charset_collation(self) -> dict[str, Any]:
        context_database: str = self._get_query_context_database()
        self.logger.debug(f"🔍 Obteniendo charset/collation de la BD ({self.db_type})")
        row = self.result_normalizer.normalize_one(
            await self._execute_metadata_one(
                "database_charset_collation",
                params={"database": context_database},
                error_message="Error obteniendo charset/collation",
                table_name="database_charset_collation",
            )
        )
        return self._parse_charset_collation_result(row)

    async def get_columns_charset_collation(self, tabla: str) -> list[tuple[str, str | None, str | None]]:
        context_database: str = self._get_query_context_database()
        context_label: str = self._get_query_context_label()
        cache_key: tuple[str, str] = self._cache_table_key(context_database, tabla)

        supports_columns_charset = self._supports_columns_charset_collation()
        if self.db_type == "oracle":
            cached_support = getattr(self, "_oracle_column_collation_supported", None)
            if cached_support is None:
                version_text: str = await self.get_database_version()
                version_match: re.Match[str] | None = re.search(r"Release\s+(\d+)\.(\d+)", version_text)
                supports_columns_charset = False
                if version_match:
                    major = int(version_match.group(1))
                    minor = int(version_match.group(2))
                    supports_columns_charset = (major, minor) >= (12, 2)
                self._oracle_column_collation_supported: bool = supports_columns_charset
            else:
                supports_columns_charset = bool(cached_support)

        if not supports_columns_charset:
            self.logger.debug(
                "ℹ️ Charset/collation por columna no soportado para %s; devolviendo lista vacía para %s",
                self.db_type,
                tabla,
            )
            empty_rows: list[tuple[str, str | None, str | None]] = []
            self.db_cache.set_columns_charset_collation(cache_key, empty_rows)
            return empty_rows

        async def _fetch_charset_collation() -> list[Any]:
            rows = await self._execute_metadata_many(
                "columns_charset_collation",
                params={"tabla": tabla, "database": context_database},
                error_message="Error obteniendo charset/collation de columnas",
                table_name=tabla,
            )
            return [self.__parse_column_charset_collation_row(row) for row in rows]

        rows = await self._get_cached_rows_async(
            cache_lookup=lambda: self.db_cache.get_columns_charset_collation(cache_key),
            cache_store=lambda items: self.db_cache.set_columns_charset_collation(cache_key, items),
            fetch_rows=_fetch_charset_collation,
            cache_hit_message=f"♻️  Usando charset/collation en caché para tabla {tabla}",
            success_message=f"✅ Charset/Collation de {{count}} columnas obtenido ({context_label}: {context_database})",
            fetch_debug_message=f"🔍 Obteniendo charset/collation de columnas de {tabla} ({context_label}: {context_database})",
        )
        return cast(list[tuple[str, str | None, str | None]], rows)

    async def get_query_info(self) -> dict[str, Any]:
        executor = await self._get_query_executor()

        def _build_query_info() -> dict[str, Any]:
            queries: dict[str, str] = executor.registry.queries.get(self.db_type, {})
            info: dict[str, Any] = {
                "db_type": self.db_type,
                "total_queries": len(queries),
                "query_names": list(queries.keys()),
                "queries": {},
            }
            for name, query in queries.items():
                required_params: list[str] = list(set(re.findall(self._PARAMETER_PATTERN, query)))
                info["queries"][name] = {
                    "template": query,
                    "required_parameters": required_params,
                    "parameter_count": len(required_params),
                }
            return info

        result = await self._run_manager_operation_async(
            action=_build_query_info,
            error_message="Error obteniendo información de consultas",
            operation="SELECT",
        )
        return cast(dict[str, Any], result)

    def get_database_type_description(self) -> str:
        """Devuelve la descripción del tipo de base de datos configurado."""
        return get_database_validator().get_db_type_description(self.db_type)

    def get_database_type_info(self) -> dict[str, Any]:
        """Obtiene información completa del tipo de base de datos."""
        return get_database_validator().get_db_type_info(self.db_type)

    def get_database_type_name(self) -> str:
        """Obtiene el nombre descriptivo del tipo de base de datos."""
        return get_database_validator().get_db_type_name(self.db_type)

    def get_database_type_features(self) -> list[str]:
        """Obtiene las características soportadas del tipo de base de datos."""
        return get_database_validator().get_db_type_features(self.db_type)

    def get_database_type_driver_info(self) -> dict[str, Any]:
        """Obtiene información del driver del tipo de base de datos."""
        return get_database_validator().get_db_type_driver_info(self.db_type)

    def get_required_params(self) -> list[str]:
        """Obtiene los parámetros requeridos para el tipo de base de datos."""
        return get_database_validator().get_required_params(self.db_type)

    def get_optional_params(self) -> list[dict[str, Any]]:
        """Obtiene los parámetros opcionales para el tipo de base de datos."""
        return get_database_validator().get_optional_params(self.db_type)

    def get_database_type_examples(self) -> dict[str, Any]:
        """Obtiene ejemplos de configuración para el tipo de base de datos."""
        return get_database_validator().get_db_type_examples(self.db_type)

    def get_default_port(self) -> int:
        """Obtiene el puerto por defecto del tipo de base de datos."""
        return get_database_validator().get_db_type_default_port(self.db_type)

    async def get_database_info(self) -> dict[str, Any]:
        """Obtiene información básica de la base de datos y su configuración."""
        return {
            "db_type": self.db_type,
            "db_type_name": self.get_database_type_name(),
            "db_type_description": self.get_database_type_description(),
            "database": self.database,
            "connection_params": dict(self.conn_params),
            "default_port": self.get_default_port(),
            "required_params": self.get_required_params(),
            "optional_params": self.get_optional_params(),
            "supported_features": self.get_database_type_features(),
            "driver_info": self.get_database_type_driver_info(),
            "available_queries": await self.get_available_queries(),
            "connection_status": "connected"
            if (self.pool_connection is not None or self._connection is not None)
            else "disconnected",
        }

    def get_relationship_cache(self) -> RelationshipMetadataCache:
        """Retorna caché centralizada de metadatos de relaciones."""
        return self.relationship_cache

    async def get_sqlalchemy_engine(self) -> Any:
        """Obtiene un AsyncEngine de SQLAlchemy basado en la configuración actual."""
        return await AsyncSQLAlchemyEngineFactory.create_engine(
            self.db_type,
            self.conn_params,
            self.database,
            use_pool=self.use_pool,
            pool_size=int(self.conn_params.get("pool_size", 5)),
            max_overflow=int(self.conn_params.get("max_overflow", 10)),
            pool_timeout=int(self.conn_params.get("pool_timeout", 30)),
            pool_recycle=int(self.conn_params.get("pool_recycle", 1800)),
            sql_server_driver=str(self.conn_params.get("sql_server_driver", "aioodbc")),
        )

    @staticmethod
    def get_supported_db_types() -> list[str]:
        """Obtiene lista de tipos de bases de datos soportados."""
        return get_supported_db_types()

    @staticmethod
    def get_db_type_info_static(db_type: str) -> dict[str, Any]:
        """Obtiene información de un tipo de base de datos (método estático)."""
        return get_db_type_info(db_type)

    async def get_available_queries(self) -> list[str]:
        executor = await self._get_query_executor()
        result = await self._run_manager_operation_async(
            action=lambda: executor.registry.get_available_queries(self.db_type),
            error_message="Error obteniendo listado de consultas disponibles",
            operation="SELECT",
        )
        return cast(list[str], result)
