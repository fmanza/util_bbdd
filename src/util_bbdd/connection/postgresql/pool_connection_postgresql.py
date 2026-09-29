"""Pool de conexiones para PostgreSQL (psycopg 3)."""

import logging
import sys

from typing import TYPE_CHECKING, Any, ClassVar

from ..._core.exceptions import PoolConnectionError, PoolTimeoutError
from ..close import FORCE_CLOSE_TIMEOUT_SECONDS, parse_close_timeout, run_close_operation_sync
from ..params import ConnectionParamsManager
from ._libpq import to_libpq_params

try:
    from psycopg_pool import ConnectionPool as PsycopgConnectionPool

    HAS_PSYCOPG_POOL = True
except ImportError:
    HAS_PSYCOPG_POOL = False

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool as PsycopgConnectionPool


class PoolConnection:
    """Pool de conexiones nativo para PostgreSQL (psycopg 3).

    Extrae configuración del pool desde conn_params:
    - pool_size (int, default: 5): Número de conexiones en pool
    - pool_timeout (int, default: 30): Timeout de conexión en segundos
    - max_idle (int, default: 300): Tiempo máximo de inactividad
    """

    #: Claves de conn_params que no van como parámetro libpq de la URI: las que ya forman la URI y las del pool.
    _CONNINFO_URI_OR_POOL_KEYS: ClassVar[frozenset[str]] = frozenset(
        {"user", "password", "host", "port", "dbname", "pool_size", "pool_timeout", "max_idle"}
    )

    def __init__(self, conn_params: dict[str, str | int]) -> None:
        """Inicializa pool nativo de psycopg 3.

        Args:
            conn_params: Diccionario con parámetros de conexión más configuración:
                - user (str): Usuario de BD
                - password (str): Contraseña
                - host (str): Host de BD (default: localhost)
                - database (str): Nombre de base de datos
                - port (int, optional): Puerto (default: 5432)
                - pool_size (int, optional): Conexiones en pool (default: 5)
                - pool_timeout (int, optional): Timeout en segundos (default: 30)
                - max_idle (int, optional): Max inactividad en segundos (default: 300)

        Raises:
            ImportError: Si psycopg no está instalado.
            ValueError: Si faltan parámetros críticos.
            Exception: Si la creación del pool falla.

        Example:
            ```python
            conn_params = {
                "user": "postgres",
                "password": "password",
                "host": "localhost",
                "database": "mydb",
                "port": 5432,
                "pool_size": 10,
                "pool_timeout": 30
            }
            pool = PoolConnection(conn_params)
            ```
        """
        if not HAS_PSYCOPG_POOL:
            raise ImportError(
                "Módulo 'psycopg' no está instalado. Instale con: pip install 'psycopg[pool]' o pip install psycopg"
            )

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.pool: PsycopgConnectionPool | None = None
        self._closed: bool = False
        self._close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))
        pool_config = ConnectionParamsManager.get_pool_config("postgresql", conn_params)
        self.pool_size: int = pool_config.pool_size
        self.pool_timeout: int = pool_config.pool_timeout
        self.max_idle: int = pool_config.max_idle
        self.conn_params: dict[str, str | int | bool] = pool_config.to_driver_kwargs()

        self.__create_pool()

    def __del__(self) -> None:
        """Limpia recursos al destruir el objeto."""
        try:
            self.close(timeout_seconds=self._close_timeout_seconds, force=True)
        except Exception:
            pass  # No propagar excepciones desde destructor

    def __create_pool(self) -> None:
        """Crea pool nativo de psycopg 3.

        Raises:
            Exception: Si la creación del pool falla.
        """
        try:
            from urllib.parse import quote, urlencode

            # Construir conninfo string para psycopg. user/password/database van URL-encoded:
            # interpolarlos crudos permite que un valor con "/", "#", "%" o espacios reinterprete
            # la URI y desvíe la conexión (ver AUDIT_CODE CNX-01, 2026-09-22).
            user: str | None = str(self.conn_params.get("user")) if self.conn_params.get("user") else None
            password: str | None = str(self.conn_params.get("password")) if self.conn_params.get("password") else None
            host: str = str(self.conn_params.get("host", "localhost"))
            port: str | int = self.conn_params.get("port", 5432)
            # Nombres y valores de libpq (dbname con prioridad sobre database, keepalives_*, booleanos 0/1).
            libpq_params: dict[str, Any] = to_libpq_params(dict(self.conn_params))
            raw_database: Any = libpq_params.get("dbname")
            database: str | None = str(raw_database) if raw_database else None

            user_enc: str = quote(user, safe="") if user else ""
            password_enc: str = quote(password, safe="") if password else ""
            database_enc: str = quote(database, safe="") if database else ""

            conninfo: str = f"postgresql://{user_enc}:{password_enc}@{host}:{port}/{database_enc}"

            # H6: el resto de opciones libpq (sslmode, connect_timeout, keepalives, application_name,
            # options...) van como parámetros de la URI; antes solo iba ``options`` y el pool ignoraba
            # p. ej. sslmode="require".
            query_params: dict[str, Any] = {
                key: value
                for key, value in libpq_params.items()
                if key not in self._CONNINFO_URI_OR_POOL_KEYS and value is not None and str(value).strip() != ""
            }
            if query_params:
                conninfo = f"{conninfo}?{urlencode(query_params, quote_via=quote)}"

            self.pool = PsycopgConnectionPool(
                conninfo=conninfo,
                min_size=self.pool_size,
                max_size=self.pool_size,
                timeout=self.pool_timeout,
                max_idle=self.max_idle,
            )

            # Esperar a que el pool esté listo para entregar conexiones reales.
            wait_method = getattr(self.pool, "wait", None)
            if callable(wait_method):
                try:
                    wait_method(timeout=self.pool_timeout)
                except TypeError:
                    wait_method()

            self.logger.info(f"✅ Pool PostgreSQL (psycopg3) creado: {self.pool_size} conexiones")
        except Exception as e:
            self.logger.error(f"❌ Error creando pool PostgreSQL: {e}")
            raise

    def get_connection(self):
        """Obtiene conexión del pool.

        Returns:
            Conexión PostgreSQL lista para usar.

        Raises:
            Exception: Si no hay conexiones disponibles (timeout).
        """
        if self._closed:
            raise RuntimeError("Pool PostgreSQL cerrado")
        if not self.pool:
            raise RuntimeError("Pool PostgreSQL no inicializado")
        return self.pool.getconn()

    def close_connection(self, connection) -> None:
        """Devuelve conexión al pool.

        Args:
            connection: Conexión a devolver.
        """
        if not connection:
            return
        if self._closed:
            try:
                connection.close()
            except Exception:
                pass
            return
        if self.pool:
            self.pool.putconn(connection)

    def close(self, timeout_seconds: float | None = None, force: bool = False) -> None:
        """Cierra todas las conexiones del pool con timeout/forzado explícitos."""
        if self._closed:
            return
        self._closed = True
        if self.pool is None:
            return

        effective_timeout: float | None = self._close_timeout_seconds if timeout_seconds is None else timeout_seconds
        pool_ref = self.pool

        def _close_with_optional_timeout(close_timeout: float | None) -> None:
            # Durante la finalización del intérprete, psycopg_pool.close() intenta
            # unirse a sus threads internos y lanza PythonFinalizationError.
            # Python está terminando; el OS liberará los recursos.
            if sys.is_finalizing():
                return
            close_method = pool_ref.close
            if close_timeout is None:
                close_method()
                return
            try:
                close_method(timeout=close_timeout)
            except TypeError:
                close_method()

        try:
            run_close_operation_sync(
                action=lambda: _close_with_optional_timeout(effective_timeout),
                timeout_seconds=effective_timeout,
                action_name="cierre pool PostgreSQL",
                db_type="postgresql",
            )
            self.logger.info("✅ Pool PostgreSQL (psycopg3) cerrado")
        except PoolTimeoutError:
            if force is False:
                raise

            terminate = getattr(pool_ref, "terminate", None)
            if callable(terminate):

                def _terminate_pool() -> None:
                    _ = terminate()

                run_close_operation_sync(
                    action=_terminate_pool,
                    timeout_seconds=FORCE_CLOSE_TIMEOUT_SECONDS,
                    action_name="terminación forzada pool PostgreSQL",
                    db_type="postgresql",
                )
            else:
                run_close_operation_sync(
                    action=lambda: _close_with_optional_timeout(0.0),
                    timeout_seconds=FORCE_CLOSE_TIMEOUT_SECONDS,
                    action_name="reintento forzado pool PostgreSQL",
                    db_type="postgresql",
                )
            self.logger.info("✅ Pool PostgreSQL (psycopg3) cerrado (forzado)")
        except Exception as err:
            raise PoolConnectionError(
                message="Error cerrando pool PostgreSQL",
                db_type="postgresql",
                details=str(err),
            ) from err
        finally:
            self.pool = None
