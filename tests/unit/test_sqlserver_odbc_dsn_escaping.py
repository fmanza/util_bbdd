"""Tests de regresión CNX-02 (AUDIT_CODE 2026-09-22).

Tanto ``SQLServerConnection._connect_pyodbc`` (sync) como
``AsyncSQLServerConnection._build_dsn`` (async, también usado por el pool async) construían el
DSN ODBC por interpolación sin escapar ``;``/``{``/``}``: un valor con ``;`` podía inyectar
atributos adicionales en la cadena de conexión (p. ej. ``TrustServerCertificate=yes``).
"""

from __future__ import annotations

import sys
import types

from typing import Any

import pytest

from util_bbdd.connection.sqlserver.async_connection_sqlserver import AsyncSQLServerConnection
from util_bbdd.connection.sqlserver.connection_sqlserver import SQLServerConnection


class TestEscapeOdbcValue:
    @pytest.mark.parametrize(
        "escaper", [SQLServerConnection._escape_odbc_value, AsyncSQLServerConnection._escape_odbc_value]
    )
    def test_wraps_value_in_braces(self, escaper) -> None:
        assert escaper("myhost") == "{myhost}"

    @pytest.mark.parametrize(
        "escaper", [SQLServerConnection._escape_odbc_value, AsyncSQLServerConnection._escape_odbc_value]
    )
    def test_doubles_internal_closing_brace(self, escaper) -> None:
        assert escaper("weird}value") == "{weird}}value}"

    @pytest.mark.parametrize(
        "escaper", [SQLServerConnection._escape_odbc_value, AsyncSQLServerConnection._escape_odbc_value]
    )
    def test_semicolon_stays_inside_braces(self, escaper) -> None:
        escaped = escaper("secret;TrustServerCertificate=yes")
        assert escaped == "{secret;TrustServerCertificate=yes}"


class TestBuildDsnAsync:
    def test_dsn_confines_semicolon_payload_within_braces(self) -> None:
        dsn = AsyncSQLServerConnection._build_dsn(
            {
                "host": "localhost",
                "user": "sa",
                "password": "secret;APP=EvilInjectedApp;PWD=x",
                "database": "master",
                "port": 1433,
            }
        )

        # El payload queda contenido dentro de un único par de llaves de PWD: no puede cerrar
        # el atributo PWD prematuramente e inyectar un atributo "APP" propio no braceado.
        assert "PWD={secret;APP=EvilInjectedApp;PWD=x};" in dsn
        assert "APP=EvilInjectedApp;" not in dsn.replace("PWD={secret;APP=EvilInjectedApp;PWD=x};", "")

    def test_dsn_confines_semicolon_payload_in_user_and_database(self) -> None:
        dsn = AsyncSQLServerConnection._build_dsn(
            {
                "host": "localhost",
                "user": "sa;APP=EvilInjectedApp",
                "password": "pw",
                "database": "master;DROP DATABASE x",
                "port": 1433,
            }
        )

        assert "UID={sa;APP=EvilInjectedApp};" in dsn
        assert "Database={master;DROP DATABASE x};" in dsn
        stripped = dsn.replace("UID={sa;APP=EvilInjectedApp};", "").replace("Database={master;DROP DATABASE x};", "")
        assert "APP=EvilInjectedApp;" not in stripped
        assert "DROP DATABASE x;" not in stripped
        assert dsn.count("Encrypt=") == 1


class _FakePyodbcModule(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("pyodbc")
        self.last_conn_str: str | None = None

    def connect(self, conn_str: str, timeout: Any = None) -> object:
        self.last_conn_str = conn_str
        return object()


def test_sync_connect_pyodbc_confines_semicolon_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_pyodbc = _FakePyodbcModule()
    monkeypatch.setitem(sys.modules, "pyodbc", fake_pyodbc)

    SQLServerConnection._connect_pyodbc(
        {
            "host": "localhost",
            "user": "sa",
            "password": "secret;APP=EvilInjectedApp;PWD=x",
            "database": "master",
            "port": 1433,
        }
    )

    assert fake_pyodbc.last_conn_str is not None
    assert "PWD={secret;APP=EvilInjectedApp;PWD=x};" in fake_pyodbc.last_conn_str
    stripped = fake_pyodbc.last_conn_str.replace("PWD={secret;APP=EvilInjectedApp;PWD=x};", "")
    assert "APP=EvilInjectedApp;" not in stripped
