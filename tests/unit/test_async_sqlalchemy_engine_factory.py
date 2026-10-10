"""Tests base (PR-00) para AsyncSQLAlchemyEngineFactory."""

from __future__ import annotations

import asyncio

from typing import Any

import pytest

from sqlalchemy.pool import NullPool

from util_bbdd.exceptions import ConnectionError, ValidationError
from util_bbdd.factory.async_sqlalchemy_engine_factory import AsyncSQLAlchemyEngineFactory


class _FakeConn:
    def __init__(self) -> None:
        self.executed = False

    async def execute(self, _statement: Any) -> None:
        self.executed = True
        await asyncio.sleep(0)


class _FakeConnectContext:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        return None


class _FakeEngine:
    def __init__(self) -> None:
        self.conn = _FakeConn()

    def connect(self) -> _FakeConnectContext:
        return _FakeConnectContext(self.conn)


def test_async_sqlalchemy_engine_factory_no_pool_uses_nullpool(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_create_async_engine(conn_str: str, **kwargs: Any) -> _FakeEngine:
        captured["conn_str"] = conn_str
        captured["kwargs"] = kwargs
        return _FakeEngine()

    monkeypatch.setattr("sqlalchemy.ext.asyncio.create_async_engine", _fake_create_async_engine)

    async def _run() -> None:
        engine = await AsyncSQLAlchemyEngineFactory.create_engine(
            db_type="sqlite",
            conn_params={"database": ":memory:"},
            use_pool=False,
        )
        assert isinstance(engine, _FakeEngine)
        assert captured["conn_str"].startswith("sqlite+aiosqlite:///")
        assert captured["kwargs"]["poolclass"] is NullPool
        assert engine.conn.executed is True

    asyncio.run(_run())


def test_async_sqlalchemy_engine_factory_with_pool_sets_pool_kwargs(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_create_async_engine(conn_str: str, **kwargs: Any) -> _FakeEngine:
        captured["conn_str"] = conn_str
        captured["kwargs"] = kwargs
        return _FakeEngine()

    monkeypatch.setattr("sqlalchemy.ext.asyncio.create_async_engine", _fake_create_async_engine)

    async def _run() -> None:
        engine = await AsyncSQLAlchemyEngineFactory.create_engine(
            db_type="postgresql",
            conn_params={
                "host": "localhost",
                "port": 5432,
                "user": "postgres",
                "password": "test_pwd",
                "database": "db_async",
            },
            use_pool=True,
            pool_size=7,
            max_overflow=3,
            pool_timeout=20,
            pool_recycle=600,
        )
        assert isinstance(engine, _FakeEngine)
        assert captured["conn_str"].startswith("postgresql+asyncpg://")
        assert captured["kwargs"]["pool_size"] == 7
        assert captured["kwargs"]["max_overflow"] == 3
        assert captured["kwargs"]["pool_timeout"] == 20
        assert captured["kwargs"]["pool_recycle"] == 600

    asyncio.run(_run())


def test_async_sqlalchemy_engine_factory_hsqldb_not_supported() -> None:
    async def _run() -> None:
        try:
            await AsyncSQLAlchemyEngineFactory.create_engine(
                db_type="hsqldb",
                conn_params={"host": "localhost"},
                database="legacy",
            )
            raise AssertionError("Se esperaba ConnectionError para hsqldb async")
        except ConnectionError as err:
            assert "hsqldb async no soportado" in str(err).lower()

    asyncio.run(_run())


def test_build_hsqldb_connection_string_removed_as_dead_code() -> None:
    """SVC-04 (AUDIT_CODE 2026-09-22): _build_hsqldb_connection_string era inalcanzable
    (create_engine rechaza hsqldb explícitamente antes de llegar a ningún builder) y
    se retiró. No debe reintroducirse sin un caller real."""
    assert not hasattr(AsyncSQLAlchemyEngineFactory, "_build_hsqldb_connection_string")


def test_postgresql_builder_requires_password() -> None:
    with pytest.raises(ValidationError):
        AsyncSQLAlchemyEngineFactory._build_postgresql_connection_string(
            {
                "host": "localhost",
                "port": 5432,
                "user": "postgres",
                "database": "db_async",
            },
            database=None,
        )


def test_postgresql_builder_uses_database_fallback() -> None:
    conn_str = AsyncSQLAlchemyEngineFactory._build_postgresql_connection_string(
        {
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "test_pwd",
            "database": "db_from_params",
        },
        database=None,
    )
    assert conn_str == "postgresql+asyncpg://postgres:test_pwd@localhost:5432/db_from_params"


def test_sqlite_builder_memory_and_relative_path() -> None:
    memory_str = AsyncSQLAlchemyEngineFactory._build_sqlite_connection_string({"database": ":memory:"})
    relative_str = AsyncSQLAlchemyEngineFactory._build_sqlite_connection_string({"database": "tmp/test.db"})

    assert memory_str == "sqlite+aiosqlite:///:memory:"
    assert relative_str == "sqlite+aiosqlite:///tmp/test.db"


def test_sqlite_builder_requires_database_param() -> None:
    with pytest.raises(ValidationError):
        AsyncSQLAlchemyEngineFactory._build_sqlite_connection_string({"database": ""})


def test_mariadb_builder_requires_password() -> None:
    with pytest.raises(ValidationError):
        AsyncSQLAlchemyEngineFactory._build_mariadb_connection_string(
            {
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "database": "db_async",
            },
            database=None,
        )


def test_mariadb_builder_uses_database_fallback() -> None:
    conn_str = AsyncSQLAlchemyEngineFactory._build_mariadb_connection_string(
        {
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "test_pwd",
            "database": "db_from_params",
        },
        database=None,
    )
    assert conn_str == "mysql+aiomysql://root:test_pwd@localhost:3306/db_from_params"


def test_async_sqlalchemy_engine_factory_mariadb_pool_mode(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_create_async_engine(conn_str: str, **kwargs: Any) -> _FakeEngine:
        captured["conn_str"] = conn_str
        captured["kwargs"] = kwargs
        return _FakeEngine()

    monkeypatch.setattr("sqlalchemy.ext.asyncio.create_async_engine", _fake_create_async_engine)

    async def _run() -> None:
        engine = await AsyncSQLAlchemyEngineFactory.create_engine(
            db_type="mariadb",
            conn_params={
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "test_pwd",
                "database": "db_async",
            },
            use_pool=True,
            pool_size=4,
            max_overflow=2,
            pool_timeout=25,
            pool_recycle=500,
        )
        assert isinstance(engine, _FakeEngine)
        assert captured["conn_str"].startswith("mysql+aiomysql://")
        assert captured["kwargs"]["pool_size"] == 4
        assert captured["kwargs"]["max_overflow"] == 2
        assert captured["kwargs"]["pool_timeout"] == 25
        assert captured["kwargs"]["pool_recycle"] == 500

    asyncio.run(_run())


def test_oracle_builder_requires_user() -> None:
    with pytest.raises(ValidationError):
        AsyncSQLAlchemyEngineFactory._build_oracle_connection_string(
            {
                "password": "test_pwd",
                "host": "localhost",
                "port": 1521,
                "service_name": "XE",
            },
            database=None,
        )


def test_oracle_builder_requires_password() -> None:
    with pytest.raises(ValidationError):
        AsyncSQLAlchemyEngineFactory._build_oracle_connection_string(
            {
                "user": "system",
                "host": "localhost",
                "port": 1521,
                "service_name": "XE",
            },
            database=None,
        )


def test_oracle_builder_requires_service_name_or_database() -> None:
    with pytest.raises(ValidationError):
        AsyncSQLAlchemyEngineFactory._build_oracle_connection_string(
            {
                "user": "system",
                "password": "test_pwd",
                "host": "localhost",
                "port": 1521,
            },
            database=None,
        )


def test_oracle_builder_uses_database_as_service_name_fallback() -> None:
    conn_str = AsyncSQLAlchemyEngineFactory._build_oracle_connection_string(
        {
            "user": "system",
            "password": "test_pwd",
            "host": "localhost",
            "port": 1521,
        },
        database="XE",
    )
    assert conn_str == "oracle+oracledb://system:test_pwd@localhost:1521/?service_name=XE"


def test_sqlserver_builder_requires_password() -> None:
    with pytest.raises(ValidationError):
        AsyncSQLAlchemyEngineFactory._build_sqlserver_connection_string(
            {
                "host": "localhost",
                "port": 1433,
                "user": "sa",
                "database": "db_async",
            },
            database=None,
        )


def test_sqlserver_builder_requires_database() -> None:
    with pytest.raises(ValidationError):
        AsyncSQLAlchemyEngineFactory._build_sqlserver_connection_string(
            {
                "host": "localhost",
                "port": 1433,
                "user": "sa",
                "password": "test_pwd",
            },
            database=None,
        )


def test_sqlserver_builder_requires_aioodbc_driver() -> None:
    with pytest.raises(ValidationError):
        AsyncSQLAlchemyEngineFactory._build_sqlserver_connection_string(
            {
                "host": "localhost",
                "port": 1433,
                "user": "sa",
                "password": "test_pwd",
                "database": "db_async",
            },
            database=None,
            sql_server_driver="pyodbc",
        )


def test_sqlserver_builder_uses_database_fallback() -> None:
    conn_str = AsyncSQLAlchemyEngineFactory._build_sqlserver_connection_string(
        {
            "host": "localhost",
            "port": 1433,
            "user": "sa",
            "password": "test_pwd",
            "database": "db_async",
        },
        database=None,
        sql_server_driver="aioodbc",
    )
    assert conn_str == "mssql+aioodbc://sa:test_pwd@localhost:1433/db_async"


def test_async_sqlalchemy_engine_factory_sqlserver_pool_mode(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_create_async_engine(conn_str: str, **kwargs: Any) -> _FakeEngine:
        captured["conn_str"] = conn_str
        captured["kwargs"] = kwargs
        return _FakeEngine()

    monkeypatch.setattr("sqlalchemy.ext.asyncio.create_async_engine", _fake_create_async_engine)

    async def _run() -> None:
        engine = await AsyncSQLAlchemyEngineFactory.create_engine(
            db_type="sqlserver",
            conn_params={
                "host": "localhost",
                "port": 1433,
                "user": "sa",
                "password": "test_pwd",
                "database": "db_async",
            },
            use_pool=True,
            sql_server_driver="aioodbc",
            pool_size=6,
            max_overflow=4,
            pool_timeout=35,
            pool_recycle=700,
        )
        assert isinstance(engine, _FakeEngine)
        assert captured["conn_str"].startswith("mssql+aioodbc://")
        assert captured["kwargs"]["pool_size"] == 6
        assert captured["kwargs"]["max_overflow"] == 4
        assert captured["kwargs"]["pool_timeout"] == 35
        assert captured["kwargs"]["pool_recycle"] == 700

    asyncio.run(_run())
