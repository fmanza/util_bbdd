"""Tests de soporte async SQL Server con mocks de aioodbc."""

from __future__ import annotations

import asyncio
import sys

from util_bbdd import AsyncDatabaseManager
from util_bbdd.connection.sqlserver.async_connection_sqlserver import AsyncSQLServerConnection
from util_bbdd.connection.sqlserver.async_pool_connection_sqlserver import AsyncSQLServerPool


class _FakeSQLServerConn:
    async def execute(self, sql: str, params=None):
        await asyncio.sleep(0)
        return None

    async def fetchone(self):
        await asyncio.sleep(0)
        return ("sqls-one",)

    async def fetchall(self):
        await asyncio.sleep(0)
        return [("sqls-many",)]

    async def close(self):
        """Close SQL Server connection"""
        await asyncio.sleep(0)


class _FakeSQLServerPool:
    def __init__(self) -> None:
        self.conn = _FakeSQLServerConn()
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


class _HangingSQLServerPool(_FakeSQLServerPool):
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


class _FakeAioODBCModule:
    def __init__(self) -> None:
        self.conn = _FakeSQLServerConn()
        self.pool = _FakeSQLServerPool()

    async def connect(self, **kwargs):
        await asyncio.sleep(0)
        return self.conn

    async def create_pool(self, **kwargs):
        await asyncio.sleep(0)
        return self.pool


def _install_fake_aioodbc(monkeypatch):
    fake_mod = _FakeAioODBCModule()
    monkeypatch.setitem(sys.modules, "aioodbc", fake_mod)
    return fake_mod


def _install_fake_aioodbc_with_pool(monkeypatch, fake_pool):
    class _CustomFakeAioODBCModule:
        def __init__(self) -> None:
            self.conn = _FakeSQLServerConn()
            self.pool = fake_pool

        async def connect(self, **kwargs):
            await asyncio.sleep(0)
            return self.conn

        async def create_pool(self, **kwargs):
            await asyncio.sleep(0)
            return self.pool

    fake_mod = _CustomFakeAioODBCModule()
    monkeypatch.setitem(sys.modules, "aioodbc", fake_mod)
    return fake_mod


def test_async_sqlserver_connection(monkeypatch):
    fake_mod = _install_fake_aioodbc(monkeypatch)

    async def _run() -> None:
        conn = await AsyncSQLServerConnection.connect(
            {
                "host": "localhost",
                "port": 1433,
                "user": "sa",
                "password": "pwd",
                "database": "master",
                "sql_server_driver": "pyodbc",
            }
        )
        rows = await conn.fetchall()
        assert rows == [("sqls-many",)]
        assert conn is fake_mod.conn

    asyncio.run(_run())


def test_async_sqlserver_pool(monkeypatch):
    fake_mod = _install_fake_aioodbc(monkeypatch)

    async def _run() -> None:
        pool = await AsyncSQLServerPool.create(
            {
                "host": "localhost",
                "port": 1433,
                "user": "sa",
                "password": "pwd",
                "database": "master",
                "sql_server_driver": "pyodbc",
                "pool_size": 2,
                "max_overflow": 1,
            }
        )
        conn = await pool.acquire()
        one = await conn.fetchone()
        assert one == ("sqls-one",)
        await pool.release(conn)
        await pool.close()
        assert fake_mod.pool.release_count == 1
        assert fake_mod.pool.closed is True

    asyncio.run(_run())


def test_async_database_manager_sqlserver_pool(monkeypatch):
    fake_mod = _install_fake_aioodbc(monkeypatch)

    async def _run() -> None:
        async with AsyncDatabaseManager(
            db_type="sqlserver",
            conn_params={
                "host": "localhost",
                "port": 1433,
                "user": "sa",
                "password": "pwd",
                "database": "master",
                "sql_server_driver": "pyodbc",
                "pool_size": 2,
            },
            use_pool=True,
        ) as manager:
            row = await manager.execute_custom_one("SELECT 1")
            assert row == ("sqls-one",)

        assert fake_mod.pool.release_count == 1
        assert fake_mod.pool.closed is True

    asyncio.run(_run())


def test_async_sqlserver_pool_forced_close_on_timeout(monkeypatch):
    hanging_pool = _HangingSQLServerPool()
    _install_fake_aioodbc_with_pool(monkeypatch, hanging_pool)

    async def _run() -> None:
        pool = await AsyncSQLServerPool.create(
            {
                "host": "localhost",
                "port": 1433,
                "user": "sa",
                "password": "pwd",
                "database": "master",
                "sql_server_driver": "pyodbc",
                "close_timeout": 0.01,
            }
        )
        await pool.close()
        assert hanging_pool.terminated is True
        assert hanging_pool.closed is True

    asyncio.run(_run())
