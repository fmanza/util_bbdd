"""P2 de drivers-connections-audit (FASE 1, 2026-10-08): SQL Server, SQLite, HSQLDB y Oracle.

- **Q2**: el pool propio de SQL Server abría la conexión de red con el lock cogido (una conexión lenta bloqueaba a
  todos los que pedían conexión) y al agotarse lanzaba ``TimeoutError`` en vez de ``PoolTimeoutError``.
  (**Q3**, valores de ``Encrypt`` para ODBC Driver 17, quedó resuelto en v0.35.6.)
- **L1**: el pool de SQLite ignoraba ``cached_statements``.
- **H1**: HSQLDB validaba ``connection_properties`` pero no las pasaba a ``jaydebeapi.connect``, y registraba la
  ``jdbc_url`` (que puede llevar ``password=``) en DEBUG.
- **H2**: el Engine de SQLAlchemy para HSQLDB se construía como ``hsqldb+pyodbc://sa@…`` (usuario fijo, dialecto
  inexistente, ``jdbc_url`` ignorada): ahora falla con un mensaje claro.
- **O2**: Oracle aceptaba ``protocol`` (p. ej. ``tcps``) y ``encoding`` en ``conn_params`` y los descartaba: con
  ``protocol="tcps"`` la conexión iba por TCP sin TLS. ``encoding`` no lo usa python-oracledb (siempre UTF-8).
"""

from __future__ import annotations

import logging
import threading
import time

from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd._core.exceptions import ConnectionError, PoolTimeoutError, ValidationError
from util_bbdd.connection.hsqldb.connection_hsqldb import HSQLDBConnection
from util_bbdd.connection.oracle import connection_oracle
from util_bbdd.connection.oracle._dsn import build_oracle_dsn
from util_bbdd.connection.sqlite.pool_connection_sqlite import PoolConnection as SQLitePool
from util_bbdd.connection.sqlserver import pool_connection_sqlserver
from util_bbdd.factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory

SQLSERVER: dict[str, Any] = {"host": "h", "user": "u", "password": "p", "database": "d"}


def test_sqlserver_pool_creates_connections_outside_the_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pool_connection_sqlserver.PoolConnection, "_create_connection", lambda self: MagicMock())
    pool = pool_connection_sqlserver.PoolConnection({**SQLSERVER, "pool_size": 1, "max_overflow": 2})
    held_lock_while_connecting: list[bool] = []

    def _slow_connect(self: Any) -> Any:
        held_lock_while_connecting.append(self._lock.locked())
        time.sleep(0.05)
        return MagicMock()

    monkeypatch.setattr(pool_connection_sqlserver.PoolConnection, "_create_connection", _slow_connect)
    first = pool.get_connection()  # la del pool
    threads = [threading.Thread(target=pool.get_connection) for _ in range(2)]  # dos de desbordamiento
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert first is not None
    assert held_lock_while_connecting == [False, False]
    pool._closed = True


def test_sqlserver_pool_exhaustion_raises_pool_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pool_connection_sqlserver.PoolConnection, "_create_connection", lambda self: MagicMock())
    pool = pool_connection_sqlserver.PoolConnection({**SQLSERVER, "pool_size": 1, "max_overflow": 0, "pool_timeout": 0})
    pool.get_connection()

    with pytest.raises(PoolTimeoutError):
        pool.get_connection()
    pool._closed = True


def test_sqlserver_pool_releases_slot_when_overflow_connection_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pool_connection_sqlserver.PoolConnection, "_create_connection", lambda self: MagicMock())
    pool = pool_connection_sqlserver.PoolConnection({**SQLSERVER, "pool_size": 1, "max_overflow": 1})
    pool.get_connection()

    def _fail(self: Any) -> Any:
        raise OSError("red caída")

    monkeypatch.setattr(pool_connection_sqlserver.PoolConnection, "_create_connection", _fail)
    with pytest.raises(OSError):
        pool.get_connection()

    assert pool._total_connections == 1  # el hueco de desbordamiento queda libre
    pool._closed = True


def test_sqlite_pool_applies_cached_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    import sqlite3

    received: dict[str, Any] = {}
    real_connect = sqlite3.connect

    def _connect(*args: Any, **kwargs: Any) -> Any:
        received.update(kwargs)
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", _connect)
    SQLitePool({"database": ":memory:", "cached_statements": 7}).close()

    assert received["cached_statements"] == 7


HSQLDB: dict[str, Any] = {
    "user": "SA",
    "password": "pw",
    "jdbc_url": "jdbc:hsqldb:hsql://db/test;password=secreta",
    "jdbc_jar": "hsqldb.jar",
}


def test_hsqldb_passes_connection_properties_and_hides_url_password(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    jaydebeapi = pytest.importorskip("jaydebeapi")
    received: dict[str, Any] = {}
    monkeypatch.setattr(jaydebeapi, "connect", lambda *args, **kwargs: received.update(args=args) or "conn")

    with caplog.at_level(logging.DEBUG):
        HSQLDBConnection.connect({**HSQLDB, "connection_properties": {"shutdown": "true"}})

    _driver, _url, driver_args, _jars = received["args"]
    assert driver_args == {"user": "SA", "password": "pw", "shutdown": "true"}
    assert "secreta" not in caplog.text


def test_hsqldb_engine_fails_with_clear_message() -> None:
    with pytest.raises((ConnectionError, ValidationError), match="HSQLDB"):
        SQLAlchemyEngineFactory.create_engine("hsqldb", HSQLDB, "test")


def test_oracle_dsn_uses_tcps_protocol() -> None:
    oracledb = pytest.importorskip("oracledb")

    dsn = build_oracle_dsn(oracledb, {"host": "db", "port": 2484, "service_name": "ORCL", "protocol": "tcps"})

    assert "(PROTOCOL=TCPS)" in dsn
    assert "(PROTOCOL=TCP)" not in dsn


def test_oracle_dsn_defaults_to_tcp() -> None:
    oracledb = pytest.importorskip("oracledb")

    assert "(PROTOCOL=TCP)" in build_oracle_dsn(oracledb, {"host": "db", "port": 1521, "sid": "XE"})


def test_oracle_connect_honours_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    oracledb = pytest.importorskip("oracledb")

    received: dict[str, Any] = {}
    monkeypatch.setattr(oracledb, "connect", lambda **kwargs: received.update(kwargs) or "conn")

    connection_oracle.OracleConnection.connect(
        {"user": "u", "password": "p", "host": "db", "port": 2484, "service_name": "ORCL", "protocol": "tcps"}
    )

    assert "(PROTOCOL=TCPS)" in received["dsn"]


def test_oracle_rejects_unknown_protocol() -> None:
    from util_bbdd.connection.config import OracleConnectionConfig

    with pytest.raises(ValueError, match="protocol"):
        OracleConnectionConfig.from_params({"user": "u", "password": "p", "service_name": "S", "protocol": "udp"})
