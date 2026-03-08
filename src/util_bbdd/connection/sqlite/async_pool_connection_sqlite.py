"""Pool async para SQLite con conexión única y semáforo."""

from __future__ import annotations

import asyncio
import logging

from typing import Any

from .async_connection_sqlite import AsyncSQLiteConnection


class AsyncSQLitePool:
    """Pool async simple para SQLite."""

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, connection: Any) -> None:
        self._connection: Any = connection
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(1)
        self._closed: bool = False

    @classmethod
    async def create(cls, conn_params: dict[str, Any]) -> AsyncSQLitePool:
        """Crea el pool simple de SQLite con conexión única."""
        conn: Any = await AsyncSQLiteConnection.connect(conn_params)
        cls.logger.info("✅ Pool SQLite async creado (conexión única)")
        return cls(conn)

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

    async def aclose(self) -> None:
        """Cierra conexión y marca pool como cerrado."""
        if self._closed:
            return
        self._closed = True
        if self._connection is not None and hasattr(self._connection, "close"):
            await self._connection.close()
            self._connection = None
