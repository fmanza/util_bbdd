"""
Módulo para manejo de operaciones de base de datos.
Soporta MariaDB, Oracle, PostgreSQL, SQLite, HSQLDB y SQL Server.
"""

import logging

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy.engine.base import Engine

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine

from .._foundation.exceptions import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseDriverError,
    DatabaseOperationError,
    DatabaseValidationError,
    QueryError,
)
from .._foundation.queries import DatabaseQueries
from .._foundation.validators_core import (
    DatabaseTypeValidator,
    get_database_validator,
    get_db_type_info,
    get_supported_db_types,
    validate_db_type,
)
from ..connection.close import parse_close_timeout
from ..connection.factory import ConnectionFactory
from ..connection.params import ConnectionParamsManager
from ..connection.protocols import ConnectionPoolProtocol
from ..executors.sync_query_executor import SyncQueryExecutor
from ..factory.pool_factory import PoolFactory
from ..factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory
from ..metadata import (
    DatabaseMetadataCache,
    NormalizedColumnRow,
    NormalizedTableRow,
    RelationshipMetadataCache,
    Rows,
    normalize_column_rows,
    normalize_table_rows,
)
from ..metadata.adapters import get_global_adapter_registry
from ..metadata.mariadb import (
    MariaDBSyncAdapter,
)
from ..results import RowOrNone
from ._manager_cache_service import CacheService
from ._manager_lifecycle import close_sync_resources
from ._manager_lifecycle_sync import SyncLifecycleManager
from ._manager_metadata_factory import MetadataStrategyFactory
from ._manager_metadata_runtime import (
    MetadataFetchRequest,
    build_columns_fetch_request,
    build_routine_ddl_fetch_request,
    build_routine_parameters_fetch_request,
    build_routines_fetch_request,
    build_table_ddl_fetch_request,
    build_view_ddl_fetch_request,
    oracle_supports_columns_charset_collation,
    supports_columns_charset_collation as supports_manager_columns_charset_collation,
)
from ._manager_session import SyncSessionManager
from ._manager_shared_mixin import DatabaseManagerSharedMixin


class SyncDatabaseManager(DatabaseManagerSharedMixin):
    """
    Clase para manejar conexiones y operaciones de base de datos.

    Soporta logging y manejo de excepciones propias.
    Bases de datos soportadas: MariaDB, Oracle, PostgreSQL, SQLite, HSQLDB, SQL Server
    """

    _SYNC_QUERY_EXECUTOR_NOT_INITIALIZED = (
        "Ejecutor sync de consultas no inicializado. Verifique la conexión a la base de datos."
    )
    _query_catalog: DatabaseQueries
    sync_query_executor: SyncQueryExecutor | None

    def __init__(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        queries_file: Path | None = None,
        use_pool: bool = True,
    ):
        """
        Inicializa el gestor de base de datos con soporte de pool de conexiones

        Args:
            db_type: Tipo de base de datos ('mariadb', 'oracle', 'postgresql', 'sqlite', 'hsqldb', 'sqlserver')
            conn_params: Parámetros de conexión (debe incluir 'database'; Oracle acepta 'oracle_client_path')
            queries_file: Ruta al archivo JSON con consultas (opcional)
            use_pool: Habilita pool de conexiones (default True)

        Raises:
            DatabaseValidationError: Si la validación de parámetros falla
            DatabaseDriverError: Si un driver requerido no está disponible
            DatabaseConnectionError: Si la conexión inicial falla
        """
        # Inicializar logger
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.info(f"🔧 Inicializando SyncDatabaseManager para {db_type.upper()}")

        # Inicializar cachés centralizados (composición jerárquica)
        self.db_cache: DatabaseMetadataCache = DatabaseMetadataCache()
        self.relationship_cache: RelationshipMetadataCache = RelationshipMetadataCache(db_cache=self.db_cache)
        self.logger.debug("✅ Cachés centralizados [DatabaseMetadataCache + RelationshipMetadataCache] inicializados")

        # Inicializar servicio de caché
        self.cache_service = CacheService(self.db_cache, self.relationship_cache, self.logger)

        # Inicializar validador de tipos (lazy loading)
        self._db_validator: DatabaseTypeValidator | None = None

        # Normalizar tipo de BD
        normalized_db_type = db_type.lower()
        self._default_close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))

        try:
            # Crear lifecycle manager
            self.lifecycle_manager = SyncLifecycleManager(
                db_type=normalized_db_type,
                conn_params=conn_params.copy(),
                logger=self.logger,
                validators=self.db_validator,
            )

            # Validar parámetros de conexión
            self.lifecycle_manager.validate_connection_params()

            self.db_type: str = normalized_db_type
            self.conn_params = self.lifecycle_manager.conn_params
            self.database: str = self.conn_params.get("database", "")
            self.sql_server_driver: str = self.lifecycle_manager.sql_server_driver

            # Obtener estrategias via factory
            self._metadata_fetch_strategy = MetadataStrategyFactory.get_fetch_strategy(self.db_type)
            self._storage_inventory_strategy = MetadataStrategyFactory.get_storage_strategy(self.db_type)
            self.logger.debug(f"✅ Tipo de BD validado: {self.db_type}")

            # Inicializar gestor de consultas
            queries_path: Path | None = queries_file if queries_file else None
            self._query_catalog = DatabaseQueries(self.db_type, queries_path)
            self.logger.debug("✅ Gestor de consultas inicializado")

            # Inicializar gestor de sesión
            self.session_manager = SyncSessionManager(pool_connection=None, logger=self.logger)

            # Pool de conexiones
            self.use_pool: bool = use_pool
            self.pool_connection: ConnectionPoolProtocol | None = None
            self._connection: Any = None
            self.cursor: Any = None
            self.sync_query_executor: SyncQueryExecutor | None = None

            # Determinar si usar pool
            if self.use_pool and self.lifecycle_manager.supports_pool():
                self._init_pool()
            else:
                if self.use_pool and not self.lifecycle_manager.supports_pool():
                    self.logger.warning(f"⚠️ Pool no soportado para {self.db_type}. Usando conexión única.")
                self.use_pool = False
                self._connect()

            self.logger.info(f"✅ Conexión establecida (BD: {self.db_type})")

        except DatabaseValidationError:
            self.logger.error("❌ Error de validación de parámetros")
            raise
        except DatabaseDriverError:
            self.logger.error("❌ Error en disponibilidad de driver")
            raise
        except DatabaseConnectionError:
            self.logger.error("❌ Error al conectar a la base de datos")
            raise
        except ValueError as e:
            self.logger.error(f"❌ Error de validación: {e}")
            raise DatabaseValidationError(str(e), self.db_type) from e
        except Exception as e:
            self.logger.error(f"❌ Error inesperado inicializando SyncDatabaseManager: {e}")
            raise DatabaseConfigurationError(
                f"Error al inicializar SyncDatabaseManager: {str(e)}", self.db_type, str(e)
            ) from e

    @property
    def db_validator(self) -> DatabaseTypeValidator:
        """Lazy loading del validador de tipos de BD."""
        if self._db_validator is None:
            self._db_validator = DatabaseTypeValidator()
            self.logger.debug("✅ DatabaseTypeValidator inicializado (lazy loading)")
        return self._db_validator

    def _filter_connection_params(self, db_type: str) -> dict:
        """Filtra parámetros de conexión válidos."""
        try:
            filtered = ConnectionParamsManager.sanitize_for_connection(
                db_type,
                self.conn_params,
                driver=self.sql_server_driver if db_type == "sqlserver" else None,
            )
            self.logger.debug(f"✅ Parámetros filtrados para {db_type}: {len(filtered)} parámetros válidos")
            return filtered
        except Exception as e:
            self.logger.error(f"❌ Error filtrando parámetros de conexión: {e}")
            raise DatabaseValidationError(f"Error filtrando parámetros: {str(e)}", db_type, str(e)) from e

    def _init_pool(self) -> None:
        """Inicializa pool de conexiones."""
        try:
            self.pool_connection = PoolFactory.create_pool(self.db_type, self.conn_params)

            # Verificar que el pool puede entregar conexiones
            test_conn = self.pool_connection.get_connection()
            self.pool_connection.close_connection(test_conn)
            self.logger.debug(f"✅ Conexión de prueba obtenida/devuelta al pool para {self.db_type}")
            self.logger.info(f"🔗 Pool habilitado para {self.db_type} (size: {self.conn_params.get('pool_size', 5)})")

            # Actualizar session manager con pool
            self.session_manager.pool_connection = self.pool_connection

            # Inicializar ejecutor stateless (cada operación obtiene/libera conexión)
            self.sync_query_executor = self.session_manager.build_sync_executor(
                connection_provider=lambda: self.get_connection(),
                connection_releaser=lambda conn: self.close_connection(conn),
                registry=self._query_catalog.registry,
                resolver=self._query_catalog.resolver,
            )

        except ValueError as e:
            self.logger.warning(f"⚠️ Pool no disponible: {e}. Usando conexión única.")
            self.use_pool = False
            self._connect()
        except Exception as e:
            self.logger.error(f"❌ Error inicializando pool: {e}")
            raise

    def _connect(self) -> None:
        """Establece una conexión directa a la base de datos."""
        try:
            self.logger.info(f"🔗 Estableciendo conexión a {self.db_type}")

            valid_params = self._filter_connection_params(self.db_type)

            # Crear conexión usando la factory
            self._connection = ConnectionFactory.create_connection(
                self.db_type,
                valid_params,
                db_validator=self.db_validator,
                sql_server_driver=self.sql_server_driver,
            )
            self.logger.info("✅ Conexión establecida exitosamente")

            # Actualizar session manager
            self.session_manager._connection = self._connection

            # Inicializar ejecutor stateless
            self.sync_query_executor = self.session_manager.build_sync_executor(
                connection_provider=lambda: self._connection,
                connection_releaser=lambda _conn: None,
                registry=self._query_catalog.registry,
                resolver=self._query_catalog.resolver,
            )
        except DatabaseConnectionError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error en conexión: {e}")
            raise DatabaseConnectionError(f"Error al conectar a {self.db_type}: {str(e)}", self.db_type, str(e)) from e

    @property
    def connection(self) -> Any:
        """Obtiene la conexión a la base de datos."""
        return self._connection

    @connection.setter
    def connection(self, conn: Any) -> None:
        """Establece la conexión a la base de datos (solo para conexiones directas)."""
        self._connection = conn

    def get_connection(self) -> Any:
        """Obtiene conexión del pool o conexión única."""
        return self.session_manager.get_connection(
            connection=self._connection,
            db_type=self.db_type,
        )

    def close_connection(self, connection: Any | None = None) -> None:
        """Devuelve conexión al pool o cierra conexión única."""
        self.session_manager.close_connection(connection=connection)

    def close(self, timeout_seconds: float | None = None, force: bool = False) -> None:
        """Cierra la conexión a la base de datos y libera recursos del pool."""
        effective_timeout = self._default_close_timeout_seconds if timeout_seconds is None else timeout_seconds
        pool = self.pool_connection
        self.pool_connection = None
        cursor = self.cursor
        self.cursor = None
        connection = self._connection
        self._connection = None

        # Usar lifecycle_manager si existe, sino usar la función directamente (para compatibilidad con tests)
        if hasattr(self, "lifecycle_manager"):
            self.lifecycle_manager.close_resources(
                pool_connection=pool,
                cursor=cursor,
                connection=connection,
                timeout_seconds=effective_timeout,
                force=force,
            )
        else:
            # Fallback para tests que creen el manager sin pasar __init__
            close_sync_resources(
                pool_connection=pool,
                cursor=cursor,
                connection=connection,
                logger=self.logger,
                db_type=self.db_type,
                timeout_seconds=effective_timeout,
                force=force,
            )
        """Verifica que el ejecutor sync de consultas esté inicializado."""
        if not self.sync_query_executor:
            self.logger.error("❌ Ejecutor sync de consultas no inicializado")
            raise DatabaseOperationError(self._SYNC_QUERY_EXECUTOR_NOT_INITIALIZED, db_type=self.db_type)

    def _get_sync_query_executor(self) -> SyncQueryExecutor:
        """Obtiene el ejecutor sync garantizando inicialización."""
        if self.sync_query_executor is None:
            raise DatabaseOperationError(self._SYNC_QUERY_EXECUTOR_NOT_INITIALIZED, db_type=self.db_type)
        return self.sync_query_executor

    def _get_query_executor(self) -> SyncQueryExecutor:
        """Alias de paridad con AsyncDatabaseManager."""
        return self._get_sync_query_executor()

    def _run_manager_operation(
        self,
        action: Callable[[], Any],
        *,
        error_message: str,
        operation: str,
        table_name: str | None = None,
    ) -> Any:
        """Ejecuta operación del manager con passthrough de errores de dominio."""
        try:
            return action()
        except (DatabaseOperationError, QueryError):
            raise
        except Exception as err:
            self.logger.error(f"❌ {error_message}: {err}")
            raise DatabaseOperationError(error_message, operation, table_name, self.db_type) from err

    def _execute_registered_query(
        self,
        *,
        query_name: str,
        params: dict[str, Any],
        timeout: float | None,
        expect_one: bool,
    ) -> RowOrNone | Rows:
        executor = self._get_sync_query_executor()
        mode = "one" if expect_one else "many"
        self.logger.debug(f"📄 Ejecutando consulta ({mode}): {query_name}")
        execute = executor.execute_query_one if expect_one else executor.execute_query_many
        result = self._run_manager_operation(
            action=lambda: execute(
                query_name=query_name,
                db_type=self.db_type,
                params=params,
                timeout=timeout,
            ),
            error_message=f"Error ejecutando consulta: {query_name}",
            operation="SELECT",
        )
        self.logger.info(f"✅ Consulta {query_name} ejecutada exitosamente")
        return cast(RowOrNone | Rows, result)

    def _execute_custom_sql(
        self,
        *,
        sql: str,
        params: dict[str, Any] | None,
        timeout: float | None,
        expect_one: bool,
    ) -> RowOrNone | Rows:
        executor = self._get_sync_query_executor()
        mode = "one" if expect_one else "many"
        self.logger.debug(f"📝 Ejecutando consulta SQL personalizada ({mode})")
        execute = executor.execute_custom_one if expect_one else executor.execute_custom_many
        result = self._run_manager_operation(
            action=lambda: execute(sql=sql, params=params, timeout=timeout),
            error_message="Error ejecutando consulta SQL",
            operation="EXECUTE",
        )
        self.logger.info("✅ Consulta SQL personalizada ejecutada exitosamente")
        return cast(RowOrNone | Rows, result)

    def _get_mariadb_adapter(self) -> MariaDBSyncAdapter:
        adapter = getattr(self, "_mariadb_adapter", None)
        if adapter is None:
            adapter = MariaDBSyncAdapter(self)
            self._mariadb_adapter = adapter
        return cast(MariaDBSyncAdapter, adapter)

    def _get_adapter_sync(self, adapter_type: str) -> Any:
        """Obtiene adapter sync del Registry según db_type y tipo de adapter.

        Esta es la forma genérica y extensible de resolver adapters, a diferencia
        de `_get_mariadb_adapter()` que es específica de MariaDB.

        Args:
            adapter_type: Tipo de adapter ('source' o 'routine')

        Returns:
            Instancia del adapter (SourceAdapter o RoutineAdapter)

        Raises:
            DatabaseConfigurationError: Si no hay adapter registrado para el driver
        """
        cache_key = f"_adapter_sync_{adapter_type}"
        cached_adapter = getattr(self, cache_key, None)
        if cached_adapter is not None:
            return cached_adapter

        registry = get_global_adapter_registry()
        if adapter_type == "source":
            adapter_class = registry.get_source_adapter_sync(self.db_type)
        elif adapter_type == "routine":
            adapter_class = registry.get_routine_adapter_sync(self.db_type)
        else:
            msg = f"Tipo de adapter inválido: {adapter_type}. Use 'source' o 'routine'."
            raise ValueError(msg)

        if adapter_class is None:
            msg = f"No hay adapter sync registrado para {self.db_type} (tipo: {adapter_type})"
            raise DatabaseConfigurationError(msg)

        # Crear instancia y cachear
        adapter = adapter_class(self)
        setattr(self, cache_key, adapter)
        return adapter

    def _execute_metadata_fetch_request_many(self, request: MetadataFetchRequest) -> Rows:
        return self._execute_metadata_many(
            request.query_name,
            params=request.params,
            error_message=request.error_message,
            table_name=request.table_name,
        )

    def _execute_metadata_fetch_request_one(self, request: MetadataFetchRequest) -> RowOrNone:
        return self._execute_metadata_one(
            request.query_name,
            params=request.params,
            error_message=request.error_message,
            table_name=request.table_name,
        )

    def _get_routines_fetcher(self, context_database: str) -> Callable[[], Rows]:
        return self._metadata_fetch_strategy.build_sync_rows_fetcher(
            request=build_routines_fetch_request(context_database),
            specialized_fetcher=lambda: self._get_mariadb_adapter().fetch_routines(context_database),
            execute_many=self._execute_metadata_fetch_request_many,
        )

    def _get_table_ddl_fetcher(self, context_database: str, tabla: str) -> Callable[[], str]:
        return self._metadata_fetch_strategy.build_sync_text_fetcher(
            request=build_table_ddl_fetch_request(
                context_database,
                tabla,
                self._add_metadata_context_params,
            ),
            specialized_fetcher=lambda: self._get_mariadb_adapter().build_table_ddl_from_metadata(tabla),
            execute_one=self._execute_metadata_fetch_request_one,
            normalize_one=self._normalize_ddl_result,
        )

    def _get_view_ddl_fetcher(self, context_database: str, vista: str) -> Callable[[], str]:
        return self._metadata_fetch_strategy.build_sync_text_fetcher(
            request=build_view_ddl_fetch_request(
                context_database,
                vista,
                self._add_metadata_context_params,
            ),
            specialized_fetcher=lambda: self._get_mariadb_adapter().fetch_view_from_information_schema(
                context_database,
                vista,
            ),
            execute_one=self._execute_metadata_fetch_request_one,
            normalize_one=self._normalize_ddl_result,
        )

    def _get_columns_fetcher(self, context_database: str, tabla: str) -> Callable[[], Rows]:
        return self._metadata_fetch_strategy.build_sync_rows_fetcher(
            request=build_columns_fetch_request(context_database, tabla),
            specialized_fetcher=lambda: self._get_mariadb_adapter().fetch_columns_safe(context_database, tabla),
            execute_many=self._execute_metadata_fetch_request_many,
        )

    def _get_routine_parameters_fetcher(
        self,
        context_database: str,
        rutina: str,
        routine_type: str,
    ) -> Callable[[], Rows]:
        return self._metadata_fetch_strategy.build_sync_rows_fetcher(
            specialized_fetcher=lambda: self._get_mariadb_adapter().fetch_routine_parameters_public_rows(
                database=context_database,
                routine_name=rutina,
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
    ) -> Callable[[], str]:
        return self._metadata_fetch_strategy.build_sync_text_fetcher(
            specialized_fetcher=lambda: self._get_mariadb_adapter().fetch_routine_from_information_schema(
                database=context_database,
                routine_name=rutina,
                routine_type=routine_type,
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

    def _log_and_call(self, message: str, action: Callable[[], Any]) -> Any:
        self.logger.debug(message)
        return action()

    def _run_metadata_operation(
        self,
        action: Callable[[], Any],
        *,
        error_message: str,
        table_name: str | None = None,
    ) -> Any:
        return self._run_manager_operation(
            action=action,
            error_message=error_message,
            operation="SELECT",
            table_name=table_name,
        )

    def _execute_metadata_many(
        self,
        query_name: str,
        *,
        params: dict[str, Any],
        error_message: str,
        table_name: str | None = None,
    ) -> Rows:
        executor: SyncQueryExecutor = self._get_sync_query_executor()
        result = self._run_metadata_operation(
            action=lambda: executor.execute_query_many(
                query_name=query_name,
                db_type=self.db_type,
                params=params,
            ),
            error_message=error_message,
            table_name=table_name,
        )
        return cast(Rows, result)

    def _execute_metadata_one(
        self,
        query_name: str,
        *,
        params: dict[str, Any],
        error_message: str,
        table_name: str | None = None,
    ) -> RowOrNone:
        executor: SyncQueryExecutor = self._get_sync_query_executor()
        result = self._run_metadata_operation(
            action=lambda: executor.execute_query_one(
                query_name=query_name,
                db_type=self.db_type,
                params=params,
            ),
            error_message=error_message,
            table_name=table_name,
        )
        return cast(RowOrNone, result)

    def _get_cached_rows(
        self,
        *,
        cache_lookup: Callable[[], list[Any] | None],
        cache_store: Callable[[list[Any]], None],
        fetch_rows: Callable[[], list[Any]],
        cache_hit_message: str,
        success_message: str,
        fetch_debug_message: str | None = None,
    ) -> list[Any]:
        cached_rows = cache_lookup()
        if cached_rows is not None:
            self.logger.debug(cache_hit_message)
            return list(cached_rows)
        if fetch_debug_message:
            self.logger.debug(fetch_debug_message)
        rows = list(fetch_rows())
        cache_store(rows)
        self.logger.info(success_message.format(count=len(rows)))
        return rows

    def _get_cached_rows_sync(
        self,
        *,
        cache_lookup: Callable[[], list[Any] | None],
        cache_store: Callable[[list[Any]], None],
        fetch_rows: Callable[[], list[Any]],
        cache_hit_message: str,
        success_message: str,
        fetch_debug_message: str | None = None,
    ) -> list[Any]:
        """Alias de paridad con AsyncDatabaseManager."""
        return self._get_cached_rows(
            cache_lookup=cache_lookup,
            cache_store=cache_store,
            fetch_rows=fetch_rows,
            cache_hit_message=cache_hit_message,
            success_message=success_message,
            fetch_debug_message=fetch_debug_message,
        )

    def _get_cached_text(
        self,
        *,
        cache_lookup: Callable[[], str | None],
        cache_store: Callable[[str], None],
        fetch_text: Callable[[], str],
        cache_hit_message: str,
        success_message: str,
    ) -> str:
        cached_text: str | None = cache_lookup()
        if cached_text is not None:
            self.logger.debug(cache_hit_message)
            return cached_text
        text: str = fetch_text()
        cache_store(text)
        self.logger.info(success_message)
        return text

    def _get_cached_text_sync(
        self,
        *,
        cache_lookup: Callable[[], str | None],
        cache_store: Callable[[str], None],
        fetch_text: Callable[[], str],
        cache_hit_message: str,
        success_message: str,
    ) -> str:
        """Alias de paridad con AsyncDatabaseManager."""
        return self._get_cached_text(
            cache_lookup=cache_lookup,
            cache_store=cache_store,
            fetch_text=fetch_text,
            cache_hit_message=cache_hit_message,
            success_message=success_message,
        )

    def get_tables(self) -> Rows:
        """
        Obtiene la lista de tablas de la base de datos.

        Returns:
            Lista de tablas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        cache_key: str = self._cache_context_key(context_database)
        context_label: str = self._get_query_context_label()

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache._tables_cache.get(cache_key),
            cache_store=lambda rows: self.db_cache._tables_cache.__setitem__(cache_key, list(rows)),
            fetch_rows=lambda: self._execute_metadata_many(
                "obtener_tablas",
                params={"database": context_database},
                error_message="Error obteniendo tablas",
            ),
            cache_hit_message=f"♻️  Usando tablas en caché para contexto: {context_database}",
            success_message=f"✅ {{count}} tablas obtenidas para {context_label}: {context_database}",
            fetch_debug_message=f"🔍 Obteniendo lista de tablas para {context_label}: {context_database}",
        )

    def get_views(self) -> Rows:
        """
        Obtiene la lista de vistas de la base de datos.

        Returns:
            Lista de vistas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        cache_key: str = self._cache_context_key(context_database)
        context_label: str = self._get_query_context_label()

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache._views_cache.get(cache_key),
            cache_store=lambda rows: self.db_cache._views_cache.__setitem__(cache_key, list(rows)),
            fetch_rows=lambda: self._execute_metadata_many(
                "obtener_vistas",
                params={"database": context_database},
                error_message="Error obteniendo vistas",
            ),
            cache_hit_message=f"♻️  Usando vistas en caché para contexto: {context_database}",
            success_message=f"✅ {{count}} vistas obtenidas para {context_label}: {context_database}",
            fetch_debug_message=f"🔍 Obteniendo lista de vistas para {context_label}: {context_database}",
        )

    def get_routines(self) -> Rows:
        """
        Obtiene la lista de rutinas (procedures y funciones) de la base de datos.

        Returns:
            Lista de rutinas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        cache_key: str = self._cache_context_key(context_database)
        context_label: str = self._get_query_context_label()

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache._routines_cache.get(cache_key),
            cache_store=lambda rows: self.db_cache._routines_cache.__setitem__(cache_key, list(rows)),
            fetch_rows=self._get_routines_fetcher(context_database),
            cache_hit_message=f"♻️  Usando rutinas en caché para contexto: {context_database}",
            success_message=f"✅ {{count}} rutinas obtenidas para {context_label}: {context_database}",
            fetch_debug_message=f"🔍 Obteniendo lista de rutinas para {context_label}: {context_database}",
        )

    def get_ddl(self, tabla: str) -> str:
        """
        Obtiene el DDL de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            DDL de la tabla

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        context_label: str = self._get_query_context_label()
        cache_key: tuple[str, str] = self._cache_table_key(context_database, tabla)
        fetch_ddl = self._get_table_ddl_fetcher(context_database, tabla)

        return self._get_cached_text(
            cache_lookup=lambda: self.db_cache._ddl_cache.get(cache_key),
            cache_store=lambda ddl: self.db_cache._ddl_cache.__setitem__(cache_key, ddl),
            fetch_text=lambda: self._log_and_call(
                f"🔍 Obteniendo DDL para tabla {tabla} ({context_label}: {context_database})",
                fetch_ddl,
            ),
            cache_hit_message=f"♻️  Usando DDL en caché para tabla {tabla}",
            success_message=f"✅ DDL obtenido para tabla {tabla}",
        )

    def get_view_ddl(self, vista: str) -> str:
        """Obtiene el DDL de una vista.

        Args:
            vista: Nombre de la vista

        Returns:
            DDL de la vista

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        context_label: str = self._get_query_context_label()
        cache_key: tuple[str, str] = self._cache_table_key(context_database, vista)
        fetch_ddl = self._get_view_ddl_fetcher(context_database, vista)

        return self._get_cached_text(
            cache_lookup=lambda: self.db_cache._view_ddl_cache.get(cache_key),
            cache_store=lambda ddl: self.db_cache._view_ddl_cache.__setitem__(cache_key, ddl),
            fetch_text=lambda: self._log_and_call(
                f"🔍 Obteniendo DDL para vista {vista} ({context_label}: {context_database})",
                fetch_ddl,
            ),
            cache_hit_message=f"♻️  Usando DDL de vista en caché para {vista}",
            success_message=f"✅ DDL obtenido para vista {vista}",
        )

    def get_columns(self, tabla: str) -> Rows:
        """
        Obtiene las columnas de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            Lista de columnas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        context_label: str = self._get_query_context_label()
        cache_key: tuple[str, str] = self._cache_table_key(context_database, tabla)

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache.get_columns(cache_key),
            cache_store=lambda rows: self.db_cache.set_columns(cache_key, rows),
            fetch_rows=self._get_columns_fetcher(context_database, tabla),
            cache_hit_message=f"♻️  Usando columnas en caché para tabla {tabla}",
            success_message=f"✅ {{count}} columnas obtenidas de {tabla} ({context_label}: {context_database})",
            fetch_debug_message=f"🔍 Obteniendo columnas de {tabla} ({context_label}: {context_database})",
        )

    def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> Rows:
        """
        Obtiene los parámetros de una rutina.

        Args:
            rutina: Nombre de la rutina
            tipo_rutina: Tipo de rutina (PROCEDURE o FUNCTION)

        Returns:
            Lista de parámetros de la rutina

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        context_label: str = self._get_query_context_label()
        routine_type: str = str(tipo_rutina or "").upper()
        cache_key: tuple[str, str, str] = self._cache_routine_key(context_database, rutina, routine_type)

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache._routine_parameters_cache.get(cache_key),
            cache_store=lambda rows: self.db_cache._routine_parameters_cache.__setitem__(cache_key, list(rows)),
            fetch_rows=self._get_routine_parameters_fetcher(context_database, rutina, routine_type),
            cache_hit_message=f"♻️  Usando parámetros de rutina en caché para {routine_type} {rutina}",
            success_message=f"✅ {{count}} parámetros obtenidos de rutina {rutina} ({context_label}: {context_database})",
            fetch_debug_message=(
                f"🔍 Obteniendo parámetros de rutina {routine_type} {rutina} ({context_label}: {context_database})"
            ),
        )

    def get_routine_ddl(self, rutina: str, tipo_rutina: str) -> str:
        """
        Obtiene el DDL de una rutina.

        Args:
            rutina: Nombre de la rutina
            tipo_rutina: Tipo de rutina (PROCEDURE o FUNCTION)

        Returns:
            DDL de la rutina

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        context_label: str = self._get_query_context_label()
        routine_type: str = str(tipo_rutina or "").upper()
        cache_key: tuple[str, str, str] = self._cache_routine_key(context_database, rutina, routine_type)
        fetch_routine_ddl = self._get_routine_ddl_fetcher(context_database, rutina, routine_type)

        return self._get_cached_text(
            cache_lookup=lambda: self.db_cache._routine_ddl_cache.get(cache_key),
            cache_store=lambda ddl: self.db_cache._routine_ddl_cache.__setitem__(cache_key, ddl),
            fetch_text=lambda: self._log_and_call(
                f"🔍 Obteniendo DDL para rutina {routine_type} {rutina} ({context_label}: {context_database})",
                fetch_routine_ddl,
            ),
            cache_hit_message=f"♻️  Usando DDL de rutina en caché para {routine_type} {rutina}",
            success_message=f"✅ DDL obtenido para rutina {rutina}",
        )

    def _get_table_metadata_rows(
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
        """Template method interno para obtener metadatos tabulares cacheados."""
        context_database: str = self._get_query_context_database()
        context_label: str = self._get_query_context_label()
        cache_key: tuple[str, str] = self._cache_table_key(context_database, tabla)

        rows = self._get_cached_rows(
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

    def get_indices(self, tabla: str) -> Rows:
        """
        Obtiene los índices de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            Lista de índices

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        return self._get_table_metadata_rows(
            tabla=tabla,
            query_name="indices",
            error_message="Error obteniendo índices",
            cache_lookup=self.db_cache.get_indices,
            cache_store=self.db_cache.set_indices,
            cache_label="índices",
            success_label="índices",
        )

    def get_primary_keys(self, tabla: str) -> Rows:
        """
        Obtiene las claves primarias de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            Lista de claves primarias

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        return self._get_table_metadata_rows(
            tabla=tabla,
            query_name="claves_primarias",
            error_message="Error obteniendo claves primarias",
            cache_lookup=self.db_cache.get_primary_keys,
            cache_store=self.db_cache.set_primary_keys,
            cache_label="claves primarias",
            success_label="claves primarias",
        )

    def get_foreign_keys(self, tabla: str) -> Rows:
        """
        Obtiene las claves foráneas de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            Lista de claves foráneas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        return self._get_table_metadata_rows(
            tabla=tabla,
            query_name="claves_foraneas",
            error_message="Error obteniendo claves foráneas",
            cache_lookup=self.db_cache.get_foreign_keys,
            cache_store=self.db_cache.set_foreign_keys,
            cache_label="claves foráneas",
            success_label="claves foráneas",
        )

    def get_unique_constraints(self, tabla: str) -> Rows:
        """
        Obtiene las restricciones únicas de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            Lista de restricciones únicas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        return self._get_table_metadata_rows(
            tabla=tabla,
            query_name="claves_unicas",
            error_message="Error obteniendo restricciones únicas",
            cache_lookup=self.db_cache.get_unique_constraints,
            cache_store=self.db_cache.set_unique_constraints,
            cache_label="restricciones únicas",
            success_label="restricciones únicas",
        )

    def get_tables_normalized(self) -> list[NormalizedTableRow]:
        """Obtiene tablas en formato normalizado homogéneo."""
        rows: Rows = self.get_tables()
        return normalize_table_rows(rows)

    def get_columns_normalized(self, tabla: str) -> list[NormalizedColumnRow]:
        """Obtiene columnas en formato normalizado homogéneo."""
        rows: Rows = self.get_columns(tabla)
        return normalize_column_rows(rows)

    def get_database_version(self) -> str:
        """
        Obtiene la versión de la base de datos.

        Returns:
            String con la versión de la BD

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        self.logger.debug(f"🔍 Obteniendo versión de la BD ({self.db_type})")
        result = self._execute_metadata_one(
            "database_version",
            params={},
            error_message="Error obteniendo versión",
            table_name="database_version",
        )
        version: str = str(result[0]) if result else "Unknown"
        self.logger.info(f"✅ Versión obtenida: {version}")
        return version

    def _supports_columns_charset_collation(self) -> bool:
        """Indica si el motor expone metadata fiable de charset/collation por columna.

        Oracle solo expone collation por columna a partir de 12.2 y no en todas las
        instalaciones o privilegios. Hasta implementar una ruta versionada, se trata
        de forma conservadora como no soportado.
        """
        if self.db_type == "oracle":
            cached_support = getattr(self, "_oracle_column_collation_supported", None)
            if cached_support is not None:
                return supports_manager_columns_charset_collation(self.db_type, bool(cached_support))

            version_text = self.get_database_version()
            supported = oracle_supports_columns_charset_collation(version_text)
            self._oracle_column_collation_supported = supported
            return supports_manager_columns_charset_collation(self.db_type, supported)

        return supports_manager_columns_charset_collation(self.db_type)

    def get_database_charset_collation(self) -> dict[str, Any]:
        """
        Obtiene información de charset/collation de la base de datos.

        Returns:
            Diccionario con información de charset/collation según el motor

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        self.logger.debug(f"🔍 Obteniendo charset/collation de la BD ({self.db_type})")
        result = self._execute_metadata_one(
            "database_charset_collation",
            params={"database": context_database},
            error_message="Error obteniendo charset/collation",
            table_name="database_charset_collation",
        )
        info: dict[str, Any] = self._parse_charset_collation_result(result)
        self.logger.info(f"✅ Charset/Collation obtenido: {info}")
        return info

    def get_columns_charset_collation(self, tabla: str) -> list[tuple[str, str | None, str | None]]:
        """
        Obtiene información de charset/collation de las columnas de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            Lista de tuplas (column_name, charset, collation) para cada columna.
            Para BDs sin soporte charset/collation, retorna tuplas con valores None.

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)

        if not self._supports_columns_charset_collation():
            self.logger.debug(
                "ℹ️ Charset/collation por columna no soportado para %s; devolviendo lista vacía para %s",
                self.db_type,
                tabla,
            )
            empty_rows: list[tuple[str, str | None, str | None]] = []
            self.db_cache.set_columns_charset_collation(cache_key, empty_rows)
            return empty_rows

        return cast(
            list[tuple[str, str | None, str | None]],
            self._get_cached_rows(
                cache_lookup=lambda: self.db_cache.get_columns_charset_collation(cache_key),
                cache_store=lambda rows: self.db_cache.set_columns_charset_collation(cache_key, rows),
                fetch_rows=lambda: cast(
                    Rows,
                    [
                        self._parse_column_charset_collation_row(row)
                        for row in self._execute_metadata_many(
                            "columns_charset_collation",
                            params={"tabla": tabla, "database": context_database},
                            error_message="Error obteniendo charset/collation de columnas",
                            table_name=tabla,
                        )
                    ],
                ),
                cache_hit_message=f"♻️  Usando charset/collation en caché para tabla {tabla}",
                success_message=(
                    f"✅ Charset/Collation de {{count}} columnas obtenido ({context_label}: {context_database})"
                ),
                fetch_debug_message=(
                    f"🔍 Obteniendo charset/collation de columnas de {tabla} ({context_label}: {context_database})"
                ),
            ),
        )

    def get_storage_inventory(self, tablespace: str | None = None) -> dict[str, Any]:
        """Obtiene inventario de tamaño de ficheros/tablespaces según el motor.

        Args:
            tablespace: Nombre de tablespace (requerido en Oracle/PostgreSQL).

        Returns:
            Diccionario con claves explicitas por capacidad (`primary`,
            `temp_tablespaces`, `sqlite_file_summary`).
        """
        context_database = self._get_query_context_database()
        result = self._run_metadata_operation(
            action=lambda: self._storage_inventory_strategy.execute(self, context_database, tablespace),
            error_message="Error obteniendo inventario de almacenamiento",
        )
        return cast(dict[str, Any], result)

    # ==================== MÉTODOS ADICIONALES ====================

    def execute_query_many(self, query_name: str, timeout: float | None = None, **kwargs) -> Rows:
        """Ejecuta una consulta registrada y retorna múltiples filas."""
        result = self._execute_registered_query(
            query_name=query_name,
            params=kwargs,
            timeout=timeout,
            expect_one=False,
        )
        return cast(Rows, result)

    def execute_query_one(self, query_name: str, timeout: float | None = None, **kwargs) -> RowOrNone:
        """Ejecuta una consulta registrada y retorna una única fila o None."""
        result = self._execute_registered_query(
            query_name=query_name,
            params=kwargs,
            timeout=timeout,
            expect_one=True,
        )
        return cast(RowOrNone, result)

    def execute_custom_many(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Rows:
        """Ejecuta una consulta SQL personalizada y retorna múltiples filas."""
        result = self._execute_custom_sql(
            sql=sql,
            params=params,
            timeout=timeout,
            expect_one=False,
        )
        return cast(Rows, result)

    def execute_custom_one(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> RowOrNone:
        """Ejecuta una consulta SQL personalizada y retorna una única fila o None."""
        result = self._execute_custom_sql(
            sql=sql,
            params=params,
            timeout=timeout,
            expect_one=True,
        )
        return cast(RowOrNone, result)

    def resolve_query(self, query_name: str, **params) -> Any:
        """Resuelve una query registrada y devuelve SQL final + metadatos."""
        return self._query_catalog.resolver.resolve(query_name, params)

    def get_query_info(self) -> dict[str, Any]:
        """
        Obtiene información sobre las consultas disponibles

        Returns:
            Diccionario con información de las consultas
        """
        return self._query_catalog.get_query_info()

    def get_available_queries(self) -> list[str]:
        """
        Obtiene los nombres de las consultas disponibles

        Returns:
            Lista de nombres de consultas disponibles
        """
        return self._query_catalog.get_available_query_names()

    # ==================== MÉTODOS DE INFORMACIÓN DE TIPO BD ====================

    def get_database_type_info(self) -> dict[str, Any]:
        """
        Obtiene información completa del tipo de base de datos

        Returns:
            Diccionario con información del tipo de base de datos
        """
        return self.db_validator.get_db_type_info(self.db_type)

    def get_database_type_name(self) -> str:
        """
        Obtiene el nombre descriptivo del tipo de base de datos

        Returns:
            Nombre descriptivo del tipo de base de datos
        """
        return self.db_validator.get_db_type_name(self.db_type)

    def get_database_type_description(self) -> str:
        """
        Obtiene la descripción del tipo de base de datos

        Returns:
            Descripción del tipo de base de datos
        """
        return self.db_validator.get_db_type_description(self.db_type)

    def get_database_type_features(self) -> list[str]:
        """
        Obtiene las características soportadas del tipo de base de datos

        Returns:
            Lista de características soportadas
        """
        return self.db_validator.get_db_type_features(self.db_type)

    def get_database_type_driver_info(self) -> dict[str, Any]:
        """
        Obtiene información del driver del tipo de base de datos

        Returns:
            Diccionario con información del driver
        """
        return self.db_validator.get_db_type_driver_info(self.db_type)

    def get_required_params(self) -> list[str]:
        """
        Obtiene los parámetros requeridos para el tipo de base de datos

        Returns:
            Lista de parámetros requeridos
        """
        return self.db_validator.get_required_params(self.db_type)

    def get_optional_params(self) -> list[dict[str, Any]]:
        """
        Obtiene los parámetros opcionales para el tipo de base de datos

        Returns:
            Lista de parámetros opcionales con configuración
        """
        return self.db_validator.get_optional_params(self.db_type)

    def get_database_type_examples(self) -> dict[str, Any]:
        """
        Obtiene ejemplos de configuración para el tipo de base de datos

        Returns:
            Diccionario con ejemplos de configuración
        """
        return self.db_validator.get_db_type_examples(self.db_type)

    def get_default_port(self) -> int:
        """
        Obtiene el puerto por defecto del tipo de base de datos

        Returns:
            Puerto por defecto
        """
        return self.db_validator.get_db_type_default_port(self.db_type)

    def get_database_info(self) -> dict[str, Any]:
        """
        Obtiene información básica de la base de datos

        Returns:
            Diccionario con información de la conexión y base de datos
        """
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
            "available_queries": self.get_available_queries(),
            "connection_status": "connected" if self.connection else "disconnected",
        }

    def get_relationship_cache(self) -> "RelationshipMetadataCache":
        """Return centralized relationship metadata cache."""
        return self.relationship_cache

    # ==================== MÉTODO PARA SQLALCHEMY ====================

    def get_sqlalchemy_engine(self) -> "Engine":
        """
        Obtiene un Engine de SQLAlchemy basado en la configuración actual.

        Este método es útil para usar SyncDatabaseManager con librerías que requieren
        una Engine de SQLAlchemy, como bulk_crud.

        Returns:
            Engine de SQLAlchemy configurado con la base de datos actual.

        Raises:
            ImportError: Si SQLAlchemy no está instalado.
            DatabaseConnectionError: Si hay error creando la Engine.

        Ejemplo:
            db_mgr = SyncDatabaseManager("oracle", {"user": "hr", "password": "pass", "service_name": "ORCL"})
            engine = db_mgr.get_sqlalchemy_engine()

            # Usar con bulk_crud
            from util_bbdd.bulk import bulk_crud
            bcm = bulk_crud(engine)
        """
        return SQLAlchemyEngineFactory.create_engine(
            self.db_type,
            self.conn_params,
            self.database,
            sql_server_driver=self.sql_server_driver,
        )

    # ==================== CONTEXT MANAGER ====================

    def __enter__(self) -> "SyncDatabaseManager":
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cierra la conexión"""
        self.close(timeout_seconds=self._default_close_timeout_seconds, force=False)

    def __del__(self):
        """Destructor - cierra la conexión"""
        try:
            self.close(timeout_seconds=self._default_close_timeout_seconds, force=True)
        except Exception:
            pass  # No propagar excepciones desde destructor

    # ==================== MÉTODOS ESTÁTICOS PARA VALIDACIÓN ====================

    @staticmethod
    def get_supported_db_types() -> list[str]:
        """
        Obtiene la lista de tipos de bases de datos soportados

        Returns:
            Lista de tipos de bases de datos soportados
        """
        return get_supported_db_types()

    @staticmethod
    def is_db_type_supported(db_type: str) -> bool:
        """
        Verifica si un tipo de base de datos está soportado

        Args:
            db_type: Tipo de base de datos a verificar

        Returns:
            True si está soportado, False en caso contrario
        """
        validator = get_database_validator()
        return validator.is_db_type_supported(db_type)

    @staticmethod
    def validate_db_type_static(db_type: str) -> bool:
        """
        Método estático para validar un tipo de base de datos

        Args:
            db_type: Tipo de base de datos a validar

        Returns:
            True si es válido

        Raises:
            ValueError: Si el tipo no es válido
        """
        return validate_db_type(db_type)

    @staticmethod
    def get_db_type_info_static(db_type: str) -> dict[str, Any]:
        """
        Método estático para obtener información de un tipo de base de datos

        Args:
            db_type: Tipo de base de datos

        Returns:
            Información del tipo de base de datos
        """
        return get_db_type_info(db_type)
