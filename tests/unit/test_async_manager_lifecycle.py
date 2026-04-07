"""Tests de ciclo de vida para AsyncDatabaseManager."""

from __future__ import annotations

import asyncio

import pytest

from util_bbdd import AsyncDatabaseManager


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False
        self.last_sql = None
        self.last_params = None

    async def execute(self, query: str, params=None):
        await asyncio.sleep(0)
        self.last_sql = query
        self.last_params = params

    async def fetchone(self):
        await asyncio.sleep(0)
        return ("one",)

    async def fetchall(self):
        await asyncio.sleep(0)
        return [("many",)]

    async def close(self) -> None:
        await asyncio.sleep(0)
        self.closed = True


class FakePool:
    def __init__(self) -> None:
        self.closed = False
        self.released = 0
        self.connection = FakeConnection()

    async def acquire(self):
        await asyncio.sleep(0)
        return self.connection

    async def release(self, connection) -> None:
        await asyncio.sleep(0)
        self.released += 1

    async def close(self, mode: str) -> None:
        await asyncio.sleep(0)
        self.closed = True


def test_async_manager_direct_lifecycle() -> None:
    db_type = "sqlite"
    created: dict[str, FakeConnection] = {}

    async def builder(_db_type: str, _conn_params: dict, **kwargs):
        await asyncio.sleep(0)
        conn = FakeConnection()
        created["conn"] = conn
        return conn

    async def _run() -> None:
        manager = AsyncDatabaseManager(
            db_type=db_type,
            conn_params={},
            use_pool=False,
            connection_factory=builder,
        )
        rows = await manager.execute_custom_many("SELECT 1")
        assert rows == [("many",)]
        await manager.close()
        assert created["conn"].closed is True

    asyncio.run(_run())


def test_async_manager_pool_lifecycle() -> None:
    db_type = "sqlite"
    created: dict[str, FakePool] = {}

    async def pool_builder(_db_type: str, _conn_params: dict, **kwargs):
        await asyncio.sleep(0)
        pool = FakePool()
        created["pool"] = pool
        return pool

    async def _run() -> None:
        manager = AsyncDatabaseManager(
            db_type=db_type,
            conn_params={},
            use_pool=True,
            pool_factory=pool_builder,
        )
        row = await manager.execute_custom_one("SELECT 1")
        assert row == ("one",)
        assert created["pool"].released == 1
        await manager.close()
        assert created["pool"].closed is True

    asyncio.run(_run())


def test_async_manager_rejects_unsupported_db_type_without_custom_builder() -> None:
    with pytest.raises(Exception) as exc_info:
        AsyncDatabaseManager(db_type="unsupported_db_type", conn_params={}, use_pool=False)

    assert "no soportado" in str(exc_info.value).lower()
