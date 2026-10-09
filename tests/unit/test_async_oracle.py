"""Tests de soporte async Oracle con mocks de oracledb."""

from __future__ import annotations

import asyncio
import sys

from util_bbdd import AsyncDatabaseManager
from util_bbdd.connection.oracle.async_connection_oracle import AsyncOracleConnection
from util_bbdd.connection.oracle.async_pool_connection_oracle import AsyncOraclePool


class _FakeOracleConn:
    async def execute(self, sql: str, params=None):
        await asyncio.sleep(0)
        return None

    async def fetchone(self):
        await asyncio.sleep(0)
        return ("ora-one",)

    async def fetchall(self):
        await asyncio.sleep(0)
        return [("ora-many",)]

    async def close(self):
        """Close connection"""
        await asyncio.sleep(0)


class _FakeOraclePool:
    def __init__(self) -> None:
        self.conn = _FakeOracleConn()
        self.release_count = 0
        self.closed = False

    async def acquire(self):
        await asyncio.sleep(0)
        return self.conn

    async def release(self, connection):
        await asyncio.sleep(0)
        self.release_count += 1

    async def close(self):
        await asyncio.sleep(0)
        self.closed = True


class _HangingOraclePool(_FakeOraclePool):
    def __init__(self) -> None:
        super().__init__()
        self.force_close_used = False

    async def close(self, force: bool = False):
        if force:
            self.force_close_used = True
            self.closed = True
            return
        await asyncio.Event().wait()


class _FakeOracleDBModule:
    POOL_GETMODE_WAIT = 1

    def __init__(self) -> None:
        self.pool = _FakeOraclePool()
        self.conn = _FakeOracleConn()

    def makedsn(self, host: str, port: int, service_name=None, sid=None):
        if service_name:
            return f"{host}:{port}/{service_name}"
        return f"{host}:{port}/{sid}"

    async def connect_async(self, **kwargs):
        await asyncio.sleep(0)
        return self.conn

    async def create_pool_async(self, **kwargs):
        await asyncio.sleep(0)
        return self.pool


def _install_fake_oracledb(monkeypatch):
    fake_mod = _FakeOracleDBModule()
    monkeypatch.setitem(sys.modules, "oracledb", fake_mod)
    return fake_mod


def _install_fake_oracledb_with_pool(monkeypatch, fake_pool):
    class _CustomFakeOracleDBModule:
        POOL_GETMODE_WAIT = 1

        def __init__(self) -> None:
            self.pool = fake_pool
            self.conn = _FakeOracleConn()

        def makedsn(self, host: str, port: int, service_name=None, sid=None):
            if service_name:
                return f"{host}:{port}/{service_name}"
            return f"{host}:{port}/{sid}"

        async def connect_async(self, **kwargs):
            await asyncio.sleep(0)
            return self.conn

        async def create_pool_async(self, **kwargs):
            await asyncio.sleep(0)
            return self.pool

    fake_mod = _CustomFakeOracleDBModule()
    monkeypatch.setitem(sys.modules, "oracledb", fake_mod)
    return fake_mod


def test_async_oracle_connection(monkeypatch):
    fake_mod = _install_fake_oracledb(monkeypatch)

    async def _run() -> None:
        conn = await AsyncOracleConnection.connect(
            {
                "user": "scott",
                "password": "tiger",  # noqa: S105
                "host": "localhost",
                "port": 1521,
                "service_name": "XE",
            }
        )
        rows = await conn.fetchall()
        assert rows == [("ora-many",)]
        assert conn is fake_mod.conn

    asyncio.run(_run())


def test_async_oracle_pool(monkeypatch):
    fake_mod = _install_fake_oracledb(monkeypatch)

    async def _run() -> None:
        pool = await AsyncOraclePool.create(
            {
                "user": "scott",
                "password": "tiger",  # noqa: S105
                "host": "localhost",
                "port": 1521,
                "service_name": "XE",
                "pool_size": 3,
            }
        )
        conn = await pool.acquire()
        one = await conn.fetchone()
        assert one == ("ora-one",)
        await pool.release(conn)
        await pool.close()
        assert fake_mod.pool.release_count == 1
        assert fake_mod.pool.closed is True

    asyncio.run(_run())


def test_async_database_manager_oracle_pool(monkeypatch):
    fake_mod = _install_fake_oracledb(monkeypatch)

    async def _run() -> None:
        async with AsyncDatabaseManager(
            db_type="oracle",
            conn_params={
                "user": "scott",
                "password": "tiger",  # noqa: S105
                "host": "localhost",
                "port": 1521,
                "service_name": "XE",
                "pool_size": 2,
            },
            use_pool=True,
        ) as manager:
            row = await manager.execute_custom_one("SELECT 1")
            assert row == ("ora-one",)

        assert fake_mod.pool.release_count == 1
        assert fake_mod.pool.closed is True

    asyncio.run(_run())


def test_async_oracle_pool_forced_close_on_timeout(monkeypatch):
    hanging_pool = _HangingOraclePool()
    _install_fake_oracledb_with_pool(monkeypatch, hanging_pool)

    async def _run() -> None:
        pool = await AsyncOraclePool.create(
            {
                "user": "scott",
                "password": "tiger",  # noqa: S105
                "host": "localhost",
                "port": 1521,
                "service_name": "XE",
                "close_timeout": 0.01,
            }
        )
        await pool.close()
        assert hanging_pool.force_close_used is True
        assert hanging_pool.closed is True

    asyncio.run(_run())


def test_async_oracle_pool_with_sync_create_pool_async(monkeypatch):
    """Hotfix v0.36.1: en python-oracledb 4.x ``create_pool_async`` no es corrutina, devuelve el pool directamente.

    El doble anterior lo simulaba como corrutina y ocultaba ``TypeError: 'AsyncConnectionPool' object can't be
    awaited`` contra un servidor real.
    """
    fake_mod = _install_fake_oracledb(monkeypatch)
    calls: list[dict] = []

    def create_pool_async(**kwargs):  # firma real: función normal
        calls.append(kwargs)
        return fake_mod.pool

    monkeypatch.setattr(fake_mod, "create_pool_async", create_pool_async, raising=False)

    async def _run() -> None:
        pool = await AsyncOraclePool.create(
            {"user": "scott", "password": "tiger", "host": "localhost", "port": 1521, "service_name": "XE"}  # noqa: S105
        )
        conn = await pool.acquire()
        await pool.release(conn)
        await pool.close()
        assert fake_mod.pool.closed is True

    asyncio.run(_run())
    assert len(calls) == 1
