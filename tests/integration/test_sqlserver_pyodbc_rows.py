"""SQL Server con pyodbc (sync) y aioodbc (async) contra un servidor real: forma de las filas y pool (hotfix de 1.1.0).

Hasta v1.0.0, con ``sql_server_driver="pyodbc"`` (sync) y siempre en async, ``execute_custom_one`` devolvía
``((1, 'a'),)`` y ``execute_custom_many`` una sola «fila» con todas dentro: ``pyodbc.Row`` no es ``tuple``. Además, el
pool async ignoraba ``driver_name`` y usaba el ODBC Driver 17. Se salta sin ``UTIL_BBDD_TEST_MSSQL_URL`` o sin un ODBC
Driver 17/18 instalado::

    UTIL_BBDD_TEST_MSSQL_URL="mssql+pymssql://sa:clave@servidor:1433/basedatos" \\
        python -m pytest tests/integration/test_sqlserver_pyodbc_rows.py
"""

from __future__ import annotations

import asyncio
import os

from typing import Any

import pytest

from sqlalchemy.engine import make_url

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager

URL_ENV = "UTIL_BBDD_TEST_MSSQL_URL"


def _odbc_driver() -> str | None:
    try:
        import pyodbc
    except ImportError:
        return None
    installed = [
        name for name in pyodbc.drivers() if name in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server")
    ]
    return installed[0] if installed else None


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get(URL_ENV), reason=f"{URL_ENV} no definida"),
    pytest.mark.skipif(_odbc_driver() is None, reason="sin pyodbc u ODBC Driver 17/18 for SQL Server"),
]

SQL_ONE = "SELECT 1 AS x, 'a' AS y"
SQL_MANY = "SELECT v FROM (VALUES (1), (2), (3)) AS t(v) ORDER BY v"


def _conn_params(**extra: Any) -> dict[str, Any]:
    url = make_url(os.environ[URL_ENV])
    return {
        "host": url.host or "localhost",
        "port": url.port or 1433,
        "user": url.username,
        "password": url.password,
        "database": url.database,
        "driver_name": _odbc_driver(),
        "trust_cert": True,
        **extra,
    }


@pytest.mark.parametrize("use_pool", [True, False])
def test_sync_pyodbc_returns_one_tuple_per_row(use_pool: bool) -> None:
    with SyncDatabaseManager("sqlserver", _conn_params(sql_server_driver="pyodbc"), use_pool=use_pool) as mgr:
        assert mgr.execute_custom_one(SQL_ONE) == (1, "a")
        assert mgr.execute_custom_many(SQL_MANY) == [(1,), (2,), (3,)]


@pytest.mark.parametrize("use_pool", [True, False])
def test_async_aioodbc_connects_with_the_driver_name_and_returns_one_tuple_per_row(use_pool: bool) -> None:
    async def run() -> tuple[Any, Any]:
        async with AsyncDatabaseManager("sqlserver", _conn_params(), use_pool=use_pool) as mgr:
            return await mgr.execute_custom_one(SQL_ONE), await mgr.execute_custom_many(SQL_MANY)

    one, many = asyncio.run(run())
    assert one == (1, "a")
    assert many == [(1,), (2,), (3,)]
