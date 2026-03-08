"""Tests de ciclo de vida para AsyncDatabaseManager."""

from __future__ import annotations

import asyncio

from util_bbdd import AsyncDatabaseManager
from util_bbdd.connection.connect_factory import ConnectFactory
from util_bbdd.factory.pool_factory import PoolFactory


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False
        self.last_sql = None
        self.last_params = None

    async def execute(self, query: str, params=None):
        self.last_sql = query
        self.last_params = params

    async def fetchone(self):
        return ("one",)

    async def fetchall(self):
        return [("many",)]

    async def close(self) -> None:
        self.closed = True


class FakePool:
    def __init__(self) -> None:
        self.closed = False
        self.released = 0
        self.connection = FakeConnection()

    async def acquire(self):
        return self.connection

    async def release(self, connection) -> None:
        self.released += 1

    async def aclose(self) -> None:
        self.closed = True


def test_async_manager_direct_lifecycle() -> None:
    db_type = "test_async_manager_direct"
    created: dict[str, FakeConnection] = {}

    async def builder(conn_params, **kwargs):
        conn = FakeConnection()
        created["conn"] = conn
        return conn

    ConnectFactory.register_async_connection(db_type, builder)

    async def _run() -> None:
        manager = AsyncDatabaseManager(db_type=db_type, conn_params={}, use_pool=False)
        rows = await manager.execute_custom_query("SELECT 1")
        assert rows == [("many",)]
        await manager.aclose()
        assert created["conn"].closed is True

    asyncio.run(_run())


def test_async_manager_pool_lifecycle() -> None:
    db_type = "test_async_manager_pool"
    created: dict[str, FakePool] = {}

    async def pool_builder(conn_params, **kwargs):
        pool = FakePool()
        created["pool"] = pool
        return pool

    PoolFactory.register_async_pool(db_type, pool_builder)

    async def _run() -> None:
        manager = AsyncDatabaseManager(db_type=db_type, conn_params={}, use_pool=True)
        row = await manager.execute_custom_query("SELECT 1", fetch_one=True)
        assert row == ("one",)
        assert created["pool"].released == 1
        await manager.aclose()
        assert created["pool"].closed is True

    asyncio.run(_run())
