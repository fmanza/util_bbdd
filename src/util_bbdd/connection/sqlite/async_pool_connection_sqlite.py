"""Pool async para SQLite con conexión única y semáforo."""

from __future__ import annotations

import asyncio
import logging

from typing import Any

from ..close import (
    FORCE_CLOSE_TIMEOUT_SECONDS,
    AsyncCloseMode,
    normalize_close_mode,
    parse_close_timeout,
    run_close_operation_async,
)
from .async_connection_sqlite import AsyncSQLiteConnection


class AsyncSQLitePool:
    """Pool async simple para SQLite."""

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, connection: Any, close_timeout_seconds: float | None) -> None:
        self._connection: Any = connection
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(1)
        self._closed: bool = False
        self._close_timeout_seconds: float | None = close_timeout_seconds

    @classmethod
    async def create(cls, conn_params: dict[str, Any]) -> AsyncSQLitePool:
        """Crea el pool simple de SQLite con conexión única."""
        conn: Any = await AsyncSQLiteConnection.connect(conn_params)
        cls.logger.info("✅ Pool SQLite async creado (conexión única)")
        close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))
        return cls(conn, close_timeout_seconds=close_timeout_seconds)

    async def acquire(self) -> Any:
        """Adquiere la conexión única de SQLite."""
        if self._closed:
            raise RuntimeError("Pool SQLite async cerrado")
        await self._semaphore.acquire()
        return self._connection

    async def release(self, _connection: Any) -> None:
        """Libera la conexión única de SQLite."""
        if self._closed:
            return
        self._semaphore.release()
        # Mantiene contrato async (AsyncPoolProtocol) y evita warning de función async sin await
        await asyncio.sleep(0)

    async def close(self, mode: AsyncCloseMode | str = "immediate") -> None:
        """Cierra conexión y marca pool como cerrado."""
        if self._closed:
            return
        self._closed = True
        close_mode: AsyncCloseMode = normalize_close_mode(mode)
        if self._connection is not None and hasattr(self._connection, "close"):
            effective_timeout = (
                FORCE_CLOSE_TIMEOUT_SECONDS if close_mode == "immediate" else self._close_timeout_seconds
            )
            await run_close_operation(
                self._connection.close(),
                effective_timeout,
                self.logger,
                "cierre pool SQLite async",
            )
            self._connection = None
