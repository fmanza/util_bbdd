"""
Módulo para manejo de operaciones de base de datos
Soporta MariaDB, Oracle, PostgreSQL, HSQLDB y SQL Server
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy.engine.base import Engine

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine

from .connection.connect_factory import ConnectFactory
from .connection.connection_params_manager import ConnectionParamsManager
from .connection.pool_protocol import ConnectionPoolProtocol
from .database_exceptions import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseDriverError,
    DatabaseOperationError,
    DatabaseValidationError,
)
from .database_queries import DatabaseQueries, DatabaseQueryExecutor
from .database_type_validator import DatabaseTypeValidator
from .driver_validator import DriverValidator
from .factory.pool_factory import PoolFactory
from .factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory
from .metadata_cache import DatabaseMetadataCache, RelationshipMetadataCache


class DatabaseManager:
    """
    Clase para manejar conexiones y operaciones de base de datos.

    Soporta logging y manejo de excepciones propias.
    Bases de datos soportadas: MariaDB, Oracle, PostgreSQL, HSQLDB, SQL Server
    """

    _QUERY_EXECUTOR_NOT_INITIALIZED = "Ejecutor de consultas no inicializado. Verifique la conexión a la base de datos."

    def _build_query_executor(
        self,
        connection_provider: Callable[[], Any],
        connection_releaser: Callable[[Any], None],
    ) -> None:
        """Inicializa un DatabaseQueryExecutor stateless con provider/releaser.

        Args:
            connection_provider: Función que obtiene una conexión para cada operación.
            connection_releaser: Función que libera/devolver la conexión al finalizar.
        """
        self.query_executor = DatabaseQueryExecutor(
            connection=None,
            cursor=None,
            queries=self.db_queries,
            connection_provider=connection_provider,
            connection_releaser=connection_releaser,
        )
        self.logger.debug("✅ Query executor stateless inicializado")

    def __init__(
        self,
        db_type: str,
        conn_params: dict,
        queries_file: Path | None = None,
        use_pool: bool = True,
    ):
        """
        Inicializa el gestor de base de datos con soporte de pool de conexiones

        Args:
            db_type: Tipo de base de datos ('mariadb', 'oracle', 'postgresql', 'hsqldb', 'sqlserver')
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
        self.logger.info(f"🔧 Inicializando DatabaseManager para {db_type.upper()}")

        # Inicializar la conexión como None
        self._connection: Any = None
        self.cursor: Any = None
        self.query_executor: DatabaseQueryExecutor | None = None

        # Inicializar cachés centralizados (composición jerárquica)
        self.db_cache: DatabaseMetadataCache = DatabaseMetadataCache()
        self.relationship_cache: RelationshipMetadataCache = RelationshipMetadataCache(db_cache=self.db_cache)
        self.logger.debug("✅ Cachés centralizados [DatabaseMetadataCache + RelationshipMetadataCache] inicializados")

        # Inicializar validador de tipos (lazy loading)
        self._db_validator: DatabaseTypeValidator | None = None

        # Pool de conexiones
        self.use_pool: bool = use_pool
        self.pool_connection: ConnectionPoolProtocol | None = None

        try:
            # Validar y normalizar tipo de base de datos
            self.db_validator.validate_db_type(db_type)
            self.db_type: str = db_type.lower()
            self.logger.debug(f"✅ Tipo de BD validado: {self.db_type}")

            # Construir y validar parámetros en una única capa centralizada.
            self.conn_params = ConnectionParamsManager.prepare_and_validate(
                self.db_type,
                conn_params,
                self.db_validator,
            )

            # Extraer database desde conn_params
            self.database: str = self.conn_params.get("database", "")
            self.sql_server_driver: str = "pymssql"  # Valor por defecto, se configurará en verificación de drivers

            self.logger.debug("✅ Parámetros de conexión validados")

            # Verificar disponibilidad de drivers y configurar sql_server_driver si es necesario
            if self.db_type == "sqlserver":
                self.sql_server_driver = DriverValidator.check_driver_availability(self.db_type, self.conn_params)
            else:
                DriverValidator.check_driver_availability(self.db_type, self.conn_params)

            # Inicializar gestor de consultas
            queries_path: Path | None = queries_file if queries_file else None
            self.db_queries = DatabaseQueries(self.db_type, queries_path)
            self.logger.debug("✅ Gestor de consultas inicializado")

            # Determinar si usar pool
            if self.use_pool and self._supports_pool():
                self._init_pool()
            else:
                if self.use_pool and not self._supports_pool():
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
            self.logger.error(f"❌ Error inesperado inicializando DatabaseManager: {e}")
            raise DatabaseConfigurationError(f"Error al inicializar DatabaseManager: {str(e)}", self.db_type, str(e)) from e

    @property
    def db_validator(self) -> DatabaseTypeValidator:
        """
        Propiedad para acceso lazy loading al validador de tipos de BD.

        Inicializa la instancia de DatabaseTypeValidator solo cuando es necesario,
        mejorando el rendimiento de inicialización de DatabaseManager.

        Returns:
            Instancia de DatabaseTypeValidator
        """
        if self._db_validator is None:
            self._db_validator = DatabaseTypeValidator()
            self.logger.debug("✅ DatabaseTypeValidator inicializado (lazy loading)")
        return self._db_validator

    def _filter_connection_params(self, db_type: str) -> dict:
        """
        Filtra los parámetros de conexión válidos para el tipo de base de datos especificado.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Diccionario con parámetros validados

        Raises:
            DatabaseValidationError: Si hay error en la validación
        """
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

    def _supports_pool(self) -> bool:
        """
        Verifica si el tipo de BD soporta pool de conexiones.

        Returns:
            True si soporta pool, False en caso contrario
        """
        # HSQLDB no soporta pool directo
        return self.db_type not in ["hsqldb"]

    def _init_pool(self) -> None:
        """Inicializa pool de conexiones según tipo de BD.

        Raises:
            ValueError: Si el pool no está soportado para el tipo de BD.
            Exception: Si la creación del pool falla.
        """
        try:
            self.pool_connection = PoolFactory.create_pool(self.db_type, self.conn_params)
            self.logger.info(f"🔗 Pool habilitado para {self.db_type} (size: {self.conn_params.get('pool_size', 5)})")

            # Verificar que el pool puede entregar conexiones
            test_conn = self.pool_connection.get_connection()
            self.pool_connection.close_connection(test_conn)
            self.logger.debug(f"✅ Conexión de prueba obtenida/devuelta al pool para {self.db_type}")

            # Inicializar ejecutor stateless (cada operación obtiene/libera conexión)
            self._build_query_executor(
                connection_provider=lambda: self.get_connection(),
                connection_releaser=lambda conn: self.close_connection(conn),
            )

        except ValueError as e:
            self.logger.warning(f"⚠️ Pool no disponible: {e}. Usando conexión única.")
            self.use_pool = False
            self._connect()
        except Exception as e:
            self.logger.error(f"❌ Error inicializando pool: {e}")
            raise

    def _connect(self) -> None:
        """
        Establece una conexión a la base de datos

        Raises:
            DatabaseConnectionError: Si hay error de conexión
        """
        try:
            self.logger.info(f"🔗 Estableciendo conexión a {self.db_type}")

            # Filtrar parámetros válidos para este tipo de BD
            valid_params = self._filter_connection_params(self.db_type)

            # Crear conexión usando la factory
            self._connection = ConnectFactory.create_connection(
                self.db_type,
                valid_params,
                db_validator=self.db_validator,
                sql_server_driver=self.sql_server_driver,
            )
            self.logger.info("✅ Conexión establecida exitosamente")

            # Inicializar ejecutor stateless en conexión única
            self._build_query_executor(
                connection_provider=lambda: self._connection,
                connection_releaser=lambda _conn: None,
            )
        except DatabaseConnectionError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error en conexión: {e}")
            raise DatabaseConnectionError(f"Error al conectar a {self.db_type}: {str(e)}", self.db_type, str(e)) from e

    @property
    def connection(self) -> Any:
        """
        Obtiene la conexión a la base de datos

        Returns:
            Conexión actual
        """
        return self._connection

    @connection.setter
    def connection(self, conn: Any) -> None:
        """
        Establece la conexión a la base de datos (solo para conexiones directas)

        Args:
            conn: Conexión a establecer
        """
        self._connection = conn

    def get_connection(self) -> Any:
        """Obtiene conexión del pool o conexión única.

        Returns:
            Conexión a la base de datos.

        Raises:
            Exception: Si no hay conexiones disponibles.
        """
        if self.pool_connection:
            try:
                conn = self.pool_connection.get_connection()
            except TimeoutError as e:
                raise DatabaseOperationError(
                    f"Timeout obteniendo conexión del pool para {self.db_type}: {e}",
                    operation="CONNECT",
                    db_type=self.db_type,
                ) from e
            except RuntimeError as e:
                raise DatabaseOperationError(
                    f"Pool de conexiones no disponible para {self.db_type}: {e}",
                    operation="CONNECT",
                    db_type=self.db_type,
                ) from e
            except Exception as e:
                raise DatabaseOperationError(
                    f"Error obteniendo conexión del pool para {self.db_type}: {e}",
                    operation="CONNECT",
                    db_type=self.db_type,
                ) from e

            if conn is None:
                raise DatabaseOperationError(
                    f"Pool de conexiones devolvió conexión nula para {self.db_type}",
                    operation="CONNECT",
                    db_type=self.db_type,
                )

            self.logger.debug("📦 Conexión obtenida del pool")
            return conn

        if self._connection is None:
            raise DatabaseOperationError("No hay conexión disponible", db_type=self.db_type)

        return self._connection

    def close_connection(self, connection: Any | None = None) -> None:
        """Devuelve conexión al pool o cierra conexión única.

        Args:
            connection: Conexión a devolver (si es None y hay pool activo, ignora).
        """
        if connection is None:
            return

        try:
            if self.pool_connection:
                self.pool_connection.close_connection(connection)
                self.logger.debug("📦 Conexión devuelta al pool")
            else:
                connection.close()
                self.logger.debug("🔌 Conexión cerrada")
        except RuntimeError as e:
            self.logger.warning(f"⚠️ Pool no disponible al devolver conexión: {e}")
        except Exception as e:
            self.logger.warning(f"⚠️ Error cerrando conexión: {e}")

    def close(self) -> None:
        """
        Cierra la conexión a la base de datos y libera recursos del pool

        Logs:
            - ✅ Si la operación es exitosa
            - ❌ Si hay errores
        """
        try:
            if self.pool_connection:
                try:
                    self.pool_connection.close()
                    self.logger.info("🔗 Pool liberado y cerrado")
                except Exception as e:
                    self.logger.warning(f"⚠️  Error cerrando pool: {e}")
                finally:
                    self.pool_connection = None

            if self.cursor:
                try:
                    self.cursor.close()
                    self.logger.debug(f"✅ Cursor cerrado para {self.db_type}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Error cerrando cursor: {e}")

            if self._connection:
                try:
                    self._connection.close()
                    self.logger.info(f"✅ Conexión cerrada para {self.db_type}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Error cerrando conexión: {e}")
                finally:
                    self._connection = None

            self.logger.info("✅ DatabaseManager cerrado")
        except Exception as e:
            self.logger.error(f"❌ Error inesperado cerrando conexión: {e}")

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

    def _clear_context_cache(self, context: str) -> None:
        """Limpia caché para un contexto/schema específico."""
        self.db_cache._tables_cache.pop(context, None)
        self.db_cache._views_cache.pop(context, None)
        self.db_cache._routines_cache.pop(context, None)

        def _clear_tuple_cache_by_context(cache: dict[tuple, Any], target_context: str) -> None:
            keys_to_remove: list[tuple] = [key for key in cache if key and str(key[0]) == target_context]
            for key in keys_to_remove:
                cache.pop(key, None)

        _clear_tuple_cache_by_context(self.db_cache._primary_keys_cache, context)
        _clear_tuple_cache_by_context(self.db_cache._indices_cache, context)
        _clear_tuple_cache_by_context(self.db_cache._foreign_keys_cache, context)
        _clear_tuple_cache_by_context(self.db_cache._unique_constraints_cache, context)
        _clear_tuple_cache_by_context(self.db_cache._columns_cache, context)
        _clear_tuple_cache_by_context(self.db_cache._ddl_cache, context)
        _clear_tuple_cache_by_context(self.db_cache._view_ddl_cache, context)
        _clear_tuple_cache_by_context(self.db_cache._routine_parameters_cache, context)
        _clear_tuple_cache_by_context(self.db_cache._routine_ddl_cache, context)
        self.logger.info(f"🧹 Caché invalidada para contexto: {context}")

    def clear_cache(
        self,
        context_database: str | None = None,
        table: str | None = None,
        routine: str | None = None,
        routine_type: str | None = None,
    ) -> None:
        """Limpia cachés de metadatos (global o selectiva).

        Args:
            context_database: Contexto de esquema/base a invalidar. Si es None,
                se usa el contexto actual para invalidaciones selectivas.
            table: Nombre de tabla/vista para invalidación selectiva.
            routine: Nombre de rutina para invalidación selectiva.
            routine_type: Tipo de rutina (PROCEDURE/FUNCTION). Si no se indica,
                elimina todas las variantes de tipo para la rutina.

        Notes:
            - Sin argumentos, limpia completamente todas las cachés (incluidas relaciones).
            - Con argumentos, limpia únicamente entradas relacionadas.
            - Sincroniza limpieza entre cachés BD y cachés de relaciones.
        """
        # Limpieza global si no hay parámetros
        if context_database is None and table is None and routine is None and routine_type is None:
            self._clear_all_caches()
            return

        # Resolver contexto
        resolved_context: str = str(
            context_database if context_database is not None else self._get_query_context_database() or ""
        )

        # Limpieza por tabla
        if table:
            self._clear_table_cache(resolved_context, str(table))

        # Limpieza por rutina
        if routine:
            self._clear_routine_cache(resolved_context, str(routine), str(routine_type) if routine_type else None)

        # Limpieza por contexto
        if not table and not routine:
            self._clear_context_cache(resolved_context)

    # ==================== MÉTODOS DE CONSULTA (DELEGADOS) ====================

    def _verify_executor_initialized(self) -> None:
        """
        Verifica que el ejecutor de consultas esté inicializado

        Raises:
            DatabaseOperationError: Si el ejecutor no está inicializado
        """
        if not self.query_executor:
            self.logger.error("❌ Ejecutor de consultas no inicializado")
            raise DatabaseOperationError(self._QUERY_EXECUTOR_NOT_INITIALIZED, db_type=self.db_type)

    def _get_query_context_database(self) -> str:
        """Obtiene el contexto de esquema/base para consultas de metadatos.

        Returns:
            Identificador de esquema/base a usar en queries.

        Notes:
            - En Oracle se prioriza el usuario de conexión (owner/schema).
            - En PostgreSQL/HSQLDB/SQL Server se permite `schema` explícito
              (si no viene, mantiene compatibilidad con `self.database`).
        """
        context_database: str = (self.database or "").strip()

        if self.db_type == "oracle":
            oracle_user: str = str(self.conn_params.get("user", "")).strip()
            context_database = oracle_user or context_database
        elif self.db_type == "postgresql":
            explicit_schema: str = str(self.conn_params.get("schema", "")).strip()
            context_database = explicit_schema or context_database or "public"
        elif self.db_type == "hsqldb":
            explicit_schema: str = str(self.conn_params.get("schema", "")).strip()
            context_database = explicit_schema or context_database or "PUBLIC"
        elif self.db_type == "sqlserver":
            explicit_schema: str = str(self.conn_params.get("schema", "")).strip()
            context_database = explicit_schema or context_database or "dbo"

        return context_database

    def _get_query_context_label(self) -> str:
        """Obtiene etiqueta descriptiva del contexto de consultas de metadatos."""
        return "owner/schema" if self.db_type == "oracle" else "database"

    def get_query_context_database(self) -> str:
        """Expone el contexto de metadatos (schema/database) para consumidores externos.

        Returns:
            Contexto efectivo usado por las consultas de metadatos.
        """
        return self._get_query_context_database()

    def get_tables(self) -> list:
        """
        Obtiene la lista de tablas de la base de datos.

        Returns:
            Lista de tablas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: str = str(context_database or "")

            cached_tables = self.db_cache._tables_cache.get(cache_key)
            if cached_tables is not None:
                self.logger.debug(f"♻️  Usando tablas en caché para contexto: {context_database}")
                return list(cached_tables)

            context_label: str = self._get_query_context_label()
            self.logger.debug(f"🔍 Obteniendo lista de tablas para {context_label}: {context_database}")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            tables = executor.get_tables(context_database)
            self.db_cache._tables_cache[cache_key] = list(tables)
            self.logger.info(f"✅ {len(tables)} tablas obtenidas")
            return tables
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo tablas: {e}")
            raise DatabaseOperationError(f"Error obteniendo tablas: {str(e)}", "SELECT", db_type=self.db_type) from e

    def get_views(self) -> list:
        """
        Obtiene la lista de vistas de la base de datos.

        Returns:
            Lista de vistas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: str = str(context_database or "")

            cached_views = self.db_cache._views_cache.get(cache_key)
            if cached_views is not None:
                self.logger.debug(f"♻️  Usando vistas en caché para contexto: {context_database}")
                return list(cached_views)

            context_label: str = self._get_query_context_label()
            self.logger.debug(f"🔍 Obteniendo lista de vistas para {context_label}: {context_database}")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            views = executor.get_views(context_database)
            self.db_cache._views_cache[cache_key] = list(views)
            self.logger.info(f"✅ {len(views)} vistas obtenidas")
            return views
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo vistas: {e}")
            raise DatabaseOperationError(f"Error obteniendo vistas: {str(e)}", "SELECT", db_type=self.db_type) from e

    def get_routines(self) -> list:
        """
        Obtiene la lista de rutinas (procedures y funciones) de la base de datos.

        Returns:
            Lista de rutinas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: str = str(context_database or "")

            cached_routines = self.db_cache._routines_cache.get(cache_key)
            if cached_routines is not None:
                self.logger.debug(f"♻️  Usando rutinas en caché para contexto: {context_database}")
                return list(cached_routines)

            context_label: str = self._get_query_context_label()
            self.logger.debug(f"🔍 Obteniendo lista de rutinas para {context_label}: {context_database}")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            routines = executor.get_routines(context_database)
            self.db_cache._routines_cache[cache_key] = list(routines)
            self.logger.info(f"✅ {len(routines)} rutinas obtenidas")
            return routines
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo rutinas: {e}")
            raise DatabaseOperationError(f"Error obteniendo rutinas: {str(e)}", "SELECT", db_type=self.db_type) from e

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
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: tuple[str, str] = (str(context_database or ""), str(tabla or ""))

            cached_ddl = self.db_cache._ddl_cache.get(cache_key)
            if cached_ddl is not None:
                self.logger.debug(f"♻️  Usando DDL en caché para tabla {tabla}")
                return cached_ddl

            context_label: str = self._get_query_context_label()
            self.logger.debug(f"🔍 Obteniendo DDL para tabla {tabla} ({context_label}: {context_database})")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            ddl: str = executor.get_ddl(tabla, context_database)
            self.db_cache._ddl_cache[cache_key] = ddl
            self.logger.info(f"✅ DDL obtenido para tabla {tabla}")
            return ddl
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo DDL para {tabla}: {e}")
            raise DatabaseOperationError(f"Error obteniendo DDL: {str(e)}", "SELECT", tabla, self.db_type) from e

    def get_view_ddl(self, vista: str) -> str:
        """Obtiene el DDL de una vista.

        Args:
            vista: Nombre de la vista

        Returns:
            DDL de la vista

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: tuple[str, str] = (str(context_database or ""), str(vista or ""))

            cached_ddl = self.db_cache._view_ddl_cache.get(cache_key)
            if cached_ddl is not None:
                self.logger.debug(f"♻️  Usando DDL de vista en caché para {vista}")
                return cached_ddl

            context_label: str = self._get_query_context_label()
            self.logger.debug(f"🔍 Obteniendo DDL para vista {vista} ({context_label}: {context_database})")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            ddl: str = executor.get_view_ddl(vista, context_database)
            self.db_cache._view_ddl_cache[cache_key] = ddl
            self.logger.info(f"✅ DDL obtenido para vista {vista}")
            return ddl
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo DDL para vista {vista}: {e}")
            raise DatabaseOperationError(f"Error obteniendo DDL de vista: {str(e)}", "SELECT", vista, self.db_type) from e

    def get_columns(self, tabla: str) -> list:
        """
        Obtiene las columnas de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            Lista de columnas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: tuple[str, str] = (str(context_database or ""), str(tabla or ""))

            cached_columns = self.db_cache._columns_cache.get(cache_key)
            if cached_columns is not None:
                self.logger.debug(f"♻️  Usando columnas en caché para tabla {tabla}")
                return list(cached_columns)

            context_label: str = self._get_query_context_label()
            self.logger.debug(f"🔍 Obteniendo columnas de {tabla} ({context_label}: {context_database})")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            columns = executor.get_columns(context_database, tabla)
            self.db_cache._columns_cache[cache_key] = list(columns)
            self.logger.info(f"✅ {len(columns)} columnas obtenidas de {tabla}")
            return columns
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo columnas de {tabla}: {e}")
            raise DatabaseOperationError(f"Error obteniendo columnas: {str(e)}", "SELECT", tabla, self.db_type) from e

    def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> list:
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
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: tuple[str, str, str] = (
                str(context_database or ""),
                str(rutina or ""),
                str(tipo_rutina or "").upper(),
            )

            cached_params = self.db_cache._routine_parameters_cache.get(cache_key)
            if cached_params is not None:
                self.logger.debug(f"♻️  Usando parámetros de rutina en caché para {tipo_rutina} {rutina}")
                return list(cached_params)

            context_label: str = self._get_query_context_label()
            self.logger.debug(
                f"🔍 Obteniendo parámetros de rutina {tipo_rutina} {rutina} ({context_label}: {context_database})"
            )
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            parameters = executor.get_routine_parameters(context_database, rutina, tipo_rutina)
            self.db_cache._routine_parameters_cache[cache_key] = list(parameters)
            self.logger.info(f"✅ {len(parameters)} parámetros obtenidos de rutina {rutina}")
            return parameters
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo parámetros de rutina {rutina}: {e}")
            raise DatabaseOperationError(f"Error obteniendo parámetros de rutina: {str(e)}", "SELECT", rutina, self.db_type) from e

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
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: tuple[str, str, str] = (
                str(context_database or ""),
                str(rutina or ""),
                str(tipo_rutina or "").upper(),
            )

            cached_ddl = self.db_cache._routine_ddl_cache.get(cache_key)
            if cached_ddl is not None:
                self.logger.debug(f"♻️  Usando DDL de rutina en caché para {tipo_rutina} {rutina}")
                return cached_ddl

            context_label: str = self._get_query_context_label()
            self.logger.debug(
                f"🔍 Obteniendo DDL para rutina {tipo_rutina} {rutina} ({context_label}: {context_database})"
            )
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            ddl: str = executor.get_routine_ddl(rutina, tipo_rutina, context_database)
            self.db_cache._routine_ddl_cache[cache_key] = ddl
            self.logger.info(f"✅ DDL obtenido para rutina {rutina}")
            return ddl
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo DDL de rutina {rutina}: {e}")
            raise DatabaseOperationError(f"Error obteniendo DDL de rutina: {str(e)}", "SELECT", rutina, self.db_type) from e

    def get_indices(self, tabla: str) -> list:
        """
        Obtiene los índices de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            Lista de índices

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: tuple[str, str] = (str(context_database or ""), str(tabla or ""))

            cached_indices = self.db_cache._indices_cache.get(cache_key)
            if cached_indices is not None:
                self.logger.debug(f"♻️  Usando índices en caché para {tabla}")
                return list(cached_indices)

            context_label: str = self._get_query_context_label()
            self.logger.debug(f"🔍 Obteniendo índices de {tabla} ({context_label}: {context_database})")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            indices = executor.get_indices(tabla, context_database)
            self.db_cache._indices_cache[cache_key] = list(indices)
            self.logger.info(f"✅ {len(indices)} índices obtenidos de {tabla}")
            return indices
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo índices de {tabla}: {e}")
            raise DatabaseOperationError(f"Error obteniendo índices: {str(e)}", "SELECT", tabla, self.db_type) from e

    def get_primary_keys(self, tabla: str) -> list:
        """
        Obtiene las claves primarias de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            Lista de claves primarias

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: tuple[str, str] = (str(context_database or ""), str(tabla or ""))

            cached_pks = self.db_cache.get_primary_keys(cache_key)
            if cached_pks is not None:
                self.logger.debug(f"♻️  Usando claves primarias en caché para {tabla}")
                return list(cached_pks)

            context_label: str = self._get_query_context_label()
            self.logger.debug(f"🔍 Obteniendo claves primarias de {tabla} ({context_label}: {context_database})")
            assert self.query_executor is not None
            executor = self.query_executor
            pks = executor.get_primary_keys(tabla, context_database)
            self.db_cache.set_primary_keys(cache_key, pks)
            self.logger.info(f"✅ {len(pks)} claves primarias obtenidas de {tabla}")
            return pks
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo claves primarias de {tabla}: {e}")
            raise DatabaseOperationError(f"Error obteniendo claves primarias: {str(e)}", "SELECT", tabla, self.db_type) from e

    def get_foreign_keys(self, tabla: str) -> list:
        """
        Obtiene las claves foráneas de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            Lista de claves foráneas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: tuple[str, str] = (str(context_database or ""), str(tabla or ""))

            cached_fks = self.db_cache.get_foreign_keys(cache_key)
            if cached_fks is not None:
                self.logger.debug(f"♻️  Usando claves foráneas en caché para {tabla}")
                return list(cached_fks)

            context_label: str = self._get_query_context_label()
            self.logger.debug(f"🔍 Obteniendo claves foráneas de {tabla} ({context_label}: {context_database})")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            fks = executor.get_foreign_keys(tabla, context_database)
            self.db_cache.set_foreign_keys(cache_key, fks)
            self.logger.info(f"✅ {len(fks)} claves foráneas obtenidas de {tabla}")
            return fks
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo claves foráneas de {tabla}: {e}")
            raise DatabaseOperationError(f"Error obteniendo claves foráneas: {str(e)}", "SELECT", tabla, self.db_type) from e

    def get_unique_constraints(self, tabla: str) -> list:
        """
        Obtiene las restricciones únicas de una tabla.

        Args:
            tabla: Nombre de la tabla

        Returns:
            Lista de restricciones únicas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: tuple[str, str] = (str(context_database or ""), str(tabla or ""))

            cached_ucs = self.db_cache.get_unique_constraints(cache_key)
            if cached_ucs is not None:
                self.logger.debug(f"♻️  Usando restricciones únicas en caché para {tabla}")
                return list(cached_ucs)

            context_label: str = self._get_query_context_label()
            self.logger.debug(f"🔍 Obteniendo restricciones únicas de {tabla} ({context_label}: {context_database})")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            ucs = executor.get_unique_constraints(tabla, context_database)
            self.db_cache.set_unique_constraints(cache_key, ucs)
            self.logger.info(f"✅ {len(ucs)} restricciones únicas obtenidas de {tabla}")
            return ucs
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo restricciones únicas de {tabla}: {e}")
            raise DatabaseOperationError(f"Error obteniendo restricciones únicas: {str(e)}", "SELECT", tabla, self.db_type) from e

    def get_database_version(self) -> str:
        """
        Obtiene la versión de la base de datos.

        Returns:
            String con la versión de la BD

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            self.logger.debug(f"🔍 Obteniendo versión de la BD ({self.db_type})")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            result = executor.execute_query("database_version", fetch_one=True)
            version = str(result[0]) if result else "Unknown"
            self.logger.info(f"✅ Versión obtenida: {version}")
            return version
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo versión de la BD: {e}")
            raise DatabaseOperationError(f"Error obteniendo versión: {str(e)}", "SELECT", "database_version", self.db_type) from e

    def __parse_mariadb_column_charset_collation_row(self, row: tuple[Any, ...], column_name: str) -> tuple[str, str | None, str | None]:
        """Parsea fila de charset/collation para MariaDB."""
        charset: str | None = str(row[1]) if len(row) > 1 else None
        collation: str | None = str(row[2]) if len(row) > 2 else None
        return (column_name, charset, collation)

    def __parse_collation_only_row(self, row: tuple[Any, ...], column_name: str) -> tuple[str, str | None, str | None]:
        """Parsea fila con solo collation (PostgreSQL, SQL Server, HSQLDB)."""
        collation: str | None = str(row[2]) if len(row) > 2 else None
        return (column_name, None, collation)

    def __parse_empty_charset_collation_row(self, row: tuple[Any, ...], column_name: str) -> tuple[str, str | None, str | None]:
        """Parsea fila sin información de charset/collation (Oracle, SQLite)."""
        return (column_name, None, None)

    def __parse_db_charset_mariadb(self, result: tuple[Any, ...]) -> dict[str, Any]:
        """Parsea database charset/collation para MariaDB."""
        if not result or len(result) == 0:
            return {}
        charset: str = str(result[0])
        if len(result) > 1:
            collation: str | None = str(result[1])
            return {"charset": charset, "collation": collation}
        return {"charset": charset}

    def __parse_db_charset_oracle(self, result: tuple[Any, ...]) -> dict[str, Any]:
        """Parsea database charset/collation para Oracle."""
        if not result or len(result) == 0:
            return {}
        charset: str = str(result[0])
        if len(result) > 1:
            nchar_charset: str | None = str(result[1])
            return {"charset": charset, "nchar_charset": nchar_charset}
        return {"charset": charset}

    def __parse_db_charset_postgresql(self, result: tuple[Any, ...]) -> dict[str, Any]:
        """Parsea database charset/collation para PostgreSQL."""
        if not result or len(result) == 0:
            return {}
        if len(result) > 2:
            return {"encoding": str(result[0]), "collate": str(result[1]), "ctype": str(result[2])}
        return {"encoding": str(result[0])}

    def __parse_db_charset_single_field(self, result: tuple[Any, ...], field_name: str) -> dict[str, Any]:
        """Parsea database charset/collation de un único campo."""
        return {field_name: str(result[0])} if result and len(result) > 0 else {}

    def _parse_charset_collation_result(self, result: tuple[Any, ...] | None) -> dict[str, Any]:
        """Parsea resultado de database charset/collation según tipo de BD."""
        if not result:
            return {}

        parser_map: dict[str, Callable[[tuple[Any, ...]], dict[str, Any]]] = {
            "mariadb": self.__parse_db_charset_mariadb,
            "oracle": self.__parse_db_charset_oracle,
            "postgresql": self.__parse_db_charset_postgresql,
            "sqlserver": lambda r: self.__parse_db_charset_single_field(r, "collation"),
            "hsqldb": lambda r: self.__parse_db_charset_single_field(r, "collation"),
            "sqlite": lambda r: self.__parse_db_charset_single_field(r, "encoding"),
        }

        parser: Callable[[tuple[Any, ...]], dict[str, Any]] = parser_map.get(self.db_type, lambda _: {})
        return parser(result)

    def __parse_column_charset_collation_row(self, row: tuple[Any, ...]) -> tuple[str, str | None, str | None]:
        """Parsea una fila de resultado de charset/collation de columna según el tipo de BD.

        Args:
            row: Tupla de resultado con información de columna

        Returns:
            Tupla (column_name, charset, collation) para compatibilidad con generadores de documentos
        """
        column_name: str = str(row[0]) if len(row) > 0 else ""

        # Mapeo de tipos de BD a funciones de parsing
        parser_map: dict[str, Callable[[tuple[Any, ...], str], tuple[str, str | None, str | None]]] = {
            "mariadb": self.__parse_mariadb_column_charset_collation_row,
            "oracle": self.__parse_empty_charset_collation_row,
            "postgresql": self.__parse_collation_only_row,
            "sqlserver": self.__parse_collation_only_row,
            "hsqldb": self.__parse_collation_only_row,
            "sqlite": self.__parse_empty_charset_collation_row,
        }

        parser = parser_map.get(self.db_type, self.__parse_empty_charset_collation_row)
        return parser(row, column_name)

    def get_database_charset_collation(self) -> dict[str, Any]:
        """
        Obtiene información de charset/collation de la base de datos.

        Returns:
            Diccionario con información de charset/collation según el motor

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            self.logger.debug(f"🔍 Obteniendo charset/collation de la BD ({self.db_type})")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            result = executor.execute_query("database_charset_collation", database=context_database, fetch_one=True)

            info: dict[str, Any] = self._parse_charset_collation_result(result)
            self.logger.info(f"✅ Charset/Collation obtenido: {info}")
            return info
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo charset/collation: {e}")
            raise DatabaseOperationError(f"Error obteniendo charset/collation: {str(e)}", "SELECT", "database_charset_collation", self.db_type) from e

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
        try:
            self._verify_executor_initialized()
            context_database: str = self._get_query_context_database()
            cache_key: tuple[str, str] = (str(context_database or ""), str(tabla or ""))

            cached_charset_collation = self.db_cache.get_columns_charset_collation(cache_key)
            if cached_charset_collation is not None:
                self.logger.debug(f"♻️  Usando charset/collation en caché para tabla {tabla}")
                return list(cached_charset_collation)

            context_label: str = self._get_query_context_label()
            self.logger.debug(f"🔍 Obteniendo charset/collation de columnas de {tabla} ({context_label}: {context_database})")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            results = executor.execute_query("columns_charset_collation", tabla=tabla, database=context_database)

            info_list: list[tuple[str, str | None, str | None]] = [self.__parse_column_charset_collation_row(row) for row in results] if results else []
            self.db_cache.set_columns_charset_collation(cache_key, info_list)
            self.logger.info(f"✅ Charset/Collation de {len(info_list)} columnas obtenido")
            return info_list
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo charset/collation de columnas: {e}")
            raise DatabaseOperationError(f"Error obteniendo charset/collation de columnas: {str(e)}", "SELECT", tabla, self.db_type) from e

    def get_storage_inventory(self, tablespace: str | None = None) -> dict[str, Any]:
        """Obtiene inventario de tamaño de ficheros/tablespaces según el motor.

        Args:
            tablespace: Nombre de tablespace (requerido en Oracle/PostgreSQL).

        Returns:
            Diccionario con claves `primary` y `secondary`.
        """
        try:
            self._verify_executor_initialized()
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor

            database_name: str = str(self.database or "")
            return executor.get_storage_inventory(database=database_name, tablespace=tablespace)
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo inventario de almacenamiento: {e}")
            raise DatabaseOperationError(
                f"Error obteniendo inventario de almacenamiento: {str(e)}",
                "SELECT",
                db_type=self.db_type,
            ) from e

    # ==================== MÉTODOS ADICIONALES ====================

    def execute_query(self, query_name: str, fetch_one: bool = False, **kwargs) -> Any:
        """
        Ejecuta una consulta con los parámetros proporcionados

        Args:
            query_name: Nombre de la consulta a ejecutar
            fetch_one: Si es True, devuelve solo un resultado
            **kwargs: Parámetros para formatear la consulta

        Returns:
            Resultado de la consulta

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            self.logger.debug(f"📄 Ejecutando consulta: {query_name}")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            result = executor.execute_query(query_name, fetch_one, **kwargs)
            self.logger.info(f"✅ Consulta {query_name} ejecutada exitosamente")
            return result
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error ejecutando consulta {query_name}: {e}")
            raise DatabaseOperationError(f"Error ejecutando consulta: {str(e)}", "SELECT", db_type=self.db_type) from e

    def execute_custom_query(self, sql: str, fetch_one: bool = False, params=None) -> Any:
        """
        Ejecuta una consulta SQL personalizada

        Args:
            sql: Consulta SQL a ejecutar
            fetch_one: Si es True, devuelve solo un resultado
            params: Parámetros para la consulta (opcional)

        Returns:
            Resultado de la consulta

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        try:
            self._verify_executor_initialized()
            self.logger.debug("📝 Ejecutando consulta SQL personalizada")
            assert self.query_executor is not None
            executor: DatabaseQueryExecutor = self.query_executor
            result = executor.execute_custom_query(sql, fetch_one, params)
            self.logger.info("✅ Consulta SQL personalizada ejecutada exitosamente")
            return result
        except DatabaseOperationError:
            raise
        except Exception as e:
            self.logger.error(f"❌ Error ejecutando consulta SQL: {e}")
            raise DatabaseOperationError(f"Error ejecutando consulta SQL: {str(e)}", "EXECUTE", db_type=self.db_type) from e

    def get_query_info(self) -> dict[str, Any]:
        """
        Obtiene información sobre las consultas disponibles

        Returns:
            Diccionario con información de las consultas
        """
        return self.db_queries.get_query_info()

    def get_available_queries(self) -> list[str]:
        """
        Obtiene los nombres de las consultas disponibles

        Returns:
            Lista de nombres de consultas disponibles
        """
        return self.db_queries.get_available_query_names()

    def validate_query_parameters(self, query_name: str, **kwargs) -> bool:
        """
        Valida si los parámetros proporcionados son suficientes para una consulta

        Args:
            query_name: Nombre de la consulta a validar
            **kwargs: Parámetros a validar

        Returns:
            True si los parámetros son suficientes, False en caso contrario
        """
        return self.db_queries.validate_query_parameters(query_name, **kwargs)

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

        Este método es útil para usar DatabaseManager con librerías que requieren
        una Engine de SQLAlchemy, como bulk_crud.

        Returns:
            Engine de SQLAlchemy configurado con la base de datos actual.

        Raises:
            ImportError: Si SQLAlchemy no está instalado.
            DatabaseConnectionError: Si hay error creando la Engine.

        Ejemplo:
            db_mgr = DatabaseManager("oracle", {"user": "hr", "password": "pass", "service_name": "ORCL"})
            engine = db_mgr.get_sqlalchemy_engine()

            # Usar con bulk_crud
            from util_bbdd.bulk_crud import BulkCrudManager
            bcm = BulkCrudManager(engine)
        """
        return SQLAlchemyEngineFactory.create_engine(
            self.db_type,
            self.conn_params,
            self.database,
            sql_server_driver=self.sql_server_driver,
        )

    # ==================== CONTEXT MANAGER ====================

    def __enter__(self) -> "DatabaseManager":
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cierra la conexión"""
        self.close()

    def __del__(self):
        """Destructor - cierra la conexión"""
        try:
            self.close()
        except Exception:
            pass  # Ignorar errores en destructor

    # ==================== MÉTODOS ESTÁTICOS PARA VALIDACIÓN ====================

    @staticmethod
    def get_supported_db_types() -> list[str]:
        """
        Obtiene la lista de tipos de bases de datos soportados

        Returns:
            Lista de tipos de bases de datos soportados
        """
        from .database_type_validator import get_supported_db_types

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
        from .database_type_validator import get_database_validator

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
        from .database_type_validator import validate_db_type

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
        from .database_type_validator import get_db_type_info

        return get_db_type_info(db_type)

