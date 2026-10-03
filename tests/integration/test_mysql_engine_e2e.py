"""Motor ``mysql`` (PyMySQL/aiomysql) contra un MySQL real: managers, catálogo y metadatos.

Se salta si no hay servidor configurado. Para ejecutarlo apunta ``UTIL_BBDD_TEST_MYSQL_URL`` a un servidor de
PRUEBAS (p. ej. el del banco: ``scripts/bench_env.example.sh``)::

    UTIL_BBDD_TEST_MYSQL_URL="mysql+pymysql://usuario:clave@servidor:3306/basedatos" \\
        python -m pytest tests/integration/test_mysql_engine_e2e.py

Crea y borra tablas y una vista con el prefijo ``zz_mysql_e2e_`` en la base de datos de la URL.
"""

from __future__ import annotations

import asyncio
import os
import uuid

from collections.abc import Iterator
from typing import Any

import pytest

from sqlalchemy.engine import make_url

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd._core.exceptions import DatabaseException

URL_ENV = "UTIL_BBDD_TEST_MYSQL_URL"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get(URL_ENV), reason=f"{URL_ENV} no definida"),
]


def _conn_params() -> dict[str, Any]:
    url = make_url(os.environ[URL_ENV])
    return {
        "host": url.host or "localhost",
        "port": url.port or 3306,
        "user": url.username,
        "password": url.password,
        "database": url.database,
    }


@pytest.fixture(scope="module")
def objects() -> Iterator[dict[str, str]]:
    """Tabla padre/hija con FK, índice único y vista; se borran al terminar."""
    suffix = uuid.uuid4().hex[:8]
    names = {
        "parent": f"zz_mysql_e2e_p_{suffix}",
        "child": f"zz_mysql_e2e_c_{suffix}",
        "view": f"zz_mysql_e2e_v_{suffix}",
    }
    manager = SyncDatabaseManager("mysql", _conn_params(), use_pool=False)
    ddl = [
        f"CREATE TABLE {names['parent']} (id INT PRIMARY KEY, nombre VARCHAR(50) NOT NULL DEFAULT 'x', "
        f"total DECIMAL(10,2), UNIQUE KEY uq_{suffix} (nombre)) COMMENT='padre'",
        f"CREATE TABLE {names['child']} (id INT PRIMARY KEY, parent_id INT, CONSTRAINT FK_{suffix} "
        f"FOREIGN KEY (parent_id) REFERENCES {names['parent']}(id))",
        f"CREATE VIEW {names['view']} AS SELECT id, nombre FROM {names['parent']} WHERE nombre LIKE 'a%'",
    ]
    cleanup = [
        f"DROP VIEW IF EXISTS {names['view']}",
        f"DROP TABLE IF EXISTS {names['child']}",
        f"DROP TABLE IF EXISTS {names['parent']}",
    ]
    cursor = manager._connection.cursor()
    try:
        for stmt in cleanup + ddl:
            cursor.execute(stmt)
        manager._connection.commit()
        yield names
    finally:
        for stmt in cleanup:
            cursor.execute(stmt)
        manager._connection.commit()
        manager.close()


@pytest.mark.parametrize("use_pool", [True, False], ids=["pool", "directa"])
def test_sync_manager_catalog_and_metadata(objects: dict[str, str], use_pool: bool) -> None:
    manager = SyncDatabaseManager("mysql", _conn_params(), use_pool=use_pool)
    try:
        assert manager.get_database_version()
        table_names = {t.name for t in manager.get_tables()}
        assert {objects["parent"], objects["child"]} <= table_names

        columns = {c.name: c for c in manager.get_columns(objects["parent"])}
        assert columns["nombre"].data_type == "varchar(50)"
        assert columns["nombre"].default == "'x'"  # el catálogo entrecomilla los literales de MySQL
        pk = manager.get_primary_keys(objects["parent"])
        assert pk is not None and pk.columns == ("id",)
        assert [row[0] for row in manager.execute_query_many("claves_unicas", tabla=objects["parent"])] == [
            f"uq_{objects['parent'].rsplit('_', 1)[1]}"
        ]
        fk = manager.get_foreign_keys(objects["child"])
        assert fk and fk[0].ref_table == objects["parent"]

        view_ddl = manager.get_view_ddl(objects["view"])
        assert view_ddl.startswith(f"CREATE VIEW {objects['view']} AS")
        assert "CREATE TABLE" in manager.get_ddl(objects["parent"])
    finally:
        manager.close()


def test_storage_inventory(objects: dict[str, str]) -> None:
    manager = SyncDatabaseManager("mysql", _conn_params(), use_pool=False)
    try:
        try:
            inventory = manager.get_storage_inventory()
        except DatabaseException as err:
            # temp_tablespaces lee information_schema.FILES, que en MySQL exige el privilegio global PROCESS (el banco
            # se lo concede a bench: docker-compose.bench.yml).
            if "PROCESS" in str(err):
                pytest.skip("el usuario de la URL no tiene el privilegio PROCESS (information_schema.FILES)")
            raise
        assert set(inventory) == {"primary", "temp_tablespaces"}
        assert objects["parent"] in {row[1] for row in inventory["primary"]}
    finally:
        manager.close()


def test_percent_literal_with_and_without_params() -> None:
    manager = SyncDatabaseManager("mysql", _conn_params(), use_pool=False)
    try:
        assert manager.execute_custom_many("SELECT 'a%b' AS v WHERE 'abc' LIKE 'a%'") == [("a%b",)]
        assert manager.execute_custom_many("SELECT %(x)s AS v WHERE 'abc' LIKE %(p)s", {"x": 7, "p": "a%"}) == [(7,)]
    finally:
        manager.close()


@pytest.mark.parametrize("use_pool", [True, False], ids=["pool", "directa"])
def test_async_manager(objects: dict[str, str], use_pool: bool) -> None:
    async def scenario() -> None:
        manager = AsyncDatabaseManager("mysql", _conn_params(), use_pool=use_pool)
        await manager.init()
        try:
            assert objects["parent"] in {t.name for t in await manager.get_tables()}
            columns = {c.name for c in await manager.get_columns(objects["parent"])}
            assert {"id", "nombre", "total"} <= columns
            assert (await manager.get_view_ddl(objects["view"])).startswith("CREATE VIEW")
        finally:
            await manager.close()

    asyncio.run(scenario())
