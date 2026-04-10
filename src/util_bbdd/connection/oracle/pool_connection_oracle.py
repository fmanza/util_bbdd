"""Pool de conexiones para Oracle (oracledb)."""

import logging

from typing import Any

import oracledb

from ..._core.exceptions import PoolConnectionError, PoolTimeoutError
from ..close import FORCE_CLOSE_TIMEOUT_SECONDS, parse_close_timeout, run_close_operation_sync
from ..params import ConnectionParamsManager


class PoolConnection:
    """Pool de conexiones nativo para Oracle (oracledb).

    Extrae configuración del pool desde conn_params:
    - pool_size (int, default: 5): Número de conexiones en pool
    """

    def __init__(self, conn_params: dict[str, str]) -> None:
        """Inicializa pool nativo de oracledb.

        Args:
            conn_params: Diccionario con parámetros de conexión más configuración:
                - user (str): Usuario de BD
                - password (str): Contraseña
                - dsn (str, optional): DSN connection string O
                - host (str, optional): Host de BD (default: localhost)
                - port (int, optional): Puerto (default: 1521)
                - database (str, optional): SID (default: orcl)
                - oracle_client_path (str, optional): Ruta al cliente Oracle
                - pool_size (int, optional): Conexiones en pool (default: 5)

        Raises:
            ValueError: Si faltan parámetros críticos.
            Exception: Si la creación del pool falla.

        Example:
            ```python
            conn_params = {
                "user": "scott",
                "password": "tiger",
                "host": "localhost",
                "port": 1521,
                "database": "orcl",
                "pool_size": 10
            }
            pool = PoolConnection(conn_params)
            ```
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.pool: oracledb.ConnectionPool | None = None
        self._closed: bool = False
        self._close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))
        pool_config = ConnectionParamsManager.get_pool_config("oracle", conn_params)
        self.pool_size: int = pool_config.pool_size
        self.max_lifetime: int = pool_config.max_lifetime
        self.conn_params: dict[str, Any] = pool_config.to_driver_kwargs()
        self.__create_pool()

    def __del__(self) -> None:
        """Limpia recursos al destruir el objeto."""
        try:
            self.close(timeout_seconds=self._close_timeout_seconds, force=True)
        except Exception:
            pass  # No propagar excepciones desde destructor

    def __create_pool(self) -> None:
        """Crea pool nativo de oracledb.

        Raises:
            Exception: Si la creación del pool falla.
        """
        try:
            # Inicializar cliente Oracle si se proporciona path
            oracle_path: str | None = self.conn_params.get("oracle_client_path")
            if oracle_path:
                oracledb.init_oracle_client(oracle_path)

            # Construir DSN si no existe
            dsn_value: str | None = self.conn_params.get("dsn")
            if not dsn_value:
                host: str = self.conn_params.get("host", "localhost")
                port: int = self.conn_params.get("port", 1521)
                service_name: str | None = self.conn_params.get("service_name")
                sid: str | None = self.conn_params.get("sid")
                database: str | None = self.conn_params.get("database")

                if service_name:
                    dsn_value = oracledb.makedsn(host=host, port=port, service_name=service_name)
                elif sid:
                    dsn_value = oracledb.makedsn(host=host, port=port, sid=sid)
                elif database:
                    # Compatibilidad hacia atrás: interpretar 'database' como service_name
                    dsn_value = oracledb.makedsn(host=host, port=port, service_name=database)
                else:
                    raise ValueError(
                        "Para Oracle debe proporcionar 'dsn' o bien 'service_name'/'sid' (también se acepta 'database' como alias de service_name)."
                    )

            # Oracle requiere parámetros de sesiones válidos para el pool.
            # Usamos un pool escalable de 1..pool_size para evitar ORA-24413.
            min_sessions: int = 1
            max_sessions: int = self.pool_size
            increment_sessions: int = 1

            self.pool = oracledb.create_pool(
                user=self.conn_params.get("user"),
                password=self.conn_params.get("password"),
                dsn=dsn_value,
                min=min_sessions,
                max=max_sessions,
                increment=increment_sessions,
                getmode=oracledb.POOL_GETMODE_WAIT,
                max_lifetime_session=self.max_lifetime,
            )

            self.logger.info(f"✅ Pool Oracle creado: {self.pool_size} conexiones")
        except Exception as e:
            self.logger.error(f"❌ Error creando pool Oracle: {e}")
            raise

    def get_connection(self):
        """Obtiene conexión del pool.

        Returns:
            Conexión Oracle lista para usar.

        Raises:
            Exception: Si no hay conexiones disponibles.
        """
        if self._closed:
            raise RuntimeError("Pool Oracle cerrado")
        if not self.pool:
            raise RuntimeError("Pool Oracle no inicializado")
        return self.pool.acquire()

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
            self.pool.release(connection)

    def close(self, timeout_seconds: float | None = None, force: bool = False) -> None:
        """Cierra todas las conexiones del pool con timeout/forzado explícitos."""
        if self._closed:
            return
        self._closed = True
        if self.pool is None:
            return

        effective_timeout: float | None = self._close_timeout_seconds if timeout_seconds is None else timeout_seconds
        pool_ref: oracledb.ConnectionPool = self.pool
        try:
            run_close_operation_sync(
                action=lambda: pool_ref.close(),
                timeout_seconds=effective_timeout,
                action_name="cierre pool Oracle",
                db_type="oracle",
            )
            self.logger.info("✅ Pool Oracle cerrado")
        except PoolTimeoutError:
            if force is False:
                raise

            def _force_close() -> None:
                try:
                    pool_ref.close(force=True)
                except TypeError:
                    pool_ref.close()

            run_close_operation_sync(
                action=_force_close,
                timeout_seconds=FORCE_CLOSE_TIMEOUT_SECONDS,
                action_name="cierre forzado pool Oracle",
                db_type="oracle",
            )
            self.logger.info("✅ Pool Oracle cerrado (forzado)")
        except Exception as err:
            raise PoolConnectionError(
                message="Error cerrando pool Oracle",
                db_type="oracle",
                details=str(err),
            ) from err
        finally:
            self.pool = None
