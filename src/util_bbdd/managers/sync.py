"""
Módulo para manejo de operaciones de base de datos
Soporta MariaDB, Oracle, PostgreSQL, SQLite, HSQLDB y SQL Server
"""

import logging

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy.engine.base import Engine

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine

from ..connection.connect_factory import ConnectFactory
from ..connection.connection_params_manager import ConnectionParamsManager
from ..connection.pool_protocol import ConnectionPoolProtocol
from ..connection.sync_close_utils import parse_close_timeout, run_sync_close_operation
from ..database_exceptions import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseDriverError,
    DatabaseOperationError,
    DatabaseValidationError,
    QueryError,
)
from ..database_queries import DatabaseQueries
from ..database_type_validator import (
    DatabaseTypeValidator,
    get_database_validator,
    get_db_type_info,
    get_supported_db_types,
    validate_db_type,
)
from ..driver_validator import DriverValidator
from ..executors.sync_query_executor import SyncQueryExecutor
from ..factory.pool_factory import PoolFactory
from ..factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory
from ..metadata_cache import DatabaseMetadataCache, RelationshipMetadataCache
from ..metadata_contracts import Rows
from ..metadata_normalization import (
    NormalizedColumnRow,
    NormalizedTableRow,
    normalize_column_rows,
    normalize_table_rows,
)
from ..result_types import RowOrNone


class DatabaseManager:
    """
    Clase para manejar conexiones y operaciones de base de datos.

    Soporta logging y manejo de excepciones propias.
    Bases de datos soportadas: MariaDB, Oracle, PostgreSQL, SQLite, HSQLDB, SQL Server
    """

    _SYNC_QUERY_EXECUTOR_NOT_INITIALIZED = (
        "Ejecutor sync de consultas no inicializado. Verifique la conexión a la base de datos."
    )

    def _build_query_executor(
        self,
        connection_provider: Callable[[], Any],
        connection_releaser: Callable[[Any], None],
    ) -> None:
        """Inicializa ejecutores stateless con provider/releaser.

        Args:
            connection_provider: Función que obtiene una conexión para cada operación.
            connection_releaser: Función que libera/devolver la conexión al finalizar.
        """
        self.sync_query_executor = SyncQueryExecutor(
            connection_provider=connection_provider,
            connection_releaser=connection_releaser,
            registry=self._query_catalog.registry,
            resolver=self._query_catalog.resolver,
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
        self.logger.info(f"🔧 Inicializando DatabaseManager para {db_type.upper()}")

        # Inicializar la conexión como None
        self._connection: Any = None
        self.cursor: Any = None
        self.sync_query_executor: SyncQueryExecutor | None = None

        # Inicializar cachés centralizados (composición jerárquica)
        self.db_cache: DatabaseMetadataCache = DatabaseMetadataCache()
        self.relationship_cache: RelationshipMetadataCache = RelationshipMetadataCache(db_cache=self.db_cache)
        self.logger.debug("✅ Cachés centralizados [DatabaseMetadataCache + RelationshipMetadataCache] inicializados")

        # Inicializar validador de tipos (lazy loading)
        self._db_validator: DatabaseTypeValidator | None = None

        # Pool de conexiones
        self.use_pool: bool = use_pool
        self.pool_connection: ConnectionPoolProtocol | None = None
        self._default_close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))

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
            self._query_catalog = DatabaseQueries(self.db_type, queries_path)
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
            raise DatabaseConfigurationError(
                f"Error al inicializar DatabaseManager: {str(e)}", self.db_type, str(e)
            ) from e

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

        if self.pool_connection:
            self.pool_connection.close_connection(connection)
            self.logger.debug("📦 Conexión devuelta al pool")
            return

        connection.close()
        self.logger.debug("🔌 Conexión cerrada")

    def close(self, timeout_seconds: float | None, force: bool) -> None:
        """
        Cierra la conexión a la base de datos y libera recursos del pool

        Logs:
            - ✅ Si la operación es exitosa
            - ❌ Si hay errores
        """
        effective_timeout = self._default_close_timeout_seconds if timeout_seconds is None else timeout_seconds
        close_errors: list[Exception] = []

        pool = self.pool_connection
        self.pool_connection = None
        if pool is not None:
            try:
                pool.close(timeout_seconds=effective_timeout, force=force)
                self.logger.info("🔗 Pool liberado y cerrado")
            except Exception as err:
                close_errors.append(err)

        cursor = self.cursor
        self.cursor = None
        if cursor is not None:
            try:
                run_sync_close_operation(
                    action=lambda: cursor.close(),
                    timeout_seconds=effective_timeout,
                    action_name=f"cierre cursor {self.db_type}",
                    db_type=self.db_type,
                )
                self.logger.debug(f"✅ Cursor cerrado para {self.db_type}")
            except Exception as err:
                close_errors.append(err)

        connection = self._connection
        self._connection = None
        if connection is not None:
            try:
                run_sync_close_operation(
                    action=lambda: connection.close(),
                    timeout_seconds=effective_timeout,
                    action_name=f"cierre conexión {self.db_type}",
                    db_type=self.db_type,
                )
                self.logger.info(f"✅ Conexión cerrada para {self.db_type}")
            except Exception as err:
                close_errors.append(err)

        if close_errors:
            error_details = " | ".join(str(err) for err in close_errors)
            raise DatabaseOperationError(
                message=f"Errores cerrando recursos de base de datos: {error_details}",
                operation="CLOSE",
                db_type=self.db_type,
            ) from close_errors[0]

        self.logger.info("✅ DatabaseManager cerrado")

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

    @staticmethod
    def _clear_tuple_cache_by_context(cache: dict[tuple[Any, ...], Any], context: str) -> None:
        keys_to_remove: list[tuple[Any, ...]] = [key for key in cache if key and str(key[0]) == context]
        for key in keys_to_remove:
            cache.pop(key, None)

    def _clear_context_cache(self, context: str) -> None:
        """Limpia caché para un contexto/schema específico."""
        context_caches: tuple[dict[str, Any], ...] = (
            self.db_cache._tables_cache,
            self.db_cache._views_cache,
            self.db_cache._routines_cache,
        )
        for cache in context_caches:
            cache.pop(context, None)

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
        for cache in tuple_caches:
            self._clear_tuple_cache_by_context(cache, context)

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
        """Verifica que el ejecutor sync de consultas esté inicializado."""
        self._verify_sync_executor_initialized()

    def _verify_sync_executor_initialized(self) -> None:
        """Verifica que el ejecutor sync de consultas esté inicializado."""
        if not self.sync_query_executor:
            self.logger.error("❌ Ejecutor sync de consultas no inicializado")
            raise DatabaseOperationError(self._SYNC_QUERY_EXECUTOR_NOT_INITIALIZED, db_type=self.db_type)

    def _get_sync_query_executor(self) -> SyncQueryExecutor:
        """Obtiene el ejecutor sync garantizando inicialización."""
        self._verify_sync_executor_initialized()
        assert self.sync_query_executor is not None
        return self.sync_query_executor

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

    def _add_metadata_context_params(self, params: dict[str, Any], context: str | None) -> dict[str, Any]:
        """Añade parámetros de contexto metadata según motor."""
        if not context or self.db_type == "mariadb":
            return params
        if self.db_type in {"oracle", "sqlserver"}:
            params["esquema"] = context
        if self.db_type in {"postgresql", "hsqldb", "sqlserver"}:
            params["database"] = context
        return params

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
        for pos in (2, 1, 0):
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

    @staticmethod
    def _iter_exception_chain(err: BaseException) -> list[BaseException]:
        chain: list[BaseException] = []
        seen: set[int] = set()
        current: BaseException | None = err
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            chain.append(current)
            current = current.__cause__ if current.__cause__ is not None else current.__context__
        return chain

    def _is_mariadb_show_create_decode_error(self, err: BaseException) -> bool:
        return self._is_mariadb_decode_error(err)

    def _is_mariadb_decode_error(self, err: BaseException) -> bool:
        if self.db_type != "mariadb":
            return False
        for item in self._iter_exception_chain(err):
            if isinstance(item, UnicodeDecodeError):
                return True
            text = str(item).lower()
            if "mariadb.cursor" in text and "exception set" in text:
                return True
            if "codec can't decode" in text:
                return True
        return False

    @staticmethod
    def _escape_sql_literal(value: str) -> str:
        return str(value).replace("'", "''")

    @staticmethod
    def _decode_mariadb_hex_text(value: Any) -> str:
        if value is None:
            return ""
        raw_hex: str = str(value).strip()
        if not raw_hex:
            return ""
        try:
            raw_bytes = bytes.fromhex(raw_hex)
        except ValueError:
            return str(value)
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return raw_bytes.decode("latin-1")

    def _fetch_mariadb_columns_safe(self, context_database: str, tabla: str) -> Rows:
        escaped_database = self._escape_sql_literal(context_database)
        escaped_table = self._escape_sql_literal(tabla)
        sql = (
            "SELECT HEX(COLUMN_NAME) AS column_name_hex, "
            "HEX(COLUMN_TYPE) AS column_type_hex, "
            "IS_NULLABLE, "
            "COLUMN_KEY, "
            "CASE WHEN COLUMN_DEFAULT IS NULL THEN 1 ELSE 0 END AS default_is_null, "
            "HEX(CAST(COLUMN_DEFAULT AS BINARY)) AS column_default_hex, "
            "HEX(COALESCE(EXTRA, '')) AS extra_hex, "
            "HEX(COALESCE(COLUMN_COMMENT, '')) AS column_comment_hex "
            "FROM information_schema.columns "
            f"WHERE table_schema = '{escaped_database}' AND table_name = '{escaped_table}' "
            "ORDER BY ordinal_position"
        )
        safe_rows: Rows = self.execute_custom_many(sql)
        decoded_rows: Rows = []
        for row in safe_rows:
            if not isinstance(row, (tuple, list)) or len(row) < 8:
                continue

            default_is_null = str(row[4]).strip() in {"1", "True", "true"}
            column_default: str | None = None
            if not default_is_null:
                column_default = self._decode_mariadb_hex_text(row[5])

            decoded_rows.append(
                (
                    self._decode_mariadb_hex_text(row[0]),
                    self._decode_mariadb_hex_text(row[1]),
                    str(row[2]),
                    str(row[3]),
                    column_default,
                    self._decode_mariadb_hex_text(row[6]),
                    self._decode_mariadb_hex_text(row[7]),
                )
            )
        return decoded_rows

    @staticmethod
    def _quote_identifier_mariadb(identifier: str) -> str:
        safe_identifier = str(identifier).replace("`", "``")
        return f"`{safe_identifier}`"

    def _fetch_mariadb_view_from_information_schema(self, database: str, view_name: str) -> str:
        """Obtiene DDL de vista MariaDB desde INFORMATION_SCHEMA cuando SHOW CREATE VIEW falla."""
        escaped_view = self._escape_sql_literal(view_name)
        sql: str = f"""
            SELECT VIEW_DEFINITION
            FROM information_schema.views
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = '{escaped_view}'
            LIMIT 1
        """
        try:
            result = self.execute_custom_one(sql)
            if result and len(result) > 0 and result[0]:
                view_def = str(result[0]).strip()
                if view_def:
                    return f"CREATE OR REPLACE VIEW `{view_name}` AS\n{view_def}"
            return f"-- View {view_name} definition unavailable (fallback)\n"
        except Exception as e:
            self.logger.warning("Fallback para vista %s también falló: %s", view_name, e)
            return f"-- View {view_name} definition unavailable\n"

    def _fetch_mariadb_routine_from_information_schema(
        self, database: str, routine_name: str, routine_type: str
    ) -> str:
        """Obtiene DDL de rutina MariaDB desde INFORMATION_SCHEMA cuando SHOW CREATE falla."""
        escaped_routine: str = self._escape_sql_literal(routine_name)
        escaped_type: str = self._escape_sql_literal(routine_type.upper())
        sql: str = f"""
            SELECT ROUTINE_DEFINITION
            FROM information_schema.routines
            WHERE TABLE_SCHEMA = DATABASE()
            AND ROUTINE_NAME = '{escaped_routine}'
            AND ROUTINE_TYPE = '{escaped_type}'
            LIMIT 1
        """
        try:
            result = self.execute_custom_one(sql)
            if result and len(result) > 0 and result[0]:
                routine_def = str(result[0]).strip()
                if routine_def:
                    return f"CREATE {routine_type} `{routine_name}`\n{routine_def}"
            return f"-- {routine_type} {routine_name} definition unavailable (fallback)\n"
        except Exception as e:
            self.logger.warning("Fallback para rutina %s también falló: %s", routine_name, e)
            return f"-- {routine_type} {routine_name} definition unavailable\n"

    @staticmethod
    def _format_mariadb_default(default_value: Any) -> str:
        raw = str(default_value)
        upper_raw = raw.upper()
        if upper_raw == "NULL":
            return "NULL"
        if upper_raw in {"CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP()"}:
            return raw
        if upper_raw.endswith("()"):
            return raw
        try:
            float(raw)
            return raw
        except ValueError:
            escaped = raw.replace("\\", "\\\\").replace("'", "''")
            return f"'{escaped}'"

    def _build_mariadb_ddl_from_metadata(self, tabla: str) -> str:
        """Construye DDL de MariaDB desde metadata de columnas.

        Args:
            tabla: Nombre de la tabla

        Returns:
            String DDL CREATE TABLE (vacío si no hay columnas)
        """
        rows: list[Any] = list(self.get_columns(tabla))
        if not rows:
            return ""

        column_defs: list[str] = [self._build_column_definition(row) for row in rows if self._is_valid_column_row(row)]

        if not column_defs:
            return ""

        pk_constraint: str = self._build_primary_key_constraint(tabla)
        if pk_constraint:
            column_defs.append(pk_constraint)

        table_identifier: str = self._quote_identifier_mariadb(tabla)
        return "CREATE TABLE " + table_identifier + " (\n" + ",\n".join(column_defs) + "\n)"

    def _is_valid_column_row(self, row: Any) -> bool:
        """Valida que una fila sea una tupla/lista válida.

        Args:
            row: Fila a validar

        Returns:
            True si la fila es válida
        """
        return isinstance(row, (tuple, list)) and bool(row)

    def _build_column_definition(self, row: Any) -> str:
        """Construye la definición de columna MariaDB.

        Args:
            row: Tupla/lista con datos de columna [name, type, nullable, ..., default, extra]

        Returns:
            String con definición completa de columna
        """
        column_name: str = self._extract_column_name(row)
        column_type: str = self._extract_column_type(row)
        nullable: str = self._extract_nullable_clause(row)
        default_clause: str = self._extract_default_clause(row)
        extra: str = self._extract_extra_clause(row)

        parts: list[str] = [
            self._quote_identifier_mariadb(column_name),
            column_type,
            nullable,
        ]

        if default_clause:
            parts.append(default_clause)
        if extra:
            parts.append(extra)

        return "  " + " ".join(parts)

    def _extract_column_name(self, row: Any) -> str:
        """Extrae nombre de columna desde fila."""
        return str(row[0]) if row else ""

    def _extract_column_type(self, row: Any) -> str:
        """Extrae tipo de dato desde fila."""
        return str(row[1]) if len(row) > 1 else "TEXT"

    def _extract_nullable_clause(self, row: Any) -> str:
        """Extrae cláusula NULL/NOT NULL."""
        nullable_flag: str = str(row[2]).upper() if len(row) > 2 else "YES"
        return "NOT NULL" if nullable_flag == "NO" else "NULL"

    def _extract_default_clause(self, row: Any) -> str:
        """Extrae cláusula DEFAULT."""
        if len(row) <= 4 or row[4] is None:
            return ""

        default_value = self._format_mariadb_default(row[4])
        return f"DEFAULT {default_value}"

    def _extract_extra_clause(self, row: Any) -> str:
        """Extrae cláusula EXTRA (AUTO_INCREMENT, etc)."""
        if len(row) <= 5 or not row[5]:
            return ""

        extra: str = str(row[5]).strip()
        return extra if extra else ""

    def _build_primary_key_constraint(self, tabla: str) -> str:
        """Construye cláusula PRIMARY KEY si existen claves primarias.

        Args:
            tabla: Nombre de la tabla

        Returns:
            String con PRIMARY KEY constraint o vacío
        """
        pk_rows: list[Any] = list(self.get_primary_keys(tabla))
        pk_columns: list[str] = [
            self._quote_identifier_mariadb(str(row[0]))
            for row in pk_rows
            if isinstance(row, (tuple, list)) and len(row) > 0
        ]

        if not pk_columns:
            return ""

        return f"  PRIMARY KEY ({', '.join(pk_columns)})"

    def get_query_context_database(self) -> str:
        """Expone el contexto de metadatos (schema/database) para consumidores externos.

        Returns:
            Contexto efectivo usado por las consultas de metadatos.
        """
        return self._get_query_context_database()

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
        executor = self._get_sync_query_executor()
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
        executor = self._get_sync_query_executor()
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
        cache_lookup: Callable[[], list | None],
        cache_store: Callable[[list], None],
        fetch_rows: Callable[[], Rows],
        cache_hit_message: str,
        success_message: str,
        fetch_debug_message: str | None = None,
    ) -> list:
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

    def _get_cached_text(
        self,
        *,
        cache_lookup: Callable[[], str | None],
        cache_store: Callable[[str], None],
        fetch_text: Callable[[], str],
        cache_hit_message: str,
        success_message: str,
    ) -> str:
        cached_text = cache_lookup()
        if cached_text is not None:
            self.logger.debug(cache_hit_message)
            return cached_text
        text = fetch_text()
        cache_store(text)
        self.logger.info(success_message)
        return text

    def get_tables(self) -> list:
        """
        Obtiene la lista de tablas de la base de datos.

        Returns:
            Lista de tablas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        cache_key = self._cache_context_key(context_database)
        context_label = self._get_query_context_label()

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

    def get_views(self) -> list:
        """
        Obtiene la lista de vistas de la base de datos.

        Returns:
            Lista de vistas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        cache_key = self._cache_context_key(context_database)
        context_label = self._get_query_context_label()

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

    def get_routines(self) -> list:
        """
        Obtiene la lista de rutinas (procedures y funciones) de la base de datos.

        Returns:
            Lista de rutinas

        Raises:
            DatabaseOperationError: Si hay error en la operación
        """
        context_database: str = self._get_query_context_database()
        cache_key = self._cache_context_key(context_database)
        context_label = self._get_query_context_label()

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache._routines_cache.get(cache_key),
            cache_store=lambda rows: self.db_cache._routines_cache.__setitem__(cache_key, list(rows)),
            fetch_rows=lambda: self._execute_metadata_many(
                "obtener_rutinas",
                params={"database": context_database},
                error_message="Error obteniendo rutinas",
            ),
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
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)

        def _fetch_ddl() -> str:
            self.logger.debug(f"🔍 Obteniendo DDL para tabla {tabla} ({context_label}: {context_database})")
            params: dict[str, Any] = self._add_metadata_context_params({"tabla": tabla}, context_database)
            try:
                ddl_raw = self._execute_metadata_one(
                    "create_table",
                    params=params,
                    error_message="Error obteniendo DDL",
                    table_name=tabla,
                )
            except DatabaseOperationError as err:
                if not self._is_mariadb_show_create_decode_error(err):
                    raise
                self.logger.warning(
                    "Fallback DDL MariaDB por error de decodificación en SHOW CREATE TABLE para %s",
                    tabla,
                )
                return self._build_mariadb_ddl_from_metadata(tabla)
            return self._normalize_ddl_result(ddl_raw)

        return self._get_cached_text(
            cache_lookup=lambda: self.db_cache._ddl_cache.get(cache_key),
            cache_store=lambda ddl: self.db_cache._ddl_cache.__setitem__(cache_key, ddl),
            fetch_text=_fetch_ddl,
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
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, vista)

        def _fetch_ddl() -> str:
            self.logger.debug(f"🔍 Obteniendo DDL para vista {vista} ({context_label}: {context_database})")
            params: dict[str, Any] = self._add_metadata_context_params({"tabla": vista}, context_database)
            try:
                ddl_raw = self._execute_metadata_one(
                    "create_view",
                    params=params,
                    error_message="Error obteniendo DDL de vista",
                    table_name=vista,
                )
                return self._normalize_ddl_result(ddl_raw)
            except DatabaseOperationError:
                if self.db_type != "mariadb":
                    raise
                self.logger.warning(
                    "Fallback DDL vista MariaDB por error en SHOW CREATE VIEW para %s. Obteniendo de INFORMATION_SCHEMA",
                    vista,
                )
                return self._fetch_mariadb_view_from_information_schema(context_database, vista)

        return self._get_cached_text(
            cache_lookup=lambda: self.db_cache._view_ddl_cache.get(cache_key),
            cache_store=lambda ddl: self.db_cache._view_ddl_cache.__setitem__(cache_key, ddl),
            fetch_text=_fetch_ddl,
            cache_hit_message=f"♻️  Usando DDL de vista en caché para {vista}",
            success_message=f"✅ DDL obtenido para vista {vista}",
        )

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
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)

        def _fetch_columns() -> Rows:
            try:
                return self._execute_metadata_many(
                    "columnas_tabla",
                    params={"database": context_database, "tabla": tabla},
                    error_message="Error obteniendo columnas",
                    table_name=tabla,
                )
            except DatabaseOperationError as err:
                if not self._is_mariadb_decode_error(err):
                    raise
                self.logger.warning(
                    "Fallback columnas MariaDB por error de decodificación en metadata para %s",
                    tabla,
                )
                return self._fetch_mariadb_columns_safe(context_database, tabla)

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache.get_columns(cache_key),
            cache_store=lambda rows: self.db_cache.set_columns(cache_key, rows),
            fetch_rows=_fetch_columns,
            cache_hit_message=f"♻️  Usando columnas en caché para tabla {tabla}",
            success_message=f"✅ {{count}} columnas obtenidas de {tabla} ({context_label}: {context_database})",
            fetch_debug_message=f"🔍 Obteniendo columnas de {tabla} ({context_label}: {context_database})",
        )

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
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        routine_type = str(tipo_rutina or "").upper()
        cache_key = self._cache_routine_key(context_database, rutina, routine_type)

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache._routine_parameters_cache.get(cache_key),
            cache_store=lambda rows: self.db_cache._routine_parameters_cache.__setitem__(cache_key, list(rows)),
            fetch_rows=lambda: self._execute_metadata_many(
                "parametros_rutina",
                params={"database": context_database, "rutina": rutina, "tipo_rutina": routine_type},
                error_message="Error obteniendo parámetros de rutina",
                table_name=rutina,
            ),
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
        context_label = self._get_query_context_label()
        routine_type = str(tipo_rutina or "").upper()
        cache_key = self._cache_routine_key(context_database, rutina, routine_type)

        def _fetch_routine_ddl() -> str:
            self.logger.debug(
                f"🔍 Obteniendo DDL para rutina {routine_type} {rutina} ({context_label}: {context_database})"
            )
            params: dict[str, Any] = self._add_metadata_context_params(
                {"rutina": rutina, "tipo_rutina": routine_type},
                context_database,
            )
            try:
                ddl_raw = self._execute_metadata_one(
                    "create_rutina",
                    params=params,
                    error_message="Error obteniendo DDL de rutina",
                    table_name=rutina,
                )
                return self._normalize_ddl_result(ddl_raw)
            except DatabaseOperationError:
                if self.db_type != "mariadb":
                    raise
                self.logger.warning(
                    "Fallback DDL rutina MariaDB por error en SHOW CREATE para %s %s. Obteniendo de INFORMATION_SCHEMA",
                    routine_type,
                    rutina,
                )
                return self._fetch_mariadb_routine_from_information_schema(context_database, rutina, routine_type)

        return self._get_cached_text(
            cache_lookup=lambda: self.db_cache._routine_ddl_cache.get(cache_key),
            cache_store=lambda ddl: self.db_cache._routine_ddl_cache.__setitem__(cache_key, ddl),
            fetch_text=_fetch_routine_ddl,
            cache_hit_message=f"♻️  Usando DDL de rutina en caché para {routine_type} {rutina}",
            success_message=f"✅ DDL obtenido para rutina {rutina}",
        )

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
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache.get_indices(cache_key),
            cache_store=lambda rows: self.db_cache.set_indices(cache_key, rows),
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
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache.get_primary_keys(cache_key),
            cache_store=lambda rows: self.db_cache.set_primary_keys(cache_key, rows),
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
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache.get_foreign_keys(cache_key),
            cache_store=lambda rows: self.db_cache.set_foreign_keys(cache_key, rows),
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
        context_database: str = self._get_query_context_database()
        context_label = self._get_query_context_label()
        cache_key = self._cache_table_key(context_database, tabla)

        return self._get_cached_rows(
            cache_lookup=lambda: self.db_cache.get_unique_constraints(cache_key),
            cache_store=lambda rows: self.db_cache.set_unique_constraints(cache_key, rows),
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
        version = str(result[0]) if result else "Unknown"
        self.logger.info(f"✅ Versión obtenida: {version}")
        return version

    def __parse_mariadb_column_charset_collation_row(
        self, row: tuple[Any, ...], column_name: str
    ) -> tuple[str, str | None, str | None]:
        """Parsea fila de charset/collation para MariaDB."""
        charset: str | None = str(row[1]) if len(row) > 1 else None
        collation: str | None = str(row[2]) if len(row) > 2 else None
        return (column_name, charset, collation)

    def __parse_collation_only_row(self, row: tuple[Any, ...], column_name: str) -> tuple[str, str | None, str | None]:
        """Parsea fila con solo collation (PostgreSQL, SQL Server, HSQLDB)."""
        collation: str | None = str(row[2]) if len(row) > 2 else None
        return (column_name, None, collation)

    def __parse_empty_charset_collation_row(
        self, row: tuple[Any, ...], column_name: str
    ) -> tuple[str, str | None, str | None]:
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

        return cast(
            list[tuple[str, str | None, str | None]],
            self._get_cached_rows(
                cache_lookup=lambda: self.db_cache.get_columns_charset_collation(cache_key),
                cache_store=lambda rows: self.db_cache.set_columns_charset_collation(cache_key, rows),
                fetch_rows=lambda: cast(
                    Rows,
                    [
                        self.__parse_column_charset_collation_row(row)
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

    def _storage_inventory_sqlserver(self, _context_database: str, _tablespace: str | None) -> dict[str, Any]:
        return {
            "primary": self.execute_query_many("ficheros_fisicos"),
            "secondary": [],
        }

    def _storage_inventory_oracle(self, _context_database: str, tablespace: str | None) -> dict[str, Any]:
        if not tablespace:
            raise ValueError("Para Oracle debe proporcionar 'tablespace'")
        return {
            "primary": self.execute_query_many("ficheros_fisicos", tablespace=tablespace),
            "secondary": [],
        }

    def _storage_inventory_mariadb(self, context_database: str, _tablespace: str | None) -> dict[str, Any]:
        if not context_database:
            raise ValueError("Para MariaDB debe proporcionar 'database'")
        return {
            "primary": self.execute_query_many("ficheros_fisicos", database=context_database),
            "secondary": self.execute_query_many("ficheros_fisicos_adicional", database=context_database),
        }

    def _storage_inventory_postgresql(self, _context_database: str, tablespace: str | None) -> dict[str, Any]:
        if not tablespace:
            raise ValueError("Para PostgreSQL debe proporcionar 'tablespace'")
        return {
            "primary": self.execute_query_many("ficheros_fisicos", tablespace=tablespace),
            "secondary": self.execute_query_many("temp_tablespaces"),
        }

    def _storage_inventory_sqlite(self, _context_database: str, _tablespace: str | None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "primary": self.execute_query_many("ficheros_fisicos"),
            "secondary": self.execute_query_many("ficheros_fisicos_adicional"),
        }
        try:
            result["temp_tablespaces"] = self.execute_query_many("temp_tablespaces")
        except Exception:
            result["temp_tablespaces"] = []
        return result

    def get_storage_inventory(self, tablespace: str | None = None) -> dict[str, Any]:
        """Obtiene inventario de tamaño de ficheros/tablespaces según el motor.

        Args:
            tablespace: Nombre de tablespace (requerido en Oracle/PostgreSQL).

        Returns:
            Diccionario con claves `primary` y `secondary`.
        """
        context_database = self._get_query_context_database()
        handlers: dict[str, Callable[[str, str | None], dict[str, Any]]] = {
            "sqlserver": self._storage_inventory_sqlserver,
            "oracle": self._storage_inventory_oracle,
            "mariadb": self._storage_inventory_mariadb,
            "postgresql": self._storage_inventory_postgresql,
            "sqlite": self._storage_inventory_sqlite,
        }
        handler = handlers.get(self.db_type)
        if handler is None:
            return {"primary": [], "secondary": []}
        result = self._run_metadata_operation(
            action=lambda: handler(context_database, tablespace),
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
        return self._query_catalog.resolver.resolve(query_name, self.db_type, params)

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
