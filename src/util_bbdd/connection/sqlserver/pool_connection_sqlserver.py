"""Pool de conexiones para SQL Server (pymssql/pyodbc)."""

import logging

from queue import Empty, LifoQueue
from threading import Lock
from typing import Any

from ..._core.exceptions import PoolConnectionError, PoolTimeoutError
from ..close import FORCE_CLOSE_TIMEOUT_SECONDS, SyncPoolCloseMixin, run_close_operation_sync
from ..params import ConnectionParamsManager
from ..sqlserver.connection_sqlserver import SQLServerConnection


class PoolConnection(SyncPoolCloseMixin):
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
        self._leased_connections: dict[int, Any] = {}
        self._closed: bool = False
        self._close_timeout_seconds: float | None = pool_config.close_timeout

        self.__create_pool()

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
            self.close(timeout_seconds=self._close_timeout_seconds, force=True)
            raise

    def get_connection(self) -> Any:
        """Obtiene conexión del pool.

        Returns:
            Conexión SQL Server lista para usar.

        Raises:
            RuntimeError: Si el pool fue cerrado.
            PoolTimeoutError: Si no hay conexión libre en ``pool_timeout`` segundos.
        """
        if self._closed:
            raise RuntimeError("Pool SQL Server cerrado")

        try:
            connection = self._available.get_nowait()
            with self._lock:
                self._leased_connections[id(connection)] = connection
            return connection
        except Empty:
            pass

        max_connections: int = self.pool_size + self.max_overflow

        # Se reserva el hueco con el lock y se conecta fuera: abrir la conexión de red con el lock cogido bloqueaba
        # a todos los que pedían conexión mientras durara el login.
        with self._lock:
            if self._closed:
                raise RuntimeError("Pool SQL Server cerrado")
            reserved: bool = self._total_connections < max_connections
            if reserved:
                self._total_connections += 1

        if reserved:
            try:
                connection = self._create_connection()
            except Exception:
                with self._lock:
                    self._total_connections -= 1
                raise
            with self._lock:
                self._leased_connections[id(connection)] = connection
            return connection

        # Esperar devolución de conexión cuando ya alcanzó límite total
        try:
            connection = self._available.get(timeout=self.pool_timeout)
            with self._lock:
                self._leased_connections[id(connection)] = connection
            return connection
        except Empty as e:
            raise PoolTimeoutError(
                timeout_seconds=float(self.pool_timeout),
                operation="get_connection",
                db_type="sqlserver",
            ) from e

    def _forget_connection(self, connection: Any) -> None:
        """Saca la conexión del registro de prestadas (también si el pool ya está cerrado)."""
        with self._lock:
            self._leased_connections.pop(id(connection), None)

    def _return_to_pool(self, connection: Any) -> None:
        """Devuelve la conexión a la cola, o la cierra si es de desbordamiento."""
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

    def _collect_available_connections(self) -> list[Any]:
        available_connections: list[Any] = []
        while True:
            try:
                available_connections.append(self._available.get_nowait())
            except Empty:
                return available_connections

    def _collect_and_reset_leased_connections(self) -> list[Any]:
        with self._lock:
            leased_connections = list(self._leased_connections.values())
            self._leased_connections.clear()
            self._total_connections = 0
        return leased_connections

    def _close_with_timeout(self, connection: Any, timeout_seconds: float | None, action_name: str) -> None:
        def _close_connection() -> None:
            connection.close()

        run_close_operation_sync(
            action=_close_connection,
            timeout_seconds=timeout_seconds,
            action_name=action_name,
            db_type="sqlserver",
        )

    def _handle_close_timeout(self, connection: Any, force: bool, err: PoolTimeoutError) -> str | None:
        if force is False:
            return str(err)
        try:
            self._close_with_timeout(
                connection=connection,
                timeout_seconds=FORCE_CLOSE_TIMEOUT_SECONDS,
                action_name="reintento forzado conexión pool SQL Server",
            )
            return None
        except Exception as force_err:
            return str(force_err)

    def _close_single_connection(self, connection: Any, timeout_seconds: float | None, force: bool) -> str | None:
        try:
            self._close_with_timeout(
                connection=connection,
                timeout_seconds=timeout_seconds,
                action_name="cierre conexión pool SQL Server",
            )
            return None
        except PoolTimeoutError as err:
            return self._handle_close_timeout(connection=connection, force=force, err=err)
        except Exception as err:
            return str(err)

    def close(self, timeout_seconds: float | None = None, force: bool = False) -> None:
        """Cierra todas las conexiones (disponibles y prestadas) con timeout/forzado explícitos."""
        if self._closed:
            return

        self._closed = True
        effective_timeout: float | None = self._close_timeout_seconds if timeout_seconds is None else timeout_seconds
        errors: list[str] = []

        all_connections = self._collect_available_connections() + self._collect_and_reset_leased_connections()

        for connection in all_connections:
            error: str | None = self._close_single_connection(
                connection=connection,
                timeout_seconds=effective_timeout,
                force=force,
            )
            if error is not None:
                errors.append(error)

        if errors:
            raise PoolConnectionError(
                message="Errores cerrando pool SQL Server",
                db_type="sqlserver",
                details=" | ".join(errors),
            )

        self.logger.info("✅ Pool SQL Server cerrado")
