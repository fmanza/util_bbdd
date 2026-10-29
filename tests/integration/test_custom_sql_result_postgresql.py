"""U-8.4 (G42 de util_bbdd_web): ``execute_custom_result`` contra un PostgreSQL real, sync (psycopg) y async (asyncpg).

Comprueba las columnas (también sin filas y repetidas) y que, con ``read_only=True`` y ``timeout``, la consulta se
corta en el servidor (``SET LOCAL statement_timeout``, D8-4). Se salta si no hay servidor configurado::

    UTIL_BBDD_TEST_POSTGRESQL_URL="postgresql+psycopg://usuario:clave@servidor:5432/basedatos" \\
        python -m pytest tests/integration/test_custom_sql_result_postgresql.py
"""

from __future__ import annotations

import asyncio
import os
import time

from typing import Any

import pytest

from sqlalchemy.engine import make_url

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.exceptions import DatabaseOperationError, QueryTimeoutError

URL_ENV = "UTIL_BBDD_TEST_POSTGRESQL_URL"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get(URL_ENV), reason=f"{URL_ENV} no definida"),
]


def _conn_params() -> dict[str, Any]:
    url = make_url(os.environ[URL_ENV])
    return {
        "host": url.host or "localhost",
        "port": url.port or 5432,
        "user": url.username,
        "password": url.password,
        "database": url.database,
    }


def _sqlstate(err: BaseException) -> str | None:
    cause = err.__cause__
    return getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)


def test_sync_columns_and_server_timeout() -> None:
    with SyncDatabaseManager("postgresql", _conn_params(), use_pool=False) as mgr:
        result = mgr.execute_custom_result("SELECT 1 AS a, 2 AS a WHERE false", read_only=True)
        assert (result.columns, result.rows) == (("a", "a"), [])

        start = time.monotonic()
        with pytest.raises(QueryTimeoutError) as caught:
            mgr.execute_custom_result("SELECT pg_sleep(10)", timeout=1, read_only=True)
        assert time.monotonic() - start < 5  # lo corta el servidor: el plazo del cliente no interrumpe la consulta
        assert _sqlstate(caught.value) == "57014"

        with pytest.raises(DatabaseOperationError):
            mgr.execute_custom_result("CREATE TEMP TABLE zz_ro (id INT)", read_only=True)
        # la sesión vuelve a su estado: sin statement_timeout ni solo lectura
        assert mgr.execute_custom_result("SHOW statement_timeout").rows == [("0",)]


def test_async_columns_and_server_timeout() -> None:
    async def run() -> None:
        async with AsyncDatabaseManager("postgresql", _conn_params(), use_pool=False) as mgr:
            result = await mgr.execute_custom_result("SELECT 1 AS a, 2 AS a WHERE false", read_only=True)
            assert (result.columns, result.rows) == (("a", "a"), [])
            limited = await mgr.execute_custom_result("SELECT generate_series(1, 5) AS n", max_rows=2)
            assert (limited.columns, limited.rows) == (("n",), [(1,), (2,)])

            with pytest.raises(QueryTimeoutError):
                await mgr.execute_custom_result("SELECT pg_sleep(10)", timeout=1, read_only=True)
            assert (await mgr.execute_custom_result("SHOW statement_timeout")).rows == [("0",)]

    asyncio.run(run())
