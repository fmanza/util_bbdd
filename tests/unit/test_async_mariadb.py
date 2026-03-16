"""Tests de soporte async MariaDB con mocks de aiomysql."""

from __future__ import annotations

import asyncio
import sys

from util_bbdd import AsyncDatabaseManager
from util_bbdd.connection.mariadb.async_connection_mariadb import AsyncMariaDBConnection
from util_bbdd.connection.mariadb.async_pool_connection_mariadb import AsyncMariaDBPool


class _FakeMariaConn:
    def __init__(self) -> None:
        self.closed = False

    async def execute(self, sql: str, params=None):
        await asyncio.sleep(0)
        return None

    async def fetchone(self):
        await asyncio.sleep(0)
        return ("maria-one",)

    async def fetchall(self):
        await asyncio.sleep(0)
        return [("maria-many",)]

    async def close(self):
        await asyncio.sleep(0)
        self.closed = True


class _FakeMariaPool:
    def __init__(self) -> None:
        self.conn = _FakeMariaConn()
        self.release_count = 0
        self.closed = False

    async def acquire(self):
        await asyncio.sleep(0)
        return self.conn

    def release(self, connection) -> None:
        self.release_count += 1

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        await asyncio.sleep(0)
        return None


class _HangingMariaPool(_FakeMariaPool):
    def __init__(self) -> None:
        super().__init__()
        self.terminated = False

    async def wait_closed(self) -> None:
        if self.terminated:
            return
        await asyncio.Event().wait()

    def terminate(self) -> None:
        self.terminated = True
        self.closed = True


class _FakeAioMySQLModule:
    def __init__(self) -> None:
        self.conn = _FakeMariaConn()
        self.pool = _FakeMariaPool()

    async def connect(self, *args, **kwargs):
        await asyncio.sleep(0)
        return self.conn

    async def create_pool(self, *args, **kwargs):
        await asyncio.sleep(0)
        return self.pool


def _install_fake_aiomysql(monkeypatch):
    fake_mod = _FakeAioMySQLModule()
    monkeypatch.setitem(sys.modules, "aiomysql", fake_mod)
    return fake_mod


def _install_fake_aiomysql_with_pool(monkeypatch, fake_pool):
    class _CustomFakeAioMySQLModule:
        def __init__(self) -> None:
            self.conn = _FakeMariaConn()
            self.pool = fake_pool

        async def connect(self, *args, **kwargs):
            await asyncio.sleep(0)
            return self.conn

        async def create_pool(self, *args, **kwargs):
            await asyncio.sleep(0)
            return self.pool

    fake_mod = _CustomFakeAioMySQLModule()
    monkeypatch.setitem(sys.modules, "aiomysql", fake_mod)
    return fake_mod


def test_async_mariadb_connection(monkeypatch):
    fake_mod = _install_fake_aiomysql(monkeypatch)

    async def _run() -> None:
        conn = await AsyncMariaDBConnection.connect(
            {
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "pwd",
                "database": "db",
            }
        )
        rows = await conn.fetchall()
        assert rows == [("maria-many",)]
        assert conn is fake_mod.conn

    asyncio.run(_run())


def test_async_mariadb_pool(monkeypatch):
    fake_mod = _install_fake_aiomysql(monkeypatch)

    async def _run() -> None:
        pool = await AsyncMariaDBPool.create(
            {
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "pwd",
                "database": "db",
                "pool_size": 4,
            }
        )
        conn = await pool.acquire()
        one = await conn.fetchone()
        assert one == ("maria-one",)
        await pool.release(conn)
        await pool.close()
        assert fake_mod.pool.release_count == 1
        assert fake_mod.pool.closed is True

    asyncio.run(_run())


def test_async_database_manager_mariadb_pool(monkeypatch):
    fake_mod = _install_fake_aiomysql(monkeypatch)

    async def _run() -> None:
        async with AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "pwd",
                "database": "db",
                "pool_size": 2,
            },
            use_pool=True,
        ) as manager:
            row = await manager.execute_custom_one("SELECT 1")
            assert row == ("maria-one",)

        assert fake_mod.pool.release_count == 1
        assert fake_mod.pool.closed is True

    asyncio.run(_run())


def test_async_mariadb_pool_forced_close_on_timeout(monkeypatch):
    hanging_pool = _HangingMariaPool()
    _install_fake_aiomysql_with_pool(monkeypatch, hanging_pool)

    async def _run() -> None:
        pool = await AsyncMariaDBPool.create(
            {
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "pwd",
                "database": "db",
                "close_timeout": 0.01,
            }
        )
        await pool.close()
        assert hanging_pool.terminated is True
        assert hanging_pool.closed is True

    asyncio.run(_run())
