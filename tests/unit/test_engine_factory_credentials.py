"""Hotfix P0 de drivers-connections-audit (FASE 1, 2026-10-08): S1 y S4 en las factories de Engine.

- **S1**: usuario y contraseña se interpolaban sin escapar en la URL. Con la contraseña
  ``a@evil.example:3306/x?`` el host efectivo pasaba a ser ``evil.example`` (credenciales enviadas a otro servidor).
- **S4**: ``create_engine``/``create_async_engine`` recibían solo la URL, así que el camino SQLAlchemy (bulk, dump,
  comparar) ignoraba TLS y charset de ``conn_params``. El Engine usa ahora la conexión nativa de
  ``ConnectionFactory`` (``creator``/``async_creator``), la misma que los managers.
"""

from __future__ import annotations

import asyncio

from typing import Any

import pytest

from sqlalchemy.engine import make_url

from util_bbdd.connection.factory import ConnectionFactory
from util_bbdd.factory.async_sqlalchemy_engine_factory import AsyncSQLAlchemyEngineFactory
from util_bbdd.factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory

USER = "app@corp"
PASSWORD = "a@evil.example:3306/x?#%"
HOST = "db.prod"
PARAMS: dict[str, Any] = {"host": HOST, "user": USER, "password": PASSWORD}

SYNC_BUILDERS = [
    ("mariadb", lambda: SQLAlchemyEngineFactory._build_mariadb_connection_string({**PARAMS, "port": 3306}, "ventas")),
    ("mysql", lambda: SQLAlchemyEngineFactory._build_mysql_connection_string({**PARAMS, "port": 3306}, "ventas")),
    (
        "postgresql",
        lambda: SQLAlchemyEngineFactory._build_postgresql_connection_string({**PARAMS, "port": 5432}, "ventas"),
    ),
    (
        "sqlserver-pymssql",
        lambda: SQLAlchemyEngineFactory._build_sqlserver_connection_string({**PARAMS, "port": 1433}, "ventas"),
    ),
    (
        "sqlserver-pyodbc",
        lambda: SQLAlchemyEngineFactory._build_sqlserver_connection_string(
            {**PARAMS, "port": 1433}, "ventas", "pyodbc"
        ),
    ),
]

ASYNC_BUILDERS = [
    (
        "mariadb",
        lambda: AsyncSQLAlchemyEngineFactory._build_mariadb_connection_string({**PARAMS, "port": 3306}, "ventas"),
    ),
    (
        "postgresql",
        lambda: AsyncSQLAlchemyEngineFactory._build_postgresql_connection_string({**PARAMS, "port": 5432}, "ventas"),
    ),
    (
        "sqlserver",
        lambda: AsyncSQLAlchemyEngineFactory._build_sqlserver_connection_string({**PARAMS, "port": 1433}, "ventas"),
    ),
]


@pytest.mark.parametrize(
    ("name", "build"), SYNC_BUILDERS + ASYNC_BUILDERS, ids=lambda v: v if isinstance(v, str) else ""
)
def test_credentials_with_url_metacharacters_do_not_change_host(name: str, build: Any) -> None:
    url = make_url(build())

    assert url.host == HOST
    assert url.username == USER
    assert url.password == PASSWORD
    assert url.database == "ventas"


@pytest.mark.parametrize(
    "build",
    [
        lambda: SQLAlchemyEngineFactory._build_oracle_connection_string({**PARAMS, "service_name": "ORCL"}, ""),
        lambda: AsyncSQLAlchemyEngineFactory._build_oracle_connection_string({**PARAMS, "service_name": "ORCL"}, ""),
    ],
    ids=["sync", "async"],
)
def test_oracle_credentials_with_url_metacharacters_do_not_change_host(build: Any) -> None:
    url = make_url(build())

    assert url.host == HOST
    assert url.username == USER
    assert url.password == PASSWORD
    assert url.query["service_name"] == "ORCL"


def test_sanitized_conn_str_does_not_leak_password_suffix() -> None:
    conn_str = SQLAlchemyEngineFactory._build_postgresql_connection_string(
        {"host": "h", "user": "u", "password": "ab@cd"}, "d"
    )

    assert "cd" not in SQLAlchemyEngineFactory._sanitize_conn_str(conn_str).split("@")[0]


class _FakeConnection:
    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def execute(self, _statement: Any) -> None:
        return None


class _FakeEngine:
    def connect(self) -> _FakeConnection:
        return _FakeConnection()


def _capture_sync_engine(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def _fake_create_engine(conn_str: str, **kwargs: Any) -> _FakeEngine:
        captured["conn_str"] = conn_str
        captured["kwargs"] = kwargs
        return _FakeEngine()

    monkeypatch.setattr("sqlalchemy.create_engine", _fake_create_engine)
    return captured


def _capture_native_connect(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def _fake_create_connection(
        db_type: str,
        conn_params: dict[str, Any],
        db_validator: Any = None,
        sql_server_driver: str = "pymssql",
        found_rows: bool = False,
    ) -> str:
        calls.append({"db_type": db_type, "params": conn_params, "driver": sql_server_driver, "found_rows": found_rows})
        return "dbapi-connection"

    monkeypatch.setattr(ConnectionFactory, "create_connection", staticmethod(_fake_create_connection))
    return calls


def test_sync_engine_uses_native_connection_with_tls_params(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_sync_engine(monkeypatch)
    calls = _capture_native_connect(monkeypatch)
    conn_params = {"host": "h", "user": "u", "password": "p", "port": 3306, "ssl_ca": "/ca.pem", "charset": "utf8mb4"}

    SQLAlchemyEngineFactory.create_engine("mysql", conn_params, "ventas")
    creator = captured["kwargs"]["creator"]

    assert creator() == "dbapi-connection"
    call = calls[0]
    assert call["db_type"] == "mysql"
    assert call["params"]["ssl_ca"] == "/ca.pem"
    assert call["params"]["charset"] == "utf8mb4"
    assert call["params"]["database"] == "ventas"


@pytest.mark.parametrize(("db_type", "found_rows"), [("mysql", True), ("mariadb", True), ("postgresql", False)])
def test_sync_engine_keeps_found_rows_like_sqlalchemy_dialect(
    monkeypatch: pytest.MonkeyPatch, db_type: str, found_rows: bool
) -> None:
    """Con ``creator`` SQLAlchemy no aplica el CLIENT.FOUND_ROWS de sus dialectos MySQL/MariaDB (``rowcount``)."""
    captured = _capture_sync_engine(monkeypatch)
    calls = _capture_native_connect(monkeypatch)

    SQLAlchemyEngineFactory.create_engine(db_type, {"host": "h", "user": "u", "password": "p"}, "ventas")
    captured["kwargs"]["creator"]()

    assert calls[0]["found_rows"] is found_rows


def test_sync_engine_passes_sql_server_driver_to_native_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_sync_engine(monkeypatch)
    calls = _capture_native_connect(monkeypatch)
    conn_params = {"host": "h", "user": "u", "password": "p", "encryption": "mandatory"}

    SQLAlchemyEngineFactory.create_engine("sqlserver", conn_params, "ventas", sql_server_driver="pyodbc")
    captured["kwargs"]["creator"]()

    assert calls[0]["driver"] == "pyodbc"
    assert calls[0]["params"]["encryption"] == "mandatory"


def test_mysql_native_connect_found_rows_sets_client_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    import pymysql

    from pymysql.constants import CLIENT

    from util_bbdd.connection.mysql.connection_mysql import MySQLConnection

    received: dict[str, Any] = {}
    monkeypatch.setattr(pymysql, "connect", lambda **kwargs: received.update(kwargs) or "conn")
    params = {"host": "h", "user": "u", "password": "p", "database": "d"}

    MySQLConnection.connect(params, found_rows=True)
    assert received["client_flag"] == CLIENT.FOUND_ROWS

    received.clear()
    MySQLConnection.connect({**params, "client_flag": 1 << 16})  # MULTI_STATEMENTS: sigue fuera de la lista blanca
    assert "client_flag" not in received


def test_mariadb_native_connect_found_rows_sets_client_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    mariadb = pytest.importorskip("mariadb")
    from mariadb.constants import CLIENT

    from util_bbdd.connection.mariadb.connection_mariadb import MariaDBConnection

    received: dict[str, Any] = {}
    monkeypatch.setattr(mariadb, "connect", lambda **kwargs: received.update(kwargs) or "conn")

    MariaDBConnection.connect({"host": "h", "user": "u", "password": "p", "database": "d"}, found_rows=True)

    assert received["client_flag"] == CLIENT.FOUND_ROWS


def test_sync_sqlite_engine_keeps_url_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_sync_engine(monkeypatch)

    SQLAlchemyEngineFactory.create_engine("sqlite", {"database": ":memory:"}, ":memory:")

    assert "creator" not in captured["kwargs"]


class _FakeAsyncConnection:
    async def __aenter__(self) -> _FakeAsyncConnection:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def execute(self, _statement: Any) -> None:
        return None


class _FakeAsyncEngine:
    def connect(self) -> _FakeAsyncConnection:
        return _FakeAsyncConnection()


def _run_async_creator(monkeypatch: pytest.MonkeyPatch, db_type: str, conn_params: dict[str, Any]) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    call: dict[str, Any] = {}

    def _fake_create_async_engine(conn_str: str, **kwargs: Any) -> _FakeAsyncEngine:
        captured["kwargs"] = kwargs
        return _FakeAsyncEngine()

    async def _fake_create_async_connection(db_type: str, conn_params: dict[str, Any], **kwargs: Any) -> str:
        call.update({"db_type": db_type, "params": conn_params, "kwargs": kwargs})
        return "async-dbapi-connection"

    monkeypatch.setattr("sqlalchemy.ext.asyncio.create_async_engine", _fake_create_async_engine)
    monkeypatch.setattr(ConnectionFactory, "create_async_connection", staticmethod(_fake_create_async_connection))

    async def _run() -> Any:
        await AsyncSQLAlchemyEngineFactory.create_engine(db_type, conn_params, "ventas")
        return await captured["kwargs"]["async_creator"]()

    assert asyncio.run(_run()) == "async-dbapi-connection"
    return call


def test_async_engine_uses_native_async_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    conn_params = {"host": "h", "user": "u", "password": "p", "sslmode": "require"}

    call = _run_async_creator(monkeypatch, "postgresql", conn_params)

    assert call["db_type"] == "postgresql"
    assert call["params"]["sslmode"] == "require"
    assert call["params"]["database"] == "ventas"
    assert call["kwargs"] == {}


def test_async_engine_keeps_found_rows_for_mysql_family(monkeypatch: pytest.MonkeyPatch) -> None:
    call = _run_async_creator(monkeypatch, "mysql", {"host": "h", "user": "u", "password": "p"})

    assert call["kwargs"] == {"found_rows": True}
