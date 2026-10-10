"""F3/F4 (v0.41.3): la precarga de SQL Server (``prefetch_table_metadata``, la usan ``dump`` y ``comparar``) no inventa
metadatos para tablas que no existen ni mezcla tablas que solo difieren en mayúsculas (collation sensible).

Requiere ``UTIL_BBDD_TEST_MSSQL_URL`` con permiso para crear bases de datos (``sa`` en el banco).
"""

from __future__ import annotations

import os

from collections.abc import Iterator
from typing import Any

import pytest

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import NoSuchTableError

from util_bbdd.metadata.reflection import prefetch_table_metadata

pytestmark = pytest.mark.integration

ENV = "UTIL_BBDD_TEST_MSSQL_URL"
DB = "zz_util_bbdd_cs"


@pytest.fixture(scope="module")
def cs_engine() -> Iterator[Any]:
    if not os.environ.get(ENV):
        pytest.skip(f"{ENV} no definida")
    base = make_url(os.environ[ENV])
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"IF DB_ID('{DB}') IS NOT NULL DROP DATABASE {DB}"))
        conn.execute(text(f"CREATE DATABASE {DB} COLLATE Latin1_General_CS_AS"))
    engine = create_engine(base.set(database=DB), isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE Users (uid INT NOT NULL CONSTRAINT pk_Users PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE users (id INT NOT NULL CONSTRAINT pk_users PRIMARY KEY, name INT)"))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"ALTER DATABASE {DB} SET SINGLE_USER WITH ROLLBACK IMMEDIATE"))
            conn.execute(text(f"DROP DATABASE {DB}"))
        admin.dispose()


@pytest.mark.parametrize(("name", "columns"), [("users", ["id", "name"]), ("Users", ["uid"])])
def test_tables_that_differ_only_in_case_are_not_mixed(cs_engine: Any, name: str, columns: list[str]) -> None:
    meta = prefetch_table_metadata(inspect(cs_engine), "dbo", [name], kinds=["columns", "pk"])

    assert [c["name"] for c in meta.get("columns", name)] == columns
    assert meta.get("pk", name)["constrained_columns"] == columns[:1]


@pytest.mark.parametrize("kind", ["columns", "pk", "fks"])
def test_missing_or_ambiguous_tables_raise_like_table_by_table(cs_engine: Any, kind: str) -> None:
    meta = prefetch_table_metadata(inspect(cs_engine), "dbo", ["zz_no_existe", "USERS"], kinds=["columns", "pk", "fks"])

    for name in ("zz_no_existe", "USERS"):  # USERS: no existe en una base sensible a mayúsculas
        with pytest.raises(NoSuchTableError):
            meta.get(kind, name)  # type: ignore[call-overload]
