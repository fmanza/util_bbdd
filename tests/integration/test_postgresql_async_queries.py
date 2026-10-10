"""Consultas de ``AsyncDatabaseManager("postgresql")`` (asyncpg) contra un PostgreSQL real (hotfix de 1.1.0).

Hasta v1.0.0 toda consulta async en PostgreSQL fallaba: el ejecutor usaba la API DB-API (``cursor().execute``), que
asyncpg no tiene. Se salta si no hay servidor configurado::

    UTIL_BBDD_TEST_POSTGRESQL_URL="postgresql+psycopg://usuario:clave@servidor:5432/basedatos" \\
        python -m pytest tests/integration/test_postgresql_async_queries.py

Crea y borra una tabla ``zz_pg_async_<sufijo>`` en el schema por defecto de la URL. asyncpg tipa los parámetros en el
servidor (no interpola en el cliente como psycopg): un parámetro sin contexto de tipo (``SELECT $1``) es ``text`` y se
necesita un cast (``%(n)s::int``).
"""

from __future__ import annotations

import asyncio
import os
import uuid

from typing import Any

import pytest

from sqlalchemy.engine import make_url

from util_bbdd import AsyncDatabaseManager
from util_bbdd.exceptions import DatabaseOperationError

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


@pytest.mark.parametrize("use_pool", [True, False])
def test_custom_queries_with_and_without_params(use_pool: bool) -> None:
    table = f"zz_pg_async_{uuid.uuid4().hex[:8]}"

    async def run() -> None:
        async with AsyncDatabaseManager("postgresql", _conn_params(), use_pool=use_pool) as mgr:
            await mgr.execute_custom_many(f"CREATE TABLE {table} (id INT PRIMARY KEY, nombre TEXT)")
            try:
                # Con un VALUES de una fila el servidor tipa los parámetros por las columnas destino.
                await mgr.execute_custom_many(
                    f"INSERT INTO {table} VALUES (%(id)s, %(nombre)s)", {"id": 1, "nombre": "a"}
                )
                await mgr.execute_custom_many(f"INSERT INTO {table} VALUES (2, 'b%')")
                assert await mgr.execute_custom_one("SELECT 1 AS x") == (1,)
                assert await mgr.execute_custom_many(f"SELECT id, nombre FROM {table} ORDER BY id") == [
                    (1, "a"),
                    (2, "b%"),
                ]
                assert await mgr.execute_custom_one(f"SELECT nombre FROM {table} WHERE id = :id", {"id": 2}) == ("b%",)
                assert await mgr.execute_custom_one(f"SELECT id FROM {table} WHERE id = %(id)s", {"id": 99}) is None
                assert await mgr.execute_custom_one("SELECT :v::int + 1", {"v": 41}) == (42,)
            finally:
                await mgr.execute_custom_many(f"DROP TABLE IF EXISTS {table}")

    asyncio.run(run())


def test_concurrent_queries_share_the_pool() -> None:
    async def run() -> list[Any]:
        async with AsyncDatabaseManager("postgresql", {**_conn_params(), "pool_size": 5}) as mgr:
            return list(
                await asyncio.gather(*(mgr.execute_custom_one("SELECT %(n)s::int", {"n": n}) for n in range(20)))
            )

    assert asyncio.run(run()) == [(n,) for n in range(20)]


def test_server_errors_are_wrapped() -> None:
    async def run() -> None:
        async with AsyncDatabaseManager("postgresql", _conn_params(), use_pool=False) as mgr:
            await mgr.execute_custom_many("SELECT * FROM zz_pg_async_no_existe")

    with pytest.raises(DatabaseOperationError, match="zz_pg_async_no_existe"):
        asyncio.run(run())
