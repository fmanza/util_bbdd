"""Tests de soporte async Oracle con mocks de oracledb."""

from __future__ import annotations

import asyncio
import sys

from util_bbdd import AsyncDatabaseManager
from util_bbdd.connection.oracle.async_connection_oracle import AsyncOracleConnection
from util_bbdd.connection.oracle.async_pool_connection_oracle import AsyncOraclePool


class _FakeOracleConn:
    async def execute(self, sql: str, params=None):
        return None

    async def fetchone(self):
        return ("ora-one",)

    async def fetchall(self):
        return [("ora-many",)]

    async def close(self):
        return None


class _FakeOraclePool:
    def __init__(self) -> None:
        self.conn = _FakeOracleConn()
        self.release_count = 0
        self.closed = False

    async def acquire(self):
        return self.conn

    async def release(self, connection):
        self.release_count += 1

    async def close(self):
        self.closed = True


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
        return self.conn

    async def create_pool_async(self, **kwargs):
        return self.pool


def _install_fake_oracledb(monkeypatch):
    fake_mod = _FakeOracleDBModule()
    monkeypatch.setitem(sys.modules, "oracledb", fake_mod)
    return fake_mod


def test_async_oracle_connection(monkeypatch):
    fake_mod = _install_fake_oracledb(monkeypatch)

    async def _run() -> None:
        conn = await AsyncOracleConnection.connect(
            {
                "user": "scott",
                "password": "tiger",
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
                "password": "tiger",
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
        await pool.aclose()
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
                "password": "tiger",
                "host": "localhost",
                "port": 1521,
                "service_name": "XE",
                "pool_size": 2,
            },
            use_pool=True,
        ) as manager:
            row = await manager.execute_custom_query("SELECT 1", fetch_one=True)
            assert row == ("ora-one",)

        assert fake_mod.pool.release_count == 1
        assert fake_mod.pool.closed is True

    asyncio.run(_run())
