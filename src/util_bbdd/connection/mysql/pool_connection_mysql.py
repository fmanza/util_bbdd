"""Pool de conexiones para MySQL: ``QueuePool`` de SQLAlchemy sobre ``pymysql.connect``.

PyMySQL no tiene pool nativo. ``QueuePool`` aporta tamaño, desbordamiento, espera, reciclado y
``pre_ping``; las conexiones que entrega son proxies que devuelven la conexión al pool al cerrarse.
"""

from __future__ import annotations

import logging

from typing import Any

from sqlalchemy import exc as sa_exc
from sqlalchemy.dialects.mysql.pymysql import MySQLDialect_pymysql
from sqlalchemy.pool import QueuePool

from ..._core.exceptions import PoolTimeoutError
from ..close import parse_close_timeout, run_close_operation_sync
from ..params import ConnectionParamsManager
from .connection_mysql import build_pymysql_connect_kwargs


class PoolConnection:
    """Pool de conexiones MySQL (``QueuePool`` de SQLAlchemy).

    Extrae configuración del pool desde conn_params:
    - pool_size (int, default: 5): conexiones que el pool mantiene
    - max_overflow (int, default: 10): conexiones adicionales permitidas
    - pool_timeout (int, default: 30): segundos de espera por una conexión libre
    - pool_recycle (int, default: 3600): segundos tras los que se recicla una conexión
    """

    def __init__(self, conn_params: dict[str, Any]) -> None:
        """Inicializa el pool MySQL.

        Args:
            conn_params: Parámetros de conexión (host, user, password, database, port...) más
                pool_size, max_overflow, pool_timeout, pool_recycle y close_timeout opcionales.

        Raises:
            ImportError: Si PyMySQL no está instalado.
            ValueError: Si faltan parámetros requeridos o son inválidos.

        Example:
            ```python
            pool = PoolConnection(
                {"host": "localhost", "user": "app", "password": "pw", "database": "mydb", "pool_size": 10}
            )
            conn = pool.get_connection()
            pool.close_connection(conn)
            pool.close()
            ```
        """
        try:
            import pymysql
        except ImportError as err:
            raise ImportError("Módulo 'pymysql' no está instalado. Instale con: pip install pymysql[rsa]") from err

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.pool: QueuePool | None = None
        self._closed: bool = False
        self._close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))

        pool_config = ConnectionParamsManager.get_pool_config("mysql", conn_params)
        connect_kwargs: dict[str, Any] = build_pymysql_connect_kwargs(pool_config.connection.to_driver_kwargs())
        self._pool_timeout: int = pool_config.pool_timeout

        def _creator() -> Any:
            return pymysql.connect(**connect_kwargs)

        self.pool = QueuePool(
            _creator,
            pool_size=pool_config.pool_size,
            max_overflow=pool_config.max_overflow,
            timeout=pool_config.pool_timeout,
            recycle=pool_config.pool_recycle,
            pre_ping=True,
            # pre_ping hace el ping a través del dialecto; sin él QueuePool no puede comprobar la conexión.
            dialect=MySQLDialect_pymysql(),
        )
        self.logger.info(
            f"✅ Pool MySQL creado: {pool_config.pool_size} conexiones (+{pool_config.max_overflow} de desbordamiento)"
        )

    def __del__(self) -> None:
        """Limpia recursos al destruir el objeto."""
        try:
            self.close(timeout_seconds=self._close_timeout_seconds, force=True)
        except Exception:
            pass  # No propagar excepciones desde destructor

    def get_connection(self) -> Any:
        """Obtiene conexión del pool.

        Returns:
            Proxy de conexión PyMySQL; ``close()`` la devuelve al pool.

        Raises:
            RuntimeError: Si el pool está cerrado o no inicializado.
            PoolTimeoutError: Si no hay conexión libre en ``pool_timeout`` segundos.
        """
        if self._closed:
            raise RuntimeError("Pool MySQL cerrado")
        if self.pool is None:
            raise RuntimeError("Pool MySQL no inicializado")
        try:
            return self.pool.connect()
        except sa_exc.TimeoutError as err:
            raise PoolTimeoutError(
                timeout_seconds=float(self._pool_timeout),
                operation="get_connection",
                db_type="mysql",
            ) from err

    def close_connection(self, connection: Any) -> None:
        """Devuelve la conexión al pool (o la cierra si el pool ya está cerrado).

        Args:
            connection: Conexión a devolver.
        """
        if not connection:
            return
        try:
            connection.close()
        except Exception:
            if not self._closed:
                raise

    def close(self, timeout_seconds: float | None = None, force: bool = False) -> None:
        """Cierra todas las conexiones del pool.

        ``QueuePool.dispose()`` cierra las conexiones libres y no espera a las prestadas, así que no hay cierre
        forzado distinto del normal: ``force`` solo evita propagar el timeout.
        """
        if self._closed:
            return
        self._closed = True
        if self.pool is None:
            return

        effective_timeout: float | None = self._close_timeout_seconds if timeout_seconds is None else timeout_seconds
        pool_ref: QueuePool = self.pool
        try:
            run_close_operation_sync(
                action=pool_ref.dispose,
                timeout_seconds=effective_timeout,
                action_name="cierre pool MySQL",
                db_type="mysql",
            )
            self.logger.info("✅ Pool MySQL cerrado")
        except PoolTimeoutError:
            if force is False:
                raise
            self.logger.warning("⚠️ Cierre del pool MySQL fuera de tiempo; se abandona (forzado)")
        finally:
            self.pool = None
