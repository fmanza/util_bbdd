"""Tests de soporte async PostgreSQL con mocks de asyncpg."""

from __future__ import annotations

import asyncio
import types

from util_bbdd import AsyncDatabaseManager
from util_bbdd.connection.postgresql.async_connection_postgresql import AsyncPostgreSQLConnection
from util_bbdd.connection.postgresql.async_pool_connection_postgresql import AsyncPostgreSQLPool


class _FakeConn:
    def __init__(self):
        self.closed = False
        self.last_sql = None

    async def execute(self, sql, params=None):
        await asyncio.sleep(0)
        self.last_sql = sql

    async def fetchone(self):
        await asyncio.sleep(0)
        return ("pg-one",)

    async def fetchall(self):
        await asyncio.sleep(0)
        return [("pg-many",)]

    async def close(self):
        await asyncio.sleep(0)
        self.closed = True


class _FakePool:
    def __init__(self):
        self.conn = _FakeConn()
        self.closed = False
        self.release_count = 0

    async def acquire(self):
        await asyncio.sleep(0)
        return self.conn

    async def release(self, connection):
        await asyncio.sleep(0)
        self.release_count += 1

    async def close(self):
        await asyncio.sleep(0)
        self.closed = True


class _HangingClosePool(_FakePool):
    def __init__(self):
        super().__init__()
        self.terminated = False

    async def close(self):
        await asyncio.Event().wait()

    def terminate(self):
        self.terminated = True
        self.closed = True


def _install_fake_asyncpg(monkeypatch):
    fake_pool = _FakePool()

    async def fake_connect(**kwargs):
        await asyncio.sleep(0)
        return _FakeConn()

    async def fake_create_pool(**kwargs):
        await asyncio.sleep(0)
        return fake_pool

    fake_module = types.SimpleNamespace(
        connect=fake_connect,
        create_pool=fake_create_pool,
    )
    monkeypatch.setitem(__import__("sys").modules, "asyncpg", fake_module)
    return fake_pool


def _install_fake_asyncpg_with_pool(monkeypatch, fake_pool):
    async def fake_connect(**kwargs):
        await asyncio.sleep(0)
        return _FakeConn()

    async def fake_create_pool(**kwargs):
        await asyncio.sleep(0)
        return fake_pool

    fake_module = types.SimpleNamespace(
        connect=fake_connect,
        create_pool=fake_create_pool,
    )
    monkeypatch.setitem(__import__("sys").modules, "asyncpg", fake_module)
    return fake_pool


def test_async_postgresql_connection(monkeypatch):
    _install_fake_asyncpg(monkeypatch)

    async def _run() -> None:
        conn = await AsyncPostgreSQLConnection.connect(
            {
                "host": "localhost",
                "port": 5432,
                "user": "postgres",
                "password": "pwd",
                "database": "db",
            }
        )
        rows = await conn.fetchall()
        assert rows == [("pg-many",)]

    asyncio.run(_run())


def test_async_postgresql_pool(monkeypatch):
    fake_pool = _install_fake_asyncpg(monkeypatch)

    async def _run() -> None:
        pool = await AsyncPostgreSQLPool.create(
            {
                "host": "localhost",
                "port": 5432,
                "user": "postgres",
                "password": "pwd",
                "database": "db",
                "pool_size": 3,
                "pool_timeout": 10,
            }
        )
        conn = await pool.acquire()
        one = await conn.fetchone()
        assert one == ("pg-one",)
        await pool.release(conn)
        await pool.close()
        assert fake_pool.release_count == 1
        assert fake_pool.closed is True

    asyncio.run(_run())


def test_async_database_manager_postgresql_pool(monkeypatch):
    fake_pool = _install_fake_asyncpg(monkeypatch)

    async def _run() -> None:
        async with AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={
                "host": "localhost",
                "port": 5432,
                "user": "postgres",
                "password": "pwd",
                "database": "db",
                "pool_size": 2,
                "pool_timeout": 10,
            },
            use_pool=True,
        ) as manager:
            row = await manager.execute_custom_one("SELECT 1")
            assert row == ("pg-one",)

        assert fake_pool.release_count == 1
        assert fake_pool.closed is True

    asyncio.run(_run())


def test_async_postgresql_pool_forced_close_on_timeout(monkeypatch):
    hanging_pool = _HangingClosePool()
    _install_fake_asyncpg_with_pool(monkeypatch, hanging_pool)

    async def _run() -> None:
        pool = await AsyncPostgreSQLPool.create(
            {
                "host": "localhost",
                "port": 5432,
                "user": "postgres",
                "password": "pwd",
                "database": "db",
                "close_timeout": 0.01,
            }
        )
        await pool.close()
        assert hanging_pool.terminated is True
        assert hanging_pool.closed is True

    asyncio.run(_run())
