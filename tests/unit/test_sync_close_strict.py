"""Unit tests for strict sync close contract (timeout/force/leak-safe)."""

from __future__ import annotations

import importlib
import logging
import sys
import threading
import types

from queue import LifoQueue
from threading import Lock
from typing import Any, cast

import pytest

from util_bbdd.connection.protocols import ConnectionPoolProtocol
from util_bbdd.exceptions import DatabaseOperationError, PoolTimeoutError
from util_bbdd.managers import SyncDatabaseManager


def _import_mariadb_pool_module(monkeypatch: pytest.MonkeyPatch):
    sys.modules.pop("util_bbdd.connection.mariadb.pool_connection_mariadb", None)
    fake_mariadb = types.SimpleNamespace(Connection=object, ConnectionPool=object)
    monkeypatch.setitem(sys.modules, "mariadb", fake_mariadb)
    return importlib.import_module("util_bbdd.connection.mariadb.pool_connection_mariadb")


def _import_oracle_pool_module(monkeypatch: pytest.MonkeyPatch):
    sys.modules.pop("util_bbdd.connection.oracle.pool_connection_oracle", None)
    fake_oracledb = types.SimpleNamespace(ConnectionPool=object)
    monkeypatch.setitem(sys.modules, "oracledb", fake_oracledb)
    return importlib.import_module("util_bbdd.connection.oracle.pool_connection_oracle")


class _BlockingCloseWithTerminate:
    def __init__(self) -> None:
        self.terminated = False

    def close(self) -> None:
        threading.Event().wait()

    def terminate(self) -> None:
        self.terminated = True


class _BlockingOracleClose:
    def __init__(self) -> None:
        self.force_used = False

    def close(self, force: bool = False) -> None:
        if force:
            self.force_used = True
            return
        threading.Event().wait()


class _BlockingClose:
    def close(self) -> None:
        threading.Event().wait()


class _CountedConnection:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class _PoolForManager:
    def __init__(self) -> None:
        self.called_with: tuple[float | None, bool] | None = None

    def get_connection(self) -> Any:
        raise NotImplementedError

    def close_connection(self, connection: Any) -> None:
        _ = connection

    def close(self, timeout_seconds: float | None = None, force: bool = False) -> None:
        self.called_with = (timeout_seconds, force)
        raise RuntimeError("pool close failed")


class _CursorForManager:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _ConnForManager:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_mariadb_pool_force_close_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _import_mariadb_pool_module(monkeypatch)
    pool_connection_class = module.PoolConnection

    pool = object.__new__(pool_connection_class)
    pool.logger = logging.getLogger(__name__)
    pool._closed = False
    pool._close_timeout_seconds = 0.01
    fake_pool = _BlockingCloseWithTerminate()
    pool.pool = cast(Any, fake_pool)

    pool.close(timeout_seconds=None, force=True)

    assert fake_pool.terminated is True
    assert pool.pool is None


def test_postgresql_pool_force_close_on_timeout() -> None:
    from util_bbdd.connection.postgresql.pool_connection_postgresql import PoolConnection

    pool = object.__new__(PoolConnection)
    pool.logger = logging.getLogger(__name__)
    pool._closed = False
    pool._close_timeout_seconds = 0.01
    fake_pool = _BlockingCloseWithTerminate()
    pool.pool = cast(Any, fake_pool)

    pool.close(timeout_seconds=None, force=True)

    assert fake_pool.terminated is True
    assert pool.pool is None


def test_oracle_pool_force_close_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _import_oracle_pool_module(monkeypatch)
    pool_connection_class = module.PoolConnection

    pool = object.__new__(pool_connection_class)
    pool.logger = logging.getLogger(__name__)
    pool._closed = False
    pool._close_timeout_seconds = 0.01
    fake_pool = _BlockingOracleClose()
    pool.pool = cast(Any, fake_pool)

    pool.close(timeout_seconds=None, force=True)

    assert fake_pool.force_used is True
    assert pool.pool is None


def test_sqlite_pool_raises_timeout_without_force() -> None:
    from util_bbdd.connection.sqlite.pool_connection_sqlite import PoolConnection

    pool = object.__new__(PoolConnection)
    pool.logger = logging.getLogger(__name__)
    pool._closed = False
    pool._close_timeout_seconds = 0.01
    pool.connection = _BlockingClose()

    with pytest.raises(PoolTimeoutError):
        pool.close(timeout_seconds=None, force=False)


def test_sqlserver_pool_close_also_closes_leased_connections() -> None:
    from util_bbdd.connection.sqlserver.pool_connection_sqlserver import PoolConnection

    available_conn = _CountedConnection()
    leased_conn = _CountedConnection()

    pool = object.__new__(PoolConnection)
    pool.logger = logging.getLogger(__name__)
    pool._closed = False
    pool._close_timeout_seconds = 0.1
    pool.pool_size = 1
    pool.max_overflow = 1
    pool.pool_timeout = 1
    pool._available = LifoQueue(maxsize=1)
    pool._available.put_nowait(available_conn)
    pool._lock = Lock()
    pool._total_connections = 2
    pool._leased_connections = {id(leased_conn): leased_conn}

    pool.close(timeout_seconds=None, force=False)

    assert available_conn.close_calls == 1
    assert leased_conn.close_calls == 1
    assert pool._leased_connections == {}
    assert pool._total_connections == 0


def test_database_manager_close_propagates_errors_and_attempts_all_resources() -> None:
    fake_pool = _PoolForManager()
    manager = object.__new__(SyncDatabaseManager)
    manager.logger = logging.getLogger(__name__)
    manager.db_type = "sqlite"
    manager._default_close_timeout_seconds = 0.1
    manager.pool_connection = cast(ConnectionPoolProtocol, fake_pool)
    manager.cursor = _CursorForManager()
    manager._connection = _ConnForManager()

    with pytest.raises(DatabaseOperationError):
        manager.close(timeout_seconds=None, force=False)

    assert manager.pool_connection is None
    assert manager.cursor is None
    assert manager._connection is None
    assert fake_pool.called_with == (0.1, False)
