"""Driver ODBC de SQL Server por defecto (5.7.0, A2 del plan de pendientes).

Hasta 5.6.0, sin ``driver_name`` se usaba siempre «ODBC Driver 17 for SQL Server» y, con solo el 18 instalado, la
conexión con pyodbc/aioodbc fallaba (``IM002``) hasta indicarlo. Ahora se elige el más reciente instalado.
"""

from __future__ import annotations

import sys
import types

from collections.abc import Iterator
from typing import Any

import pytest

from util_bbdd.connection import build_conn_params
from util_bbdd.connection.config import SQLServerConnectionConfig
from util_bbdd.connection.sqlserver import _odbc_driver
from util_bbdd.connection.sqlserver._odbc_driver import (
    FALLBACK_ODBC_DRIVER,
    default_odbc_driver,
    newest_odbc_driver,
    resolve_odbc_driver,
)
from util_bbdd.connection.sqlserver.async_connection_sqlserver import AsyncSQLServerConnection

pytestmark = pytest.mark.unit

D17 = "ODBC Driver 17 for SQL Server"
D18 = "ODBC Driver 18 for SQL Server"
PARAMS: dict[str, Any] = {"host": "h", "port": 1433, "user": "u", "password": "p", "database": "d"}


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Lista de drivers que devuelve un ``pyodbc`` simulado; la caché se vacía antes y después."""
    drivers: list[str] = []
    monkeypatch.setitem(sys.modules, "pyodbc", types.SimpleNamespace(drivers=lambda: list(drivers)))
    default_odbc_driver.cache_clear()
    yield drivers
    default_odbc_driver.cache_clear()


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        ([D17], D17),
        ([D18], D18),
        ([D17, D18], D18),
        ([D18, D17], D18),
        (["SQL Server", "ODBC Driver 9 for SQL Server", D17], D17),  # 17 > 9: comparación numérica, no de texto
        (["SQL Server", "SQL Server Native Client 11.0", "PostgreSQL Unicode"], None),
        ([], None),
    ],
)
def test_newest_odbc_driver(names: list[str], expected: str | None) -> None:
    assert newest_odbc_driver(names) == expected


@pytest.mark.parametrize(
    ("names", "expected"),
    [([D18], D18), ([D17, D18], D18), ([D17], D17), (["SQL Server"], FALLBACK_ODBC_DRIVER), ([], FALLBACK_ODBC_DRIVER)],
)
def test_default_is_the_newest_installed_or_17(installed: list[str], names: list[str], expected: str) -> None:
    installed.extend(names)

    assert default_odbc_driver() == expected
    assert resolve_odbc_driver({}) == expected
    assert resolve_odbc_driver({"driver_name": ""}) == expected  # vacío = no indicado


def test_explicit_driver_name_always_wins(installed: list[str]) -> None:
    installed.append(D18)

    assert resolve_odbc_driver({"driver_name": "Mi DSN de ODBC"}) == "Mi DSN de ODBC"


def test_without_pyodbc_keeps_driver_17(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pyodbc", None)  # import pyodbc -> ImportError
    default_odbc_driver.cache_clear()
    try:
        assert default_odbc_driver() == FALLBACK_ODBC_DRIVER
    finally:
        default_odbc_driver.cache_clear()


def test_driver_manager_error_keeps_driver_17(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> list[str]:
        raise RuntimeError("unixODBC sin configurar")

    monkeypatch.setitem(sys.modules, "pyodbc", types.SimpleNamespace(drivers=broken))
    default_odbc_driver.cache_clear()
    try:
        assert default_odbc_driver() == FALLBACK_ODBC_DRIVER
    finally:
        default_odbc_driver.cache_clear()


def test_detection_is_cached(installed: list[str]) -> None:
    installed.append(D17)
    assert default_odbc_driver() == D17

    installed.append(D18)  # instalar un driver con el proceso en marcha no cambia el elegido
    assert default_odbc_driver() == D17


def test_config_from_params_pyodbc_and_pymssql(installed: list[str]) -> None:
    installed.append(D18)

    assert SQLServerConnectionConfig.from_params({**PARAMS, "sql_server_driver": "pyodbc"}).driver_name == D18
    explicit = SQLServerConnectionConfig.from_params({**PARAMS, "sql_server_driver": "pyodbc", "driver_name": D17})
    assert explicit.driver_name == D17
    # pymssql no usa ODBC: ni se consulta pyodbc ni cambia el valor de siempre
    assert SQLServerConnectionConfig.from_params(PARAMS).driver_name == FALLBACK_ODBC_DRIVER


def test_pymssql_config_keeps_an_explicit_driver_name(installed: list[str]) -> None:
    # AUDIT_CODE: con pymssql, un driver_name indicado se conserva (to_driver_kwargs(driver="pyodbc") lo usa)
    installed.append(D18)
    config = SQLServerConnectionConfig.from_params({**PARAMS, "driver_name": "Mi DSN"})

    assert config.driver_name == "Mi DSN"
    assert config.to_driver_kwargs(driver="pyodbc")["driver_name"] == "Mi DSN"


def test_build_conn_params(installed: list[str]) -> None:
    installed.append(D18)

    assert build_conn_params("sqlserver", **PARAMS, sql_server_driver="pyodbc")["driver_name"] == D18
    assert build_conn_params("sqlserver", **PARAMS)["driver_name"] == FALLBACK_ODBC_DRIVER


def test_async_dsn_uses_the_detected_driver(installed: list[str]) -> None:
    installed.extend([D17, D18])

    assert f"Driver={{{D18}}};" in AsyncSQLServerConnection._build_dsn(PARAMS)
    assert f"Driver={{{D17}}};" in AsyncSQLServerConnection._build_dsn({**PARAMS, "driver_name": D17})


def test_module_exports() -> None:
    assert _odbc_driver.__all__ == [
        "FALLBACK_ODBC_DRIVER",
        "default_odbc_driver",
        "newest_odbc_driver",
        "resolve_odbc_driver",
    ]
