"""P1 Q1 de drivers-connections-audit (FASE 1, 2026-10-08): cifrado de SQL Server.

- Con pymssql (driver por defecto) ``_connect_pymssql`` descartaba ``encryption``: ``encryption="mandatory"`` no tenía
  efecto. pymssql (FreeTDS) acepta ``off`` / ``request`` / ``require``, pero hay builds de FreeTDS (wheel de Windows,
  FreeTDS 1.4.27, comprobado contra el banco) que aceptan ``require`` y no cifran: con ``mandatory`` se verifica la
  sesión con ``sys.dm_exec_connections.encrypt_option`` y se falla si no va cifrada (sin ``VIEW SERVER STATE``
  solo se avisa).
- pyodbc / aioodbc: la cadena ODBC llevaba ``Server={host},puerto`` (el puerto fuera de las llaves del escapado
  CNX-02), que el Driver Manager rechaza (``01S00``): ninguna conexión pyodbc/aioodbc de la librería conectaba.
"""

from __future__ import annotations

from typing import Any

import pytest

from util_bbdd._core.exceptions import ConnectionError
from util_bbdd.connection.sqlserver.async_connection_sqlserver import AsyncSQLServerConnection
from util_bbdd.connection.sqlserver.connection_sqlserver import SQLServerConnection

BASE: dict[str, Any] = {"host": "h", "user": "u", "password": "p", "database": "d"}


class _Cursor:
    def __init__(self, conn: _Connection) -> None:
        self._conn = conn

    def execute(self, sql: str) -> None:
        if self._conn.permission_error:
            raise PermissionError("VIEW SERVER STATE permission was denied")
        self._conn.executed.append(sql)

    def fetchone(self) -> tuple[Any, ...]:
        return (self._conn.encrypt_option,)

    def close(self) -> None:
        return None


class _Connection:
    def __init__(self, encrypt_option: str) -> None:
        self.encrypt_option = encrypt_option
        self.executed: list[str] = []
        self.closed = False
        self.permission_error = False

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def close(self) -> None:
        self.closed = True


def _fake_pymssql(monkeypatch: pytest.MonkeyPatch, encrypt_option: str = "TRUE") -> tuple[dict[str, Any], _Connection]:
    pymssql = pytest.importorskip("pymssql")
    received: dict[str, Any] = {}
    conn = _Connection(encrypt_option)

    def _connect(**kwargs: Any) -> _Connection:
        received.update(kwargs)
        return conn

    monkeypatch.setattr(pymssql, "connect", _connect)
    return received, conn


@pytest.mark.parametrize(("encryption", "expected"), [("mandatory", "require"), ("off", "off")])
def test_pymssql_receives_explicit_encryption(monkeypatch: pytest.MonkeyPatch, encryption: str, expected: str) -> None:
    received, _conn = _fake_pymssql(monkeypatch)

    SQLServerConnection.connect({**BASE, "encryption": encryption}, driver="pymssql")

    assert received["encryption"] == expected


def test_pymssql_optional_encryption_keeps_freetds_default(monkeypatch: pytest.MonkeyPatch) -> None:
    received, conn = _fake_pymssql(monkeypatch)

    SQLServerConnection.connect({**BASE, "encryption": "optional"}, driver="pymssql")

    assert "encryption" not in received
    assert conn.executed == []  # sin verificación extra fuera de "mandatory"


def test_pymssql_never_receives_odbc_only_options(monkeypatch: pytest.MonkeyPatch) -> None:
    received, _conn = _fake_pymssql(monkeypatch)

    SQLServerConnection.connect({**BASE, "trust_cert": True, "use_mars": True}, driver="pymssql")

    assert not {"trust_cert", "use_mars", "driver_name", "sql_server_driver"} & set(received)


def test_pymssql_mandatory_encryption_accepts_encrypted_session(monkeypatch: pytest.MonkeyPatch) -> None:
    _received, conn = _fake_pymssql(monkeypatch, encrypt_option="TRUE")

    assert SQLServerConnection.connect({**BASE, "encryption": "mandatory"}, driver="pymssql") is conn
    assert conn.executed == [SQLServerConnection._ENCRYPT_OPTION_SQL]


def test_pymssql_mandatory_encryption_fails_closed_on_plain_session(monkeypatch: pytest.MonkeyPatch) -> None:
    _received, conn = _fake_pymssql(monkeypatch, encrypt_option="FALSE")

    with pytest.raises(ConnectionError, match="mandatory"):
        SQLServerConnection.connect({**BASE, "encryption": "mandatory"}, driver="pymssql")
    assert conn.closed is True


def test_pyodbc_connection_string_keeps_port_inside_server_braces(monkeypatch: pytest.MonkeyPatch) -> None:
    pyodbc = pytest.importorskip("pyodbc")
    received: dict[str, Any] = {}
    monkeypatch.setattr(pyodbc, "connect", lambda conn_str, **_kwargs: received.update(conn_str=conn_str) or "conn")

    SQLServerConnection.connect({**BASE, "port": 51433}, driver="pyodbc")

    assert "Server={h,51433};" in received["conn_str"]


def test_aioodbc_dsn_keeps_port_inside_server_braces() -> None:
    dsn = AsyncSQLServerConnection._build_dsn({**BASE, "port": 51433})

    assert "Server={h,51433};" in dsn


@pytest.mark.parametrize(("encryption", "odbc_value"), [("mandatory", "yes"), ("optional", "no"), ("off", "no")])
def test_odbc_encrypt_uses_values_valid_in_driver_17_and_18(
    monkeypatch: pytest.MonkeyPatch, encryption: str, odbc_value: str
) -> None:
    """ODBC Driver 18 rechaza ``Encrypt=off`` y Driver 17 solo admite yes/no (comprobado contra el banco)."""
    pyodbc = pytest.importorskip("pyodbc")
    received: dict[str, Any] = {}
    monkeypatch.setattr(pyodbc, "connect", lambda conn_str, **_kwargs: received.update(conn_str=conn_str) or "conn")

    SQLServerConnection.connect({**BASE, "encryption": encryption}, driver="pyodbc")

    assert f"Encrypt={odbc_value};" in received["conn_str"]
    assert f"Encrypt={odbc_value};" in AsyncSQLServerConnection._build_dsn({**BASE, "encryption": encryption})


def test_pymssql_mandatory_encryption_only_warns_without_view_server_state(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _received, conn = _fake_pymssql(monkeypatch, encrypt_option="FALSE")
    conn.permission_error = True

    assert SQLServerConnection.connect({**BASE, "encryption": "mandatory"}, driver="pymssql") is conn
    assert conn.closed is False
    assert "VIEW SERVER STATE" in caplog.text
