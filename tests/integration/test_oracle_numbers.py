"""U-9.1 (G44 de util_bbdd_web): ``NUMBER`` de Oracle sin pasar por ``float`` contra un Oracle real, sync y async.

``execute_custom_*`` y ``execute_query_*`` dan ``Decimal`` en los ``NUMBER`` con escala o sin restricción y no enteros,
``int`` en los enteros, y dejan ``FLOAT``/``BINARY_DOUBLE`` como ``float``. El catálogo no cambia: el conversor va en
el cursor de la consulta, no en la conexión. Se salta si no hay servidor configurado::

    UTIL_BBDD_TEST_ORACLE_URL="oracle+oracledb://usuario:clave@servidor:1521/?service_name=FREEPDB1" \\
        python -m pytest tests/integration/test_oracle_numbers.py
"""

from __future__ import annotations

import asyncio
import json
import os

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from sqlalchemy.engine import make_url

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.metadata import Kind
from util_bbdd.query.registry import QueryRegistry

URL_ENV = "UTIL_BBDD_TEST_ORACLE_URL"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get(URL_ENV), reason=f"{URL_ENV} no definida"),
]

SQL = (
    "SELECT CAST(12345678901234567.891 AS NUMBER(38,3)) AS escala, 1.5 AS medio, -0.5 AS menos, 7 AS siete, "
    "CAST(7 AS NUMBER(10)) AS n10, CAST(7 AS INTEGER) AS entero, 1e30 AS grande, "
    "123456789012345678901234567890 AS treinta, CAST(1.5 AS FLOAT) AS flotante, "
    "CAST(1.5 AS BINARY_DOUBLE) AS doble, CAST(NULL AS NUMBER) AS nulo FROM dual"
)
EXPECTED = (
    Decimal("12345678901234567.891"),
    Decimal("1.5"),
    Decimal("-0.5"),
    7,
    7,
    7,
    10**30,
    123456789012345678901234567890,
    1.5,
    1.5,
    None,
)


def _conn_params(**extra: Any) -> dict[str, Any]:
    url = make_url(os.environ[URL_ENV])
    return {
        "host": url.host,
        "port": url.port or 1521,
        "user": url.username,
        "password": url.password,
        "service_name": url.query.get("service_name"),
        **extra,
    }


def _check(row: Any) -> None:
    assert tuple(row) == EXPECTED
    assert [type(value) for value in row] == [type(value) for value in EXPECTED]


@pytest.fixture
def queries_file(tmp_path: Path) -> Path:
    path = tmp_path / "queries.json"
    path.write_text(json.dumps({"oracle": {"numeros": SQL}}), encoding="utf-8")
    return path


@pytest.fixture
def table() -> Iterator[str]:
    """Tabla con ``NUMBER(38,3)`` para comprobar que el catálogo sigue dando la precisión y la escala como ``int``."""
    with SyncDatabaseManager("oracle", _conn_params(), use_pool=False) as mgr:
        try:
            mgr.execute_custom_result("DROP TABLE zz_g44")
        except Exception:
            pass
        mgr.execute_custom_result("CREATE TABLE zz_g44 (importe NUMBER(38,3), cantidad NUMBER)")
        try:
            yield "ZZ_G44"
        finally:
            mgr.execute_custom_result("DROP TABLE zz_g44")


def _columns(mgr: SyncDatabaseManager, table: str) -> list[tuple[Any, ...]]:
    snapshot = mgr.get_schema_metadata(kinds={Kind.TABLES, Kind.COLUMNS}, tables=[table])
    return [(c.name, c.data_type, c.precision, c.scale) for c in snapshot.columns(table)]


def test_sync_numbers_keep_precision(queries_file: Path, table: str) -> None:
    with SyncDatabaseManager("oracle", _conn_params(), use_pool=False) as fresh:
        before = _columns(fresh, table)

    with SyncDatabaseManager("oracle", _conn_params(pool_size=1), queries_file=queries_file) as mgr:
        result = mgr.execute_custom_result(SQL)
        _check(result.rows[0])
        _check(mgr.execute_custom_result(SQL, read_only=True).rows[0])
        _check(mgr.execute_custom_many(SQL)[0])
        _check(mgr.execute_custom_one(SQL) or ())
        _check(mgr.execute_query_many("numeros")[0])

        # misma conexión del pool (pool_size=1): ni ella ni el catálogo cambian
        conn = mgr.get_connection()
        try:
            assert conn.outputtypehandler is None
        finally:
            mgr.release_connection(conn)
        after = _columns(mgr, table)

    assert after == before
    assert all(type(p) in (int, type(None)) and type(s) in (int, type(None)) for _, _, p, s in after)


def test_async_numbers_keep_precision(queries_file: Path) -> None:
    async def run() -> None:
        async with AsyncDatabaseManager("oracle", _conn_params(pool_size=1)) as mgr:
            mgr.query_executor = AsyncQueryExecutor(
                connection_provider=mgr.get_connection,
                connection_releaser=mgr.release_connection,
                registry=QueryRegistry(queries_file),
            )
            _check((await mgr.execute_custom_result(SQL)).rows[0])
            _check((await mgr.execute_custom_result(SQL, read_only=True)).rows[0])
            _check((await mgr.execute_custom_many(SQL))[0])
            _check((await mgr.execute_query_many("numeros"))[0])

            conn = await mgr.get_connection()
            try:
                assert conn.outputtypehandler is None
            finally:
                await mgr.release_connection(conn)

    asyncio.run(run())
