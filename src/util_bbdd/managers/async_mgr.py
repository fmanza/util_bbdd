"""Gestor async de conexiones y ejecucion de consultas."""

from __future__ import annotations

import logging
import re

from collections.abc import Awaitable, Callable, Collection
from typing import Any, cast

from util_bbdd._drivers.validator import DatabaseTypeValidator

from .._core.exceptions import DatabaseOperationError, QueryError
from .._drivers import get_database_validator, get_db_type_info, get_supported_db_types
from ..async_utils import maybe_await
from ..connection.close import AsyncCloseMode, normalize_close_mode
from ..connection.factory import ConnectionFactory
from ..executors.async_query_executor import AsyncQueryExecutor
from ..factory.async_sqlalchemy_engine_factory import AsyncSQLAlchemyEngineFactory
from ..factory.pool_factory import PoolFactory
from ..metadata import (
    DatabaseMetadataCache,
    Rows,
)
from ..metadata.catalog_registry import get_catalog_dialect
from ..metadata.model import ALL_KINDS, Kind, SchemaSnapshot
from ..metadata.source import AsyncCatalogSource
from ..results import ResultNormalizer, RowOrNone
from ._catalog_executor import AsyncManagerCatalogExecutor
from ._catalog_facade import AsyncCatalogFacade
from ._manager_cache_service import CacheService
from ._manager_lifecycle import (
    close_async_resources,
    get_async_connection,
    init_async_resources,
    release_async_connection,
)
from ._manager_shared_mixin import DatabaseManagerSharedMixin


class AsyncDatabaseManager(AsyncCatalogFacade, DatabaseManagerSharedMixin):
    """Manager async-first para conexiones directas o con pool."""

    _PARAMETER_PATTERN = r"\{(\w+)\}"
    _ERROR_EXECUTOR_NOT_INITIALIZED = "AsyncQueryExecutor no inicializado"

    def __init__(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        use_pool: bool = True,
        connection_factory: Callable[..., Awaitable[Any]] | None = None,
        pool_factory: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        """Inicializa el gestor async de base de datos."""
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.info(f"🔧 Inicializando AsyncDatabaseManager para {db_type.upper()}")

        # Validar tipo de BD
        normalized_db_type: str = db_type.lower().strip()
        validator: DatabaseTypeValidator = get_database_validator()
        validator.validate_db_type(normalized_db_type)

        self.db_type: str = normalized_db_type
        self.conn_params: dict[str, Any] = conn_params
        self.database: str = str(conn_params.get("database", "") or "").strip()
        self.use_pool: bool = use_pool

        # Inicializar cachés centralizados
        self.db_cache: DatabaseMetadataCache = DatabaseMetadataCache()
        self.logger.debug("✅ Cachés centralizados inicializados")

        # Inicializar servicio de caché
        self.cache_service = CacheService(self.db_cache, self.logger)

        # Factories para conexión
        self._connection_factory: Callable[..., Awaitable[Any]] = (
            connection_factory or ConnectionFactory.create_async_connection
        )
        self._pool_factory: Callable[..., Awaitable[Any]] = pool_factory or PoolFactory.create_async_pool

        # Estado de conexión
        self._initialized: bool = False
        self._connection: Any = None
        self.pool_connection: Any = None
        self.query_executor: AsyncQueryExecutor | None = None
        self.result_normalizer = ResultNormalizer()

        self.logger.debug("✅ AsyncDatabaseManager pre-inicializado")

    async def init(self) -> AsyncDatabaseManager:
        """Inicializa recursos async una única vez."""
        if self._initialized:
            return self

        self.use_pool, self.pool_connection, self._connection = await init_async_resources(
            use_pool=self.use_pool,
            create_pool=lambda: self._pool_factory(self.db_type, self.conn_params),
            create_connection=lambda: self._connection_factory(self.db_type, self.conn_params),
        )

        # Construir executor
        self.query_executor = AsyncQueryExecutor(
            connection_provider=self.get_connection,
            connection_releaser=self.release_connection,
        )
        self._initialized = True
        self.logger.info("✅ AsyncDatabaseManager inicializado")
        return self

    async def __aenter__(self) -> AsyncDatabaseManager:
        return await self.init()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close(mode="immediate")

    async def get_connection(self) -> Any:
        """Obtiene conexión del pool o directa."""
        await self._ensure_initialized()
        return await get_async_connection(
            initialized=self._initialized,
            ensure_initialized=self._noop_init,
            pool_connection=self.pool_connection,
            connection=self._connection,
        )

    async def _noop_init(self) -> None:
        """Inicialización no-op (ya está hecha en init())."""
        pass

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
        executor: AsyncQueryExecutor | None = self.query_executor
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
        executor: AsyncQueryExecutor = await self._get_query_executor()
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
        executor: AsyncQueryExecutor = await self._get_query_executor()
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
        """
        Ejecuta SQL custom y retorna múltiples filas.

        Args:
            sql: Consulta SQL a ejecutar.
            params: Diccionario de parámetros SQL (opcional).

        Returns:
            Lista de filas resultantes.

        Raises:
            QueryError: Si hay error en la ejecución de la query.

        Example:
            Ejecutar una query personalizada (async):

            >>> import asyncio
            >>> from util_bbdd import AsyncDatabaseManager
            >>> async def main():
            ...     manager = AsyncDatabaseManager(
            ...         db_type="postgresql",
            ...         conn_params={
            ...             "host": "localhost",
            ...             "port": 5432,
            ...             "user": "postgres",
            ...             "password": "secret",
            ...             "database": "mydb"
            ...         }
            ...     )
            ...     await manager.init()
            ...     result = await manager.execute_custom_many("SELECT * FROM users LIMIT 5")
            ...     print(f"Encontradas {len(result)} filas")
            ...     await manager.close()
            >>> asyncio.run(main())
        """
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
        """
        Ejecuta SQL custom y retorna una única fila o None.

        Args:
            sql: Consulta SQL a ejecutar.
            params: Diccionario de parámetros SQL (opcional).

        Returns:
            Una tupla (fila) si encuentra resultado, None si no hay filas.

        Raises:
            QueryError: Si hay error en la ejecución de la query.

        Example:
            Obtener un registro único (async):

            >>> import asyncio
            >>> from util_bbdd import AsyncDatabaseManager
            >>> async def main():
            ...     manager = AsyncDatabaseManager(
            ...         db_type="postgresql",
            ...         conn_params={
            ...             "host": "localhost",
            ...             "port": 5432,
            ...             "user": "postgres",
            ...             "password": "secret",
            ...             "database": "mydb"
            ...         }
            ...     )
            ...     await manager.init()
            ...     user = await manager.execute_custom_one(
            ...         "SELECT id, name, email FROM users WHERE id = :id",
            ...         params={"id": 123}
            ...     )
            ...     if user:
            ...         print(f"Usuario encontrado: {user[1]} ({user[2]})")
            ...     else:
            ...         print("Usuario no encontrado")
            ...     await manager.close()
            >>> asyncio.run(main())
        """
        result = await self._execute_custom_sql(
            sql=sql,
            params=params,
            expect_one=True,
        )
        return cast(RowOrNone, result)

    async def execute_query_many(
        self,
        query_name: str,
        **params: Any,
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
        executor: AsyncQueryExecutor = await self._get_query_executor()
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
                db_type=self.db_type,
                logger=self.logger,
            )
        finally:
            self.pool_connection = None
            self._connection = None
            self._initialized = False

    async def _execute_metadata_many(
        self,
        query_name: str,
        *,
        params: dict[str, Any],
        error_message: str,
        table_name: str | None = None,
    ) -> Rows:
        executor: AsyncQueryExecutor = await self._get_query_executor()
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
        cached_rows: list[Any] | None = cache_lookup()
        if cached_rows is not None:
            if cache_hit_message:
                self.logger.debug(cache_hit_message)
            return list(cached_rows)
        if fetch_debug_message:
            self.logger.debug(fetch_debug_message)
        rows = list(await fetch_rows())
        cache_store(rows)
        if success_message:
            self.logger.info(f"Success: {len(rows)} rows")
        return rows

    async def get_query_info(self) -> dict[str, Any]:
        executor: AsyncQueryExecutor = await self._get_query_executor()

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

    @property
    def metadata_source(self) -> AsyncCatalogSource:
        """Lectura async del catálogo por lotes sobre las conexiones de este manager (ADR-003).

        Ver :meth:`get_schema_metadata`; ``clear_cache()`` invalida su caché.
        """
        source: AsyncCatalogSource | None = self.__dict__.get("_catalog_source")
        if source is None:
            source = AsyncCatalogSource(
                get_catalog_dialect(self.db_type),
                AsyncManagerCatalogExecutor(self.get_connection, self.release_connection),
                source_id=self._catalog_source_id(),
                cache=self._catalog_cache(),
                default_schema=self._catalog_default_schema(),
            )
            self.__dict__["_catalog_source"] = source
        return source

    async def get_schema_metadata(
        self,
        schema: str | None = None,
        *,
        kinds: Collection[Kind] = ALL_KINDS,
        tables: Collection[str] | None = None,
    ) -> SchemaSnapshot:
        """Metadatos de un schema con una consulta por tipo de objeto (ver ``SyncDatabaseManager.get_schema_metadata``).

        Example:
            >>> snapshot = await manager.get_schema_metadata(kinds={Kind.TABLES, Kind.COLUMNS})
        """
        return await self.metadata_source.snapshot(schema, kinds=kinds, tables=tables)

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
        executor: AsyncQueryExecutor = await self._get_query_executor()
        result = await self._run_manager_operation_async(
            action=lambda: executor.registry.get_available_queries(self.db_type),
            error_message="Error obteniendo listado de consultas disponibles",
            operation="SELECT",
        )
        return cast(list[str], result)
