"""Pool async para SQL Server basado en aioodbc."""

from __future__ import annotations

import inspect
import logging

from typing import Any

from util_bbdd._foundation.exceptions import DatabaseConnectionError

from ...async_utils import maybe_await
from ..close import (
    FORCE_CLOSE_TIMEOUT_SECONDS,
    AsyncCloseMode,
    normalize_close_mode,
    parse_close_timeout,
    run_close_operation_async,
)
from ..params import ConnectionParamsManager
from .async_connection_sqlserver import AsyncSQLServerConnection


class AsyncSQLServerPool:
    """Pool de conexiones async para SQL Server."""

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, pool: Any, close_timeout_seconds: float | None):
        self._pool: Any = pool
        self._close_timeout_seconds: float | None = close_timeout_seconds
        self._closed: bool = False

    @classmethod
    async def create(cls, conn_params: dict[str, Any]) -> AsyncSQLServerPool:
        """Crea un pool async de SQL Server."""
        try:
            import aioodbc

            pool_config = ConnectionParamsManager.get_pool_config("sqlserver", conn_params)
            sanitized_pool_params: dict[str, Any] = pool_config.to_driver_kwargs()
            close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))

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
            return cls(pool, close_timeout_seconds=close_timeout_seconds)
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

    async def close(self, mode: AsyncCloseMode | str = "immediate") -> None:
        """Cierra pool async en modo inmediato o graceful."""
        if self._closed:
            return
        self._closed = True
        close_mode: AsyncCloseMode = normalize_close_mode(mode)

        async def _force_close() -> None:
            terminate = getattr(self._pool, "terminate", None)
            if callable(terminate):
                terminate()
            else:
                self.logger.warning("⚠️ Pool SQL Server async no expone terminate(); reintentando close()")
                self._pool.close()

            wait_closed = getattr(self._pool, "wait_closed", None)
            if callable(wait_closed):
                await run_close_operation_async(
                    maybe_await(wait_closed()),
                    FORCE_CLOSE_TIMEOUT_SECONDS,
                    "espera tras cierre inmediato pool SQL Server async",
                    "sqlserver",
                )

        if close_mode == "immediate":
            await _force_close()
            return

        async def _graceful_close() -> None:
            self._pool.close()
            await maybe_await(self._pool.wait_closed())

        closed: bool = await run_close_operation_async(
            _graceful_close(),
            self._close_timeout_seconds,
            "cierre pool SQL Server async",
            "sqlserver",
        )
        if closed:
            return

        await _force_close()
