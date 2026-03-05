"""Pool de conexiones para MariaDB (mariadb.ConnectionPool)."""

import logging
from typing import Optional
from uuid import uuid4

from mariadb import Connection, ConnectionPool

from ..connection_params_manager import ConnectionParamsManager


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
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.pool: Optional[ConnectionPool] = None
        self._closed: bool = False

        self.__create_pool(conn_params)

    def __del__(self) -> None:
        """Limpia recursos al destruir el objeto."""
        if self.pool is not None:
            try:
                self.pool.close()
            except Exception:
                pass  # Ignorar si ya fue cerrado

    def __create_pool(self, conn_params: dict[str, str | int]) -> None:
        """Crea pool nativo de MariaDB.

        Args:
            conn_params: Parámetros de conexión. Debe incluir user, password, host, database.
                         Extrae pool_size si está presente (default: 5).

        Raises:
            ValueError: Si faltan parámetros requeridos.
            Exception: Si la creación del pool falla.
        """
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
            self.pool = ConnectionPool(
                **sanitized_conn_params,
            )

            self.logger.info(
                f"✅ Pool MariaDB creado: {sanitized_conn_params.get('pool_size', 5)} conexiones (pool {pool_name})"
            )
        except Exception as e:
            self.logger.error(f"❌ Error creando pool MariaDB: {e}")
            raise

    def get_connection(self) -> Connection:
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

    def close_connection(self, connection: Connection) -> None:
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

    def close(self) -> None:
        """Cierra todas las conexiones del pool."""
        if self._closed:
            return
        self._closed = True
        if self.pool:
            try:
                self.pool.close()
                self.logger.info("✅ Pool MariaDB cerrado")
            except Exception as e:
                self.logger.warning(f"⚠️  Error cerrando pool MariaDB: {e}")
            finally:
                self.pool = None
