"""Pool de conexiones para SQLite (simple pool wrapper)."""

import logging

from typing import Any, Literal, cast

from ...database_exceptions import DatabasePoolError, DatabasePoolTimeoutError
from ..close import FORCE_CLOSE_TIMEOUT_SECONDS, parse_close_timeout, run_close_operation_sync
from ..params import ConnectionParamsManager


class PoolConnection:
    """Pool simple de conexiones para SQLite.

    SQLite no soporta múltiples conexiones concurrentes de la misma manera que otros
    motores. Este pool mantiene una conexión principal y la reutiliza mediante
    un wrapper simple. Para aplicaciones con alta concurrencia, considerar usar
    otras bases de datos.

    Nota: pool_size en conn_params es ignorado (SQLite siempre usa 1 conexión)
    """

    def __init__(self, conn_params: dict[str, str]) -> None:
        """Inicializa pool simple para SQLite.

        Args:
            conn_params: Diccionario con parámetros de conexión:
                - database (str): Ruta a BD o ':memory:'
                - timeout (float, optional): Timeout en segundos (default: 5)
                - check_same_thread (bool, optional): Allow multi-thread access (default: false)
                - isolation_level (str, optional): DEFERRED, IMMEDIATE, EXCLUSIVE (default: None)
                - pool_size (int, optional): Ignorado para SQLite (siempre es 1)

        Raises:
            ValueError: Si faltan parámetros críticos.
            Exception: Si la creación de la conexión falla.

        Example:
            ```python
            conn_params = {
                "database": "./data/app.db",
                "timeout": 10,
                "check_same_thread": "false",
                "pool_size": 5  # Ignorado
            }
            pool = PoolConnection(conn_params)
            ```
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.connection: Any | None = None
        self._closed: bool = False
        self._close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))

        # pool_size se ignora para SQLite (siempre 1 conexión)
        self.pool_size: int = 1

        self.__create_pool(conn_params)

    def __del__(self) -> None:
        """Limpia recursos al destruir el objeto."""
        try:
            self.close(timeout_seconds=self._close_timeout_seconds, force=True)
        except Exception:
            pass  # No propagar excepciones desde destructor

    def __create_pool(self, conn_params: dict[str, str]) -> None:
        """Crea conexión principal para SQLite (pool simple).

        Args:
            conn_params: Parámetros de conexión.

        Raises:
            ValueError: Si faltan parámetros.
            Exception: Si la creación falla.
        """
        try:
            import sqlite3

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_pool(
                "sqlite",
                conn_params,
            )

            db_path: str = sanitized_conn_params.get("database", ":memory:")
            timeout = float(sanitized_conn_params.get("timeout", 5))
            check_same_thread: bool = bool(sanitized_conn_params.get("check_same_thread", False))
            isolation_level_raw: Literal["", "DEFERRED", "IMMEDIATE", "EXCLUSIVE"] = cast(
                Literal["", "DEFERRED", "IMMEDIATE", "EXCLUSIVE"],
                sanitized_conn_params.get("isolation_level", ""),
            )
            isolation_level: Literal["DEFERRED", "IMMEDIATE", "EXCLUSIVE"] | None = (
                None if isolation_level_raw == "" else isolation_level_raw
            )

            self.connection = sqlite3.connect(
                db_path,
                timeout=timeout,
                check_same_thread=check_same_thread,
                isolation_level=isolation_level,
            )

            # Habilitar foreign keys
            self.connection.execute("PRAGMA foreign_keys = ON")

            db_display = db_path if db_path != ":memory:" else "memory"
            self.logger.info(f"✅ Pool SQLite creado ({db_display}) - conexión única reutilizada")
        except Exception as e:
            self.logger.error(f"❌ Error creando pool SQLite: {e}")
            raise

    def get_connection(self) -> Any:
        """Obtiene la conexión principal (única para SQLite).

        Returns:
            Conexión SQLite lista para usar.

        Raises:
            RuntimeError: Si la conexión no está inicializada.
        """
        if self._closed:
            raise RuntimeError("Pool SQLite cerrado")
        if not self.connection:
            raise RuntimeError("Pool SQLite no inicializado")
        return self.connection

    def close_connection(self, connection: Any | None = None) -> None:
        """No cierra la conexión (se reutiliza).

        Args:
            connection: Ignorado (SQLite reutiliza la única conexión).
        """
        # SQLite pool simple: no cerramos, reutilizamos
        pass

    def close(self, timeout_seconds: float | None = None, force: bool = False) -> None:
        """Cierra la conexión principal con timeout/forzado explícitos."""
        if self._closed:
            return
        self._closed = True
        if self.connection is None:
            return

        effective_timeout: float | None = self._close_timeout_seconds if timeout_seconds is None else timeout_seconds
        connection_ref: Any = self.connection
        try:
            run_close_operation_sync(
                action=lambda: connection_ref.close(),
                timeout_seconds=effective_timeout,
                action_name="cierre pool SQLite",
                db_type="sqlite",
            )
            self.logger.info("✅ Pool SQLite cerrado")
        except DatabasePoolTimeoutError:
            if force is False:
                raise
            run_close_operation_sync(
                action=lambda: connection_ref.close(),
                timeout_seconds=FORCE_CLOSE_TIMEOUT_SECONDS,
                action_name="reintento forzado pool SQLite",
                db_type="sqlite",
            )
            self.logger.info("✅ Pool SQLite cerrado (forzado)")
        except Exception as err:
            raise DatabasePoolError(
                message="Error cerrando pool SQLite",
                db_type="sqlite",
                details=str(err),
            ) from err
        finally:
            self.connection = None
