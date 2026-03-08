"""Pool async para SQL Server basado en aioodbc."""

from __future__ import annotations

import inspect
import logging

from typing import Any

from util_bbdd.database_exceptions import DatabaseConnectionError

from ..connection_params_manager import ConnectionParamsManager
from .async_connection_sqlserver import AsyncSQLServerConnection


class AsyncSQLServerPool:
    """Pool de conexiones async para SQL Server."""

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, pool: Any):
        self._pool: Any = pool

    @classmethod
    async def create(cls, conn_params: dict[str, Any]) -> AsyncSQLServerPool:
        """Crea un pool async de SQL Server."""
        try:
            import aioodbc

            pool_config = ConnectionParamsManager.get_pool_config("sqlserver", conn_params)
            sanitized_pool_params: dict[str, Any] = pool_config.to_driver_kwargs()

            dsn: str = AsyncSQLServerConnection._build_dsn(sanitized_pool_params)
            pool_size: int = int(sanitized_pool_params.get("pool_size", 5))
            max_overflow: int = int(sanitized_pool_params.get("max_overflow", 10))
            pool_timeout: int = int(sanitized_pool_params.get("pool_timeout", 30))

            cls.logger.debug(f"🔗 Creando pool SQL Server async (min={pool_size}, max={pool_size + max_overflow})")
            pool: Any = await aioodbc.create_pool(
                dsn=dsn,
                minsize=pool_size,
                maxsize=pool_size + max_overflow,
                timeout=pool_timeout,
            )
            cls.logger.info("✅ Pool SQL Server async creado")
            return cls(pool)
        except ImportError as err:
            cls.logger.error("❌ Error: módulo aioodbc no disponible")
            raise DatabaseConnectionError("Módulo aioodbc no disponible", "sqlserver", str(err)) from err
        except Exception as err:
            cls.logger.error(f"❌ Error creando pool SQL Server async: {err}")
            raise DatabaseConnectionError(
                f"Error creando pool SQL Server async: {str(err)}",
                "sqlserver",
                str(err),
            ) from err

    async def acquire(self) -> Any:
        """Obtiene conexión del pool."""
        return await self._pool.acquire()

    async def release(self, connection: Any) -> None:
        """Devuelve conexión al pool."""
        result = self._pool.release(connection)
        if inspect.isawaitable(result):
            await result

    async def aclose(self) -> None:
        """Cierra pool async."""
        self._pool.close()
        await self._pool.wait_closed()
