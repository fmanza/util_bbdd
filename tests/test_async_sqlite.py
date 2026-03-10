"""Tests de soporte async SQLite con mocks de aiosqlite."""

from __future__ import annotations

import asyncio
import sys

from util_bbdd import AsyncDatabaseManager
from util_bbdd.connection.sqlite.async_connection_sqlite import AsyncSQLiteConnection
from util_bbdd.connection.sqlite.async_pool_connection_sqlite import AsyncSQLitePool


class _FakeSQLiteConn:
    def __init__(self) -> None:
        self.closed = False
        self.commands: list[str] = []

    async def execute(self, sql: str, params=None):
        self.commands.append(sql)

    async def fetchone(self):
        return ("sqlite-one",)

    async def fetchall(self):
        return [("sqlite-many",)]

    async def close(self):
        self.closed = True


class _HangingSQLiteConn(_FakeSQLiteConn):
    async def close(self):
        await asyncio.Event().wait()


class _FakeAioSQLiteModule:
    def __init__(self) -> None:
        self.conn = _FakeSQLiteConn()

    async def connect(self, *args, **kwargs):
        return self.conn


def _install_fake_aiosqlite(monkeypatch) -> _FakeSQLiteConn:
    fake_mod = _FakeAioSQLiteModule()
    monkeypatch.setitem(sys.modules, "aiosqlite", fake_mod)
    return fake_mod.conn


def _install_fake_aiosqlite_with_conn(monkeypatch, conn):
    class _CustomFakeAioSQLiteModule:
        async def connect(self, *args, **kwargs):
            return conn

    monkeypatch.setitem(sys.modules, "aiosqlite", _CustomFakeAioSQLiteModule())
    return conn


def test_async_sqlite_connection(monkeypatch):
    fake_conn = _install_fake_aiosqlite(monkeypatch)

    async def _run() -> None:
        conn = await AsyncSQLiteConnection.connect({"database": ":memory:"})
        rows = await conn.fetchall()
        assert rows == [("sqlite-many",)]
        assert "PRAGMA foreign_keys = ON" in fake_conn.commands

    asyncio.run(_run())


def test_async_sqlite_pool(monkeypatch):
    fake_conn = _install_fake_aiosqlite(monkeypatch)

    async def _run() -> None:
        pool = await AsyncSQLitePool.create({"database": ":memory:"})
        conn = await pool.acquire()
        one = await conn.fetchone()
        assert one == ("sqlite-one",)
        await pool.release(conn)
        await pool.close()
        assert fake_conn.closed is True

    asyncio.run(_run())


def test_async_database_manager_sqlite_pool(monkeypatch):
    fake_conn = _install_fake_aiosqlite(monkeypatch)

    async def _run() -> None:
        async with AsyncDatabaseManager(
            db_type="sqlite",
            conn_params={"database": ":memory:"},
            use_pool=True,
        ) as manager:
            row = await manager.execute_custom_one("SELECT 1")
            assert row == ("sqlite-one",)

        assert fake_conn.closed is True

    asyncio.run(_run())


def test_async_sqlite_pool_close_timeout_does_not_block(monkeypatch):
    hanging_conn = _HangingSQLiteConn()
    _install_fake_aiosqlite_with_conn(monkeypatch, hanging_conn)

    async def _run() -> None:
        pool = await AsyncSQLitePool.create({"database": ":memory:", "close_timeout": 0.01})
        await pool.close()

    asyncio.run(_run())

