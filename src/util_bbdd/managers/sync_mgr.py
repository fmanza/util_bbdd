"""
Módulo para manejo de operaciones de base de datos.
Soporta MariaDB, Oracle, PostgreSQL, SQLite, HSQLDB y SQL Server.
"""

import logging

from collections.abc import Callable, Collection
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from sqlalchemy.engine.base import Engine

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine

from .._core.exceptions import (
    ConnectionError,
    DatabaseConfigurationError,
    DatabaseOperationError,
    DriverError,
    QueryError,
    ValidationError,
)
from .._drivers import (
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
    Rows,
)
from ..metadata.catalog_registry import get_catalog_dialect
from ..metadata.model import ALL_KINDS, Kind, SchemaSnapshot
from ..metadata.source import CatalogSource
from ..query import DatabaseQueries
from ..results import RowOrNone
from ._catalog_executor import ManagerCatalogExecutor
from ._catalog_facade import SyncCatalogFacade
from ._manager_lifecycle import SyncConnectionLifecycleManager
from ._manager_lifecycle_sync import SyncLifecycleManager
from ._manager_session import SyncSessionManager
from ._manager_shared_mixin import DatabaseManagerSharedMixin


class SyncDatabaseManager(SyncCatalogFacade, DatabaseManagerSharedMixin):
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

        # Inicializar validador de tipos (lazy loading)
        self._db_validator: DatabaseTypeValidator | None = None

        # Normalizar tipo de BD
        normalized_db_type: str = db_type.lower()
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

        except ValidationError:
            self.logger.error("❌ Error de validación de parámetros")
            raise
        except DriverError:
            self.logger.error("❌ Error en disponibilidad de driver")
            raise
        except ConnectionError:
            self.logger.error("❌ Error al conectar a la base de datos")
            raise
        except ValueError as e:
            self.logger.error(f"❌ Error de validación: {e}")
            raise ValidationError(str(e), db_type=self.db_type) from e
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
            filtered: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                db_type,
                self.conn_params,
                driver=self.sql_server_driver if db_type == "sqlserver" else None,
            )
            self.logger.debug(f"✅ Parámetros filtrados para {db_type}: {len(filtered)} parámetros válidos")
            return filtered
        except Exception as e:
            self.logger.error(f"❌ Error filtrando parámetros de conexión: {e}")
            raise ValidationError(f"Error filtrando parámetros: {str(e)}", db_type=db_type, details=str(e)) from e

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
        except ConnectionError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error en conexión: {e}")
            raise ConnectionError(
                f"Error al conectar a {self.db_type}: {str(e)}", db_type=self.db_type, details=str(e)
            ) from e

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
        effective_timeout: float | None = (
            self._default_close_timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        pool: ConnectionPoolProtocol | None = self.pool_connection
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
            SyncConnectionLifecycleManager(self.db_type, self.logger).close_resources(
                pool_connection=pool,
                cursor=cursor,
                connection=connection,
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
        executor: SyncQueryExecutor = self._get_sync_query_executor()
        mode: Literal["one"] | Literal["many"] = "one" if expect_one else "many"
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
        executor: SyncQueryExecutor = self._get_sync_query_executor()
        mode: Literal["one"] | Literal["many"] = "one" if expect_one else "many"
        self.logger.debug(f"📝 Ejecutando consulta SQL personalizada ({mode})")
        execute = executor.execute_custom_one if expect_one else executor.execute_custom_many
        result = self._run_manager_operation(
            action=lambda: execute(sql=sql, params=params, timeout=timeout),
            error_message="Error ejecutando consulta SQL",
            operation="EXECUTE",
        )
        self.logger.info("✅ Consulta SQL personalizada ejecutada exitosamente")
        return cast(RowOrNone | Rows, result)

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
        """
        Ejecuta una consulta SQL personalizada y retorna múltiples filas.

        Args:
            sql: Consulta SQL a ejecutar.
            params: Diccionario de parámetros SQL (opcional).
            timeout: Timeout en segundos (opcional).

        Returns:
            Lista de filas resultantes.

        Raises:
            QueryError: Si hay error en la ejecución de la query.

        Example:
            Ejecutar una query personalizada:

            >>> from util_bbdd import SyncDatabaseManager
            >>> manager = SyncDatabaseManager(
            ...     db_type="postgresql",
            ...     conn_params={
            ...         "host": "localhost",
            ...         "port": 5432,
            ...         "user": "postgres",
            ...         "password": "secret",
            ...         "database": "mydb"
            ...     }
            ... )
            >>> # Query simple sin parámetros
            >>> result = manager.execute_custom_many("SELECT * FROM users LIMIT 5")
            >>> print(f"Encontradas {len(result)} filas")
            >>> # Query con parámetros
            >>> result = manager.execute_custom_many(
            ...     "SELECT * FROM users WHERE age > :age",
            ...     params={"age": 18}
            ... )
            >>> manager.close()
        """
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
        """
        Ejecuta una consulta SQL personalizada y retorna una única fila o None.

        Args:
            sql: Consulta SQL a ejecutar.
            params: Diccionario de parámetros SQL (opcional).
            timeout: Timeout en segundos (opcional).

        Returns:
            Una tupla (fila) si encuentra resultado, None si no hay filas.

        Raises:
            QueryError: Si hay error en la ejecución de la query.

        Example:
            Obtener un registro único:

            >>> from util_bbdd import SyncDatabaseManager
            >>> manager = SyncDatabaseManager(
            ...     db_type="postgresql",
            ...     conn_params={
            ...         "host": "localhost",
            ...         "port": 5432,
            ...         "user": "postgres",
            ...         "password": "secret",
            ...         "database": "mydb"
            ...     }
            ... )
            >>> # Buscar usuario por ID
            >>> user = manager.execute_custom_one(
            ...     "SELECT id, name, email FROM users WHERE id = :id",
            ...     params={"id": 123}
            ... )
            >>> if user:
            ...     print(f"Usuario encontrado: {user[1]} ({user[2]})")
            ... else:
            ...     print("Usuario no encontrado")
            >>> manager.close()
        """
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

    @property
    def metadata_source(self) -> CatalogSource:
        """Lectura del catálogo por lotes sobre las conexiones de este manager (ADR-003).

        Una consulta por schema y tipo de objeto con el driver nativo, en la caché del manager (``clear_cache()`` la
        invalida). Ver :meth:`get_schema_metadata`.
        """
        source: CatalogSource | None = self.__dict__.get("_catalog_source")
        if source is None:
            source = CatalogSource(
                get_catalog_dialect(self.db_type),
                ManagerCatalogExecutor(
                    lambda: self._get_sync_query_executor().connection_provider(),
                    lambda conn: self._get_sync_query_executor().connection_releaser(conn),
                    connection_params=self.conn_params,
                ),
                source_id=self._catalog_source_id(),
                cache=self._catalog_cache(),
                default_schema=self._catalog_default_schema(),
            )
            self.__dict__["_catalog_source"] = source
        return source

    def get_schema_metadata(
        self,
        schema: str | None = None,
        *,
        kinds: Collection[Kind] = ALL_KINDS,
        tables: Collection[str] | None = None,
    ) -> SchemaSnapshot:
        """Metadatos de un schema con una consulta por tipo de objeto (tablas, columnas, claves, índices, routines…).

        Sustituye a recorrer el schema con ``get_columns(t)``, ``get_indices(t)``…: con 500 tablas en PostgreSQL,
        12 consultas en lugar de 2503 (ADR-003).

        Args:
            schema: Schema, owner o base de datos; por defecto el contexto de metadatos del manager (``main`` en SQLite).
            kinds: Tipos de objeto a leer; pedir después uno no leído lanza ``KindNotLoadedError``.
            tables: Limita la lectura a estas tablas (hasta 50; con más, se lee el schema completo).

        Returns:
            ``SchemaSnapshot`` inmutable con modelos neutros (``TableMeta``, ``ColumnMeta``, ``ForeignKeyMeta``…).

        Example:
            >>> snapshot = manager.get_schema_metadata(kinds={Kind.TABLES, Kind.FOREIGN_KEYS})
            >>> [(fk.table, fk.ref_table) for fk in snapshot.all_foreign_keys()]
        """
        return self.metadata_source.snapshot(schema, kinds=kinds, tables=tables)

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
        validator: DatabaseTypeValidator = get_database_validator()
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
