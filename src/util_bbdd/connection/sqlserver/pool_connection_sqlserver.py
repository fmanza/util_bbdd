"""Pool de conexiones para SQL Server (pymssql/pyodbc)."""

import logging
from queue import Empty, LifoQueue
from threading import Lock
from typing import Any

from ..connection_params_manager import ConnectionParamsManager
from ..sqlserver.connection_sqlserver import SQLServerConnection


class PoolConnection:
    """Pool de conexiones nativo para SQL Server (pymssql/pyodbc).

    Extrae configuración del pool desde conn_params:
    - sql_server_driver (str, default: 'pymssql'): Driver a usar
    - pool_size (int, default: 5): Número mínimo de conexiones
    - max_overflow (int, default: 10): Conexiones adicionales permitidas
    - pool_timeout (int, default: 30): Timeout en segundos
    """

    def __init__(self, conn_params: dict[str, str | int]) -> None:
        """Inicializa pool nativo para SQL Server.

        Args:
            conn_params: Diccionario con parámetros de conexión más configuración:
                - host (str): Host de BD
                - user (str): Usuario de BD
                - password (str): Contraseña
                - database (str): Nombre de base de datos
                - port (int, optional): Puerto (default: 1433)
                - sql_server_driver (str, optional): 'pymssql' o 'pyodbc' (default: pymssql)
                - driver_name (str, optional): Driver ODBC si usa pyodbc (default: ODBC Driver 17 for SQL Server)
                - pool_size (int, optional): Min conexiones en pool (default: 5)
                - max_overflow (int, optional): Conexiones adicionales (default: 10)
                - pool_timeout (int, optional): Timeout en segundos (default: 30)

        Raises:
            ValueError: Si el driver no es válido o faltan parámetros críticos.
            Exception: Si la creación del pool falla.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        pool_config = ConnectionParamsManager.get_pool_config("sqlserver", conn_params)
        self.driver: str = pool_config.connection.sql_server_driver
        self.conn_params: dict[str, str | int | bool] = pool_config.to_driver_kwargs()

        self.pool_size: int = pool_config.pool_size
        self.max_overflow: int = pool_config.max_overflow
        self.pool_timeout: int = pool_config.pool_timeout

        self._available: LifoQueue[Any] = LifoQueue(maxsize=self.pool_size)
        self._lock: Lock = Lock()
        self._total_connections: int = 0
        self._closed: bool = False

        self.__create_pool()

    def __del__(self) -> None:
        """Limpia recursos al destruir el objeto."""
        try:
            self.close()
        except Exception:
            pass

    def _create_connection(self) -> Any:
        """Crea una conexión raw SQL Server usando el driver configurado."""
        return SQLServerConnection.connect(self.conn_params, self.driver)

    def __create_pool(self) -> None:
        """Crea pool nativo de conexiones SQL Server.

        Raises:
            Exception: Si la creación del pool falla.
        """
        try:
            created: int = 0
            while created < self.pool_size:
                connection = self._create_connection()
                self._available.put_nowait(connection)
                created += 1

            self._total_connections = created
            self.logger.info(
                f"✅ Pool SQL Server ({self.driver}) creado: {self.pool_size} conexiones iniciales + {self.max_overflow} overflow"
            )
        except Exception as e:
            self.logger.error(f"❌ Error creando pool SQL Server: {e}")
            self.close()
            raise

    def get_connection(self) -> Any:
        """Obtiene conexión del pool.

        Returns:
            Conexión SQL Server lista para usar.

        Raises:
            RuntimeError: Si el pool fue cerrado.
            Exception: Si no hay conexiones disponibles (timeout).
        """
        if self._closed:
            raise RuntimeError("Pool SQL Server cerrado")

        try:
            return self._available.get_nowait()
        except Empty:
            pass

        max_connections: int = self.pool_size + self.max_overflow

        with self._lock:
            if self._closed:
                raise RuntimeError("Pool SQL Server cerrado")

            if self._total_connections < max_connections:
                connection = self._create_connection()
                self._total_connections += 1
                return connection

        # Esperar devolución de conexión cuando ya alcanzó límite total
        try:
            return self._available.get(timeout=self.pool_timeout)
        except Empty as e:
            raise TimeoutError(
                f"Timeout obteniendo conexión SQL Server tras {self.pool_timeout}s "
                f"(pool_size={self.pool_size}, max_overflow={self.max_overflow})"
            ) from e

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

        try:
            self._available.put_nowait(connection)
        except Exception:
            # Si la cola base está llena, cerramos esta conexión de overflow.
            try:
                connection.close()
            finally:
                with self._lock:
                    if self._total_connections > 0:
                        self._total_connections -= 1

    def close(self) -> None:
        """Cierra todas las conexiones del pool."""
        if self._closed:
            return

        self._closed = True
        errors: list[str] = []

        while True:
            try:
                connection = self._available.get_nowait()
            except Empty:
                break

            try:
                connection.close()
            except Exception as e:
                errors.append(str(e))

        with self._lock:
            self._total_connections = 0

        if errors:
            self.logger.warning(f"⚠️  Errores cerrando pool SQL Server: {errors}")
        else:
            self.logger.info("✅ Pool SQL Server cerrado")

