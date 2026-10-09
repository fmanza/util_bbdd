"""B3 de drivers-connections-audit (v0.36.0): política de pool de los Engine, ``close_timeout`` en ``*PoolConfig`` y
cierre común de los pools sync (``SyncPoolCloseMixin``)."""

from __future__ import annotations

import asyncio

from typing import Any
from unittest import mock

import pytest

from util_bbdd._core.exceptions import ConnectionError
from util_bbdd.connection.close import SyncPoolCloseMixin
from util_bbdd.connection.config import (
    MariaDBPoolConfig,
    MySQLPoolConfig,
    OraclePoolConfig,
    PostgreSQLPoolConfig,
    SQLitePoolConfig,
    SQLServerPoolConfig,
)
from util_bbdd.factory._pool_policy import ENGINE_POOL_DEFAULTS, engine_pool_kwargs
from util_bbdd.factory.async_sqlalchemy_engine_factory import AsyncSQLAlchemyEngineFactory
from util_bbdd.factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory

NET = {"host": "h", "user": "u", "password": "p", "database": "d"}


# --- Política de pool de los Engine -------------------------------------------------------------------------------


def test_engine_pool_defaults_match_queuepool_and_native_recycle() -> None:
    assert ENGINE_POOL_DEFAULTS == {"pool_size": 5, "max_overflow": 10, "pool_timeout": 30, "pool_recycle": 3600}
    assert engine_pool_kwargs("postgresql", {}) == ENGINE_POOL_DEFAULTS


def test_engine_pool_kwargs_read_conn_params_and_overrides() -> None:
    params = {"pool_size": "7", "max_overflow": 2, "pool_timeout": None}
    assert engine_pool_kwargs("mysql", params) == {
        "pool_size": 7,
        "max_overflow": 2,
        "pool_timeout": 30,
        "pool_recycle": 3600,
    }
    assert engine_pool_kwargs("mysql", params, pool_size=9, pool_recycle=None)["pool_size"] == 9


def test_engine_pool_kwargs_sqlite_is_empty() -> None:
    assert engine_pool_kwargs("sqlite", {"pool_size": 3}) == {}


class _Captured(Exception):
    pass


def test_sync_engine_uses_conn_params_pool_policy() -> None:
    captured: dict[str, Any] = {}

    def fake_create_engine(url: str, **kwargs: Any) -> Any:
        captured.update(kwargs)
        raise _Captured

    with mock.patch("sqlalchemy.create_engine", fake_create_engine), pytest.raises(ConnectionError):
        SQLAlchemyEngineFactory.create_engine("postgresql", {**NET, "pool_size": 7}, "d")

    assert captured["pool_size"] == 7
    assert captured["max_overflow"] == 10
    assert captured["pool_recycle"] == 3600  # antes: sin reciclado en PostgreSQL


def test_sync_engine_sqlite_has_no_pool_sizing() -> None:
    engine = SQLAlchemyEngineFactory.create_engine("sqlite", {"database": ":memory:"}, ":memory:")
    try:
        assert "SingletonThreadPool" in type(engine.pool).__name__
    finally:
        engine.dispose()


def test_async_engine_defaults_recycle_3600_and_reads_conn_params() -> None:
    captured: dict[str, Any] = {}

    def fake_create_async_engine(url: str, **kwargs: Any) -> Any:
        captured.update(kwargs)
        raise _Captured

    async def run() -> None:
        with (
            mock.patch("sqlalchemy.ext.asyncio.create_async_engine", fake_create_async_engine),
            pytest.raises(ConnectionError),
        ):
            await AsyncSQLAlchemyEngineFactory.create_engine("postgresql", {**NET, "max_overflow": 3}, "d")

    asyncio.run(run())
    assert captured["pool_recycle"] == 3600  # antes: 1800
    assert captured["max_overflow"] == 3
    assert captured["pool_size"] == 5


# --- close_timeout en *PoolConfig ---------------------------------------------------------------------------------

POOL_CONFIGS = [
    (MariaDBPoolConfig, NET),
    (MySQLPoolConfig, NET),
    (PostgreSQLPoolConfig, NET),
    (OraclePoolConfig, {"user": "u", "password": "p", "service_name": "s"}),
    (SQLServerPoolConfig, NET),
    (SQLitePoolConfig, {"database": ":memory:"}),
]


@pytest.mark.parametrize(("config_cls", "base"), POOL_CONFIGS)
@pytest.mark.parametrize(
    ("value", "expected"), [(None, 10.0), (3, 3.0), ("2.5", 2.5), (0, None), (-1, None), ("x", 10.0)]
)
def test_pool_config_close_timeout(config_cls: Any, base: dict[str, Any], value: Any, expected: float | None) -> None:
    params = dict(base) if value is None else {**base, "close_timeout": value}
    config = config_cls.from_params(params)
    assert config.close_timeout == expected
    assert "close_timeout" not in config.to_driver_kwargs()


# --- SyncPoolCloseMixin -------------------------------------------------------------------------------------------


class _FakePool(SyncPoolCloseMixin):
    def __init__(self) -> None:
        self._closed = False
        self._close_timeout_seconds = 4.0
        self.returned: list[Any] = []
        self.forgotten: list[Any] = []
        self.close_calls: list[tuple[float | None, bool]] = []

    def close(self, timeout_seconds: float | None = None, force: bool = False) -> None:
        self.close_calls.append((timeout_seconds, force))

    def _return_to_pool(self, connection: Any) -> None:
        self.returned.append(connection)

    def _forget_connection(self, connection: Any) -> None:
        self.forgotten.append(connection)


def test_close_connection_returns_to_open_pool() -> None:
    pool = _FakePool()
    conn = mock.Mock()
    pool.close_connection(conn)
    assert pool.returned == [conn]
    assert pool.forgotten == [conn]
    conn.close.assert_not_called()


def test_close_connection_on_closed_pool_closes_and_swallows_errors() -> None:
    pool = _FakePool()
    pool._closed = True
    conn = mock.Mock()
    conn.close.side_effect = RuntimeError("socket roto")
    pool.close_connection(conn)
    assert pool.returned == []
    assert pool.forgotten == [conn]  # el registro de prestadas se limpia también con el pool cerrado


def test_close_connection_ignores_none() -> None:
    pool = _FakePool()
    pool.close_connection(None)
    assert pool.returned == pool.forgotten == []


def test_del_uses_close_timeout_and_force() -> None:
    pool = _FakePool()
    pool.__del__()
    assert pool.close_calls == [(4.0, True)]


def test_del_without_state_is_noop() -> None:
    pool = _FakePool.__new__(_FakePool)
    pool.__del__()  # __init__ no llegó a fijar _close_timeout_seconds: no lanza


def test_sync_pools_use_mixin() -> None:
    from util_bbdd.connection.mariadb import pool_connection_mariadb
    from util_bbdd.connection.mysql import pool_connection_mysql
    from util_bbdd.connection.oracle import pool_connection_oracle
    from util_bbdd.connection.postgresql import pool_connection_postgresql
    from util_bbdd.connection.sqlite import pool_connection_sqlite
    from util_bbdd.connection.sqlserver import pool_connection_sqlserver

    for module in (
        pool_connection_mariadb,
        pool_connection_mysql,
        pool_connection_oracle,
        pool_connection_postgresql,
        pool_connection_sqlite,
        pool_connection_sqlserver,
    ):
        assert issubclass(module.PoolConnection, SyncPoolCloseMixin), module.__name__
