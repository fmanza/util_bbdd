"""Pool de conexiones para MariaDB (mariadb.ConnectionPool)."""

import logging

from typing import Any
from uuid import uuid4

try:
    import mariadb

    HAS_MARIADB = True
except ImportError:
    mariadb = None
    HAS_MARIADB = False

from ..._core.exceptions import PoolConnectionError, PoolTimeoutError
from ..close import FORCE_CLOSE_TIMEOUT_SECONDS, parse_close_timeout, run_close_operation_sync
from ..params import ConnectionParamsManager


class PoolConnection:
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
        self._close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))

        self.__create_pool(conn_params)

    def __del__(self) -> None:
        """Limpia recursos al destruir el objeto."""
        try:
            self.close(timeout_seconds=self._close_timeout_seconds, force=True)
        except Exception:
            pass  # No propagar excepciones desde destructor

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
            ConnectionParamsManager.get_pool_config("mariadb", conn_params)
            sanitized_conn_params: dict[str, str | int] = ConnectionParamsManager.sanitize_for_pool(
                "mariadb",
                conn_params,
            )

            pool_name: str = str(sanitized_conn_params.get("pool_name", "")).strip()
            if not pool_name:
                pool_name = f"pool_{uuid4().hex[:12]}"
                sanitized_conn_params["pool_name"] = pool_name

            # Crear pool con parámetros
            self.pool = mariadb.ConnectionPool(
                **sanitized_conn_params,
            )

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
            Exception: Si no hay conexiones disponibles.
        """
        if self._closed:
            raise RuntimeError("Pool MariaDB cerrado")
        if not self.pool:
            raise RuntimeError("Pool MariaDB no inicializado")
        return self.pool.get_connection()

    def close_connection(self, connection: Any) -> None:
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
        if connection:
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
