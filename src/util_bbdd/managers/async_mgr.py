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
)
from ..results import ResultNormalizer, RowOrNone
from ._manager_lifecycle import (
    close_async_resources,
    get_async_connection,
    init_async_resources,
    release_async_connection,
)
from ._manager_metadata import (
    add_metadata_context_params,
    cache_context_key,
    cache_routine_key,
    cache_table_key,
    clear_all_caches,
    clear_context_cache,
    clear_routine_cache,
    clear_table_cache,
    clear_tuple_cache_by_context,
    get_query_context_database,
    get_query_context_label,
)
from ._manager_metadata_runtime import (
    MetadataFetchRequest,
    build_async_rows_fetcher,
    build_async_text_fetcher,
    build_columns_fetch_request,
    build_routine_ddl_fetch_request,
    build_routine_parameters_fetch_request,
    build_routines_fetch_request,
    build_table_ddl_fetch_request,
    build_view_ddl_fetch_request,
    normalize_ddl_result as normalize_manager_ddl_result,
    oracle_supports_columns_charset_collation,
    parse_charset_collation_result,
    parse_column_charset_collation_row,
    supports_columns_charset_collation as supports_manager_columns_charset_collation,
)
from ._manager_storage import get_storage_inventory_handler


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

    async def _execute_metadata_fetch_request_many(self, request: MetadataFetchRequest) -> Rows:
        return await self._execute_metadata_many(
            request.query_name,
            params=request.params,
            error_message=request.error_message,
            table_name=request.table_name,
        )

    async def _execute_metadata_fetch_request_one(self, request: MetadataFetchRequest) -> RowOrNone:
        return await self._execute_metadata_one(
            request.query_name,
            params=request.params,
            error_message=request.error_message,
            table_name=request.table_name,
        )

    def _get_routines_fetcher(self, context_database: str) -> Callable[[], Awaitable[Rows]]:
        return build_async_rows_fetcher(
            db_type=self.db_type,
            mariadb_fetcher=lambda: self._fetch_mariadb_routines(context_database),
            request=build_routines_fetch_request(context_database),
            execute_many=self._execute_metadata_fetch_request_many,
        )

    def _get_table_ddl_fetcher(self, context_database: str, tabla: str) -> Callable[[], Awaitable[str]]:
        return build_async_text_fetcher(
            db_type=self.db_type,
            mariadb_fetcher=lambda: self._build_mariadb_ddl_from_metadata(tabla),
            request=build_table_ddl_fetch_request(
                context_database,
                tabla,
                self._add_metadata_context_params,
            ),
            execute_one=self._execute_metadata_fetch_request_one,
            normalize_one=self._normalize_ddl_result,
        )

    def _get_view_ddl_fetcher(self, context_database: str, vista: str) -> Callable[[], Awaitable[str]]:
        return build_async_text_fetcher(
            db_type=self.db_type,
            mariadb_fetcher=lambda: self._fetch_mariadb_view_from_information_schema(context_database, vista),
            request=build_view_ddl_fetch_request(
                context_database,
                vista,
                self._add_metadata_context_params,
            ),
            execute_one=self._execute_metadata_fetch_request_one,
            normalize_one=self._normalize_ddl_result,
        )

    def _get_columns_fetcher(self, context_database: str, tabla: str) -> Callable[[], Awaitable[Rows]]:
        return build_async_rows_fetcher(
            db_type=self.db_type,
            mariadb_fetcher=lambda: self._fetch_mariadb_columns_safe(context_database, tabla),
            request=build_columns_fetch_request(context_database, tabla),
            execute_many=self._execute_metadata_fetch_request_many,
        )

    def _get_routine_parameters_fetcher(
        self,
        context_database: str,
        rutina: str,
        routine_type: str,
    ) -> Callable[[], Awaitable[Rows]]:
        return build_async_rows_fetcher(
            db_type=self.db_type,
            mariadb_fetcher=lambda: self._fetch_mariadb_routine_parameters_public_rows(
                context_database=context_database,
                rutina=rutina,
                routine_type=routine_type,
            ),
            request=build_routine_parameters_fetch_request(
                context_database,
                rutina,
                routine_type,
            ),
            execute_many=self._execute_metadata_fetch_request_many,
        )

    def _get_routine_ddl_fetcher(
        self,
        context_database: str,
        rutina: str,
        routine_type: str,
    ) -> Callable[[], Awaitable[str]]:
        return build_async_text_fetcher(
            db_type=self.db_type,
            mariadb_fetcher=lambda: self._fetch_mariadb_routine_from_information_schema(
                context_database,
                rutina,
                routine_type,
            ),
            request=build_routine_ddl_fetch_request(
                context_database,
                rutina,
                routine_type,
                self._add_metadata_context_params,
            ),
            execute_one=self._execute_metadata_fetch_request_one,
            normalize_one=self._normalize_ddl_result,
        )

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
        return get_storage_inventory_handler(self.db_type, handlers)

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
        normalized_db_type: str = db_type.lower().strip()
        validator = get_database_validator()
        validator.validate_db_type(normalized_db_type)
        self.db_type: str = normalized_db_type
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

        self.use_pool, self.pool_connection, self._connection = await init_async_resources(
            use_pool=self.use_pool,
            create_pool=lambda: self._pool_factory(self.db_type, self.conn_params),
            create_connection=lambda: self._connection_factory(self.db_type, self.conn_params),
        )

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
        return await get_async_connection(
            initialized=self._initialized,
            ensure_initialized=self.init,
            pool_connection=self.pool_connection,
            connection=self._connection,
        )

    async def release_connection(self, connection: Any) -> None:
        """Libera conexión al pool o no-op en conexión directa."""
        await release_async_connection(pool_connection=self.pool_connection, connection=connection)

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
            action=lambda: executor.resolver.bind(self.db_type).resolve(query_name, params),
            error_message=f"Error resolviendo consulta: {query_name}",
            operation="SELECT",
        )

    async def close(self, mode: AsyncCloseMode | str = "immediate") -> None:
        """Cierra pool o conexión directa con política explícita."""
        close_mode: AsyncCloseMode = normalize_close_mode(mode)
        pool_connection = self.pool_connection
        connection = self._connection
        try:
            await close_async_resources(
                pool_connection=pool_connection,
                connection=connection,
                close_mode=close_mode,
            )
        finally:
            self.pool_connection = None
            self._connection = None
            self._initialized = False

    def _get_query_context_database(self) -> str:
        """Obtiene contexto schema/database para consultas de metadatos."""
        return get_query_context_database(
            db_type=self.db_type,
            database=self.database,
            conn_params=self.conn_params,
        )

    def _add_metadata_context_params(self, params: dict[str, Any], context: str | None) -> dict[str, Any]:
        """Añade parámetros de contexto metadata según motor."""
        return add_metadata_context_params(db_type=self.db_type, params=params, context=context)

    def _get_query_context_label(self) -> str:
        """Obtiene etiqueta descriptiva del contexto de metadatos."""
        return get_query_context_label(self.db_type)

    def get_query_context_database(self) -> str:
        """Devuelve contexto efectivo schema/database para metadata."""
        return self._get_query_context_database()

    def _clear_all_caches(self) -> None:
        """Limpia completamente todas las cachés de metadatos."""
        clear_all_caches(db_cache=self.db_cache, relationship_cache=self.relationship_cache, logger=self.logger)

    def _clear_table_cache(self, context: str, table: str) -> None:
        """Limpia caché para una tabla/vista específica."""
        clear_table_cache(
            db_cache=self.db_cache,
            relationship_cache=self.relationship_cache,
            logger=self.logger,
            context=context,
            table=table,
        )

    def _clear_routine_cache(self, context: str, routine: str, routine_type: str | None = None) -> None:
        """Limpia caché para una rutina específica."""
        clear_routine_cache(
            db_cache=self.db_cache,
            logger=self.logger,
            context=context,
            routine=routine,
            routine_type=routine_type,
        )

    @staticmethod
    def _clear_tuple_cache_by_context(cache: dict[tuple[Any, ...], Any], context: str) -> None:
        clear_tuple_cache_by_context(cache, context)

    def _clear_context_cache(self, context: str) -> None:
        """Limpia caché para un contexto/schema específico."""
        clear_context_cache(db_cache=self.db_cache, logger=self.logger, context=context)

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
        return cache_context_key(context_database)

    def _cache_table_key(self, context_database: str, table_name: str) -> tuple[str, str]:
        return cache_table_key(context_database, table_name)

    def _cache_routine_key(self, context_database: str, routine_name: str, routine_type: str) -> tuple[str, str, str]:
        return cache_routine_key(context_database, routine_name, routine_type)

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

    def _parse_charset_collation_result(self, result: tuple[Any, ...] | None) -> dict[str, Any]:
        return parse_charset_collation_result(self.db_type, result)

    def _normalize_ddl_result(self, ddl: Any) -> str:
        return normalize_manager_ddl_result(ddl)

    def __parse_column_charset_collation_row(self, row: tuple[Any, ...]) -> tuple[str, str | None, str | None]:
        return parse_column_charset_collation_row(self.db_type, row)

    def _supports_columns_charset_collation(self) -> bool:
        """Indica si el motor expone metadata fiable de charset/collation por columna."""
        if self.db_type == "oracle":
            cached_support = getattr(self, "_oracle_column_collation_supported", None)
            if cached_support is not None:
                return supports_manager_columns_charset_collation(self.db_type, bool(cached_support))
            return supports_manager_columns_charset_collation(self.db_type)

        return supports_manager_columns_charset_collation(self.db_type)

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

    async def _get_table_metadata_rows_async(
        self,
        *,
        tabla: str,
        query_name: str,
        error_message: str,
        cache_lookup: Callable[[tuple[str, str]], Rows | None],
        cache_store: Callable[[tuple[str, str], Rows], None],
        cache_label: str,
        success_label: str,
    ) -> Rows:
        """Template method interno para obtener metadatos tabulares cacheados (async)."""
        context_database: str = self._get_query_context_database()
        context_label: str = self._get_query_context_label()
        cache_key: tuple[str, str] = self._cache_table_key(context_database, tabla)

        rows = await self._get_cached_rows_async(
            cache_lookup=lambda: cache_lookup(cache_key),
            cache_store=lambda items: cache_store(cache_key, cast(Rows, items)),
            fetch_rows=lambda: self._execute_metadata_many(
                query_name,
                params=self._add_metadata_context_params({"tabla": tabla}, context_database),
                error_message=error_message,
                table_name=tabla,
            ),
            cache_hit_message=f"♻️  Usando {cache_label} en caché para {tabla}",
            success_message=f"✅ {{count}} {success_label} obtenidas de {tabla} ({context_label}: {context_database})",
            fetch_debug_message=f"🔍 Obteniendo {success_label} de {tabla} ({context_label}: {context_database})",
        )
        return cast(Rows, rows)

    async def get_indices(self, tabla: str) -> Rows:
        return await self._get_table_metadata_rows_async(
            tabla=tabla,
            query_name="indices",
            error_message="Error obteniendo índices",
            cache_lookup=self.db_cache.get_indices,
            cache_store=self.db_cache.set_indices,
            cache_label="índices",
            success_label="índices",
        )

    async def get_primary_keys(self, tabla: str) -> Rows:
        return await self._get_table_metadata_rows_async(
            tabla=tabla,
            query_name="claves_primarias",
            error_message="Error obteniendo claves primarias",
            cache_lookup=self.db_cache.get_primary_keys,
            cache_store=self.db_cache.set_primary_keys,
            cache_label="claves primarias",
            success_label="claves primarias",
        )

    async def get_foreign_keys(self, tabla: str) -> Rows:
        return await self._get_table_metadata_rows_async(
            tabla=tabla,
            query_name="claves_foraneas",
            error_message="Error obteniendo claves foráneas",
            cache_lookup=self.db_cache.get_foreign_keys,
            cache_store=self.db_cache.set_foreign_keys,
            cache_label="claves foráneas",
            success_label="claves foráneas",
        )

    async def get_unique_constraints(self, tabla: str) -> Rows:
        return await self._get_table_metadata_rows_async(
            tabla=tabla,
            query_name="claves_unicas",
            error_message="Error obteniendo restricciones únicas",
            cache_lookup=self.db_cache.get_unique_constraints,
            cache_store=self.db_cache.set_unique_constraints,
            cache_label="restricciones únicas",
            success_label="restricciones únicas",
        )

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
                supports_columns_charset = oracle_supports_columns_charset_collation(version_text)
                self._oracle_column_collation_supported: bool = supports_columns_charset
            else:
                supports_columns_charset = bool(cached_support)
            supports_columns_charset = supports_manager_columns_charset_collation(
                self.db_type,
                supports_columns_charset,
            )

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
