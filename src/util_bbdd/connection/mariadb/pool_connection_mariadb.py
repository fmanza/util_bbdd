"""Pool de conexiones para MariaDB (mariadb.ConnectionPool)."""

import logging
import re

from typing import Any
from uuid import uuid4

try:
    import mariadb

    HAS_MARIADB = True
except ImportError:
    mariadb = None
    HAS_MARIADB = False

from ..._core.exceptions import PoolConnectionError, PoolTimeoutError
from ..close import (
    DEFAULT_CLOSE_TIMEOUT_SECONDS,
    FORCE_CLOSE_TIMEOUT_SECONDS,
    SyncPoolCloseMixin,
    run_close_operation_sync,
)
from ..params import ConnectionParamsManager

# Parámetros que el pool puede rechazar según versión del driver; se eliminan uno a uno si procede.
_OPTIONAL_POOL_PARAMS: frozenset[str] = frozenset({"init_command"})


class PoolConnection(SyncPoolCloseMixin):
    """Pool de conexiones nativo para MariaDB.

    Extrae configuración del pool desde conn_params:
    - pool_size (int, default: 5): Número de conexiones en pool
    """

    def __init__(self, conn_params: dict[str, str | int]) -> None:
        """Inicializa pool nativo de MariaDB.

        Args:
            conn_params: Diccionario con parámetros de conexión más configuración:
                - user (str): Usuario de BD
                - password (str): Contraseña
                - host (str): Host de BD
                - database (str): Nombre de base de datos
                - port (int, optional): Puerto (default: 3306)
                - pool_size (int, optional): Conexiones en pool (default: 5)
                - pool_name (str, optional): Nombre del pool. Si no se indica, se genera automáticamente uno único por instancia.

        Raises:
            ValueError: Si faltan parámetros críticos.
            Exception: Si la creación del pool falla.

        Example:
            ```python
            conn_params = {
                "user": "root",
                "password": "password",
                "host": "localhost",
                "database": "mydb",
                "port": 3306,
                "pool_size": 10,
                "pool_name": "pool_app_local"
            }
            pool = PoolConnection(conn_params)
            ```
        """
        if not HAS_MARIADB:
            raise ImportError("Módulo 'mariadb' no está instalado. Instale con: pip install mariadb")

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.pool: Any | None = None
        self._closed: bool = False
        self._pending_init_command: str | None = None
        # Valor provisional hasta validar la config en __create_pool (lo usa __del__ si la creación falla).
        self._close_timeout_seconds: float | None = DEFAULT_CLOSE_TIMEOUT_SECONDS

        self.__create_pool(conn_params)

    def __create_pool(self, conn_params: dict[str, str | int]) -> None:
        """Crea pool nativo de MariaDB.

        Args:
            conn_params: Parámetros de conexión. Debe incluir user, password, host, database.
                         Extrae pool_size si está presente (default: 5).

        Raises:
            ValueError: Si faltan parámetros requeridos.
            Exception: Si la creación del pool falla.
        """
        if mariadb is None:
            raise ImportError("Módulo 'mariadb' no está instalado. Instale con: pip install mariadb")

        try:
            pool_config = ConnectionParamsManager.get_pool_config("mariadb", conn_params)
            self._close_timeout_seconds = pool_config.close_timeout
            sanitized_conn_params: dict[str, str | int] = ConnectionParamsManager.sanitize_for_pool(
                "mariadb",
                conn_params,
            )

            pool_name: str = str(sanitized_conn_params.get("pool_name", "")).strip()
            if not pool_name:
                pool_name = f"pool_{uuid4().hex[:12]}"
                sanitized_conn_params["pool_name"] = pool_name

            # Preparar pool_params
            # mariadb.ConnectionPool no admite charset (comprobado en 1.1.14, la última); lo usa el pool async (aiomysql)
            pool_params: dict[str, str | int] = {k: v for k, v in sanitized_conn_params.items() if k != "charset"}

            # Crear pool; reintentar eliminando kwargs opcionales rechazados por el driver
            for _ in range(len(_OPTIONAL_POOL_PARAMS) + 1):
                try:
                    self.pool = mariadb.ConnectionPool(**pool_params)
                    break
                except TypeError as err:
                    msg = str(err)
                    if "unexpected keyword argument" not in msg:
                        raise
                    match = re.search(r"unexpected keyword argument '(\w+)'", msg)
                    if not match or match.group(1) not in _OPTIONAL_POOL_PARAMS:
                        raise
                    rejected = match.group(1)
                    mariadb_version: str = str(getattr(mariadb, "__version__", "?"))
                    # Si driver rechaza init_command, extraerlo y ejecutar manual en get_connection()
                    if rejected == "init_command":
                        self._pending_init_command = str(pool_params.pop("init_command", "")) or None
                        self.logger.warning(
                            f"⚠️ mariadb.ConnectionPool() rechazó 'init_command'; "
                            f"ejecutaremos manualmente en get_connection() (mariadb version={mariadb_version})"
                        )
                    else:
                        # Otros parámetros opcionales rechazados por la versión instalada del driver
                        pool_params = {k: v for k, v in pool_params.items() if k != rejected}
                        self.logger.warning(
                            f"⚠️ mariadb.ConnectionPool() rechazó '{rejected}'; "
                            f"reintentando sin él (mariadb version={mariadb_version})"
                        )
            else:
                raise RuntimeError("No se pudo crear el pool de MariaDB; parámetros opcionales agotados")

            self.logger.info(
                f"✅ Pool MariaDB creado: {sanitized_conn_params.get('pool_size', 5)} conexiones (pool {pool_name})"
            )
        except Exception as e:
            self.logger.error(f"❌ Error creando pool MariaDB: {e}")
            raise

    def get_connection(self) -> Any:
        """Obtiene conexión del pool.

        Returns:
            Conexión MariaDB lista para usar.

        Raises:
            Exception: Si no hay conexiones disponibles o falla el ``init_command`` manual (la conexión vuelve al
                pool: entregarla dejaría la sesión sin configurar, p. ej. sin ``SET NAMES utf8mb4``).
        """
        if self._closed:
            raise RuntimeError("Pool MariaDB cerrado")
        if not self.pool:
            raise RuntimeError("Pool MariaDB no inicializado")
        conn = self.pool.get_connection()
        if self._pending_init_command:
            try:
                cursor = conn.cursor()
                try:
                    cursor.execute(self._pending_init_command)
                finally:
                    cursor.close()
            except Exception as exc:
                self.logger.error(f"❌ init_command manual falló; la conexión vuelve al pool: {exc}")
                conn.close()
                raise
        return conn

    def _return_to_pool(self, connection: Any) -> None:
        """Devuelve la conexión al pool nativo."""
        connection.close()

    def close(self, timeout_seconds: float | None = None, force: bool = False) -> None:
        """Cierra todas las conexiones del pool con timeout/forzado explícitos."""
        if self._closed:
            return
        self._closed = True
        if self.pool is None:
            return

        effective_timeout: float | None = self._close_timeout_seconds if timeout_seconds is None else timeout_seconds
        pool_ref: Any = self.pool
        try:
            run_close_operation_sync(
                action=lambda: pool_ref.close(),
                timeout_seconds=effective_timeout,
                action_name="cierre pool MariaDB",
                db_type="mariadb",
            )
            self.logger.info("✅ Pool MariaDB cerrado")
        except PoolTimeoutError as err:
            if force is False:
                raise
            terminate = getattr(pool_ref, "terminate", None)
            if not callable(terminate):
                raise PoolConnectionError(
                    message="Pool MariaDB no soporta cierre forzado",
                    db_type="mariadb",
                ) from err

            def _terminate_pool() -> None:
                _ = terminate()

            run_close_operation_sync(
                action=_terminate_pool,
                timeout_seconds=FORCE_CLOSE_TIMEOUT_SECONDS,
                action_name="terminación forzada pool MariaDB",
                db_type="mariadb",
            )
            self.logger.info("✅ Pool MariaDB cerrado (forzado)")
        finally:
            self.pool = None
