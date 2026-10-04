"""``metadata.storage``: SQL de inventario de almacenamiento con ``:nombre`` (E2 de ADR-003)."""

from __future__ import annotations

import asyncio

from collections.abc import Mapping
from typing import Any

import pytest

from util_bbdd.metadata._paramstyle import placeholders
from util_bbdd.metadata.ddl import native_table_ddl, native_table_ddl_sql
from util_bbdd.metadata.storage import (
    aread_storage_inventory,
    read_storage_inventory,
    storage_query,
    storage_query_params,
)


class _Fetch:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        self.calls.append((sql, dict(params)))
        return [("fila",)]


@pytest.mark.parametrize(
    ("engine", "name", "params"),
    [
        ("mariadb", "ficheros_fisicos", ("schema",)),
        ("mysql", "temp_tablespaces", ()),
        ("oracle", "ficheros_fisicos", ("tablespace",)),
        ("oracle", "user_tablespaces", ()),
        ("postgresql", "ficheros_fisicos", ("tablespace",)),
        ("sqlserver", "temp_tablespaces", ()),
        ("sqlite", "sqlite_file_summary", ()),
    ],
)
def test_queries_use_bind_parameters(engine: str, name: str, params: tuple[str, ...]) -> None:
    sql = storage_query(engine, name)
    assert sql is not None and "{" not in sql
    assert storage_query_params(engine, name) == params


def test_unknown_query_or_engine() -> None:
    assert storage_query("hsqldb", "temp_tablespaces") is None
    assert storage_query("sqlite", "temp_storage_variables") is None
    assert storage_query_params("hsqldb", "ficheros_fisicos") == ()


def test_inventory_runs_the_engine_queries() -> None:
    fetch = _Fetch()
    inventory = read_storage_inventory(fetch, "postgresql", "public", "pg_default")
    assert set(inventory) == {"primary", "temp_tablespaces"}
    assert fetch.calls[0][1]["tablespace"] == "pg_default"
    sqlite = read_storage_inventory(_Fetch(), "sqlite", "main")
    assert list(sqlite) == ["primary", "sqlite_file_summary", "temp_tablespaces"]


def test_inventory_requires_tablespace_and_known_engine() -> None:
    with pytest.raises(ValueError, match="Oracle"):
        read_storage_inventory(_Fetch(), "oracle", "SCOTT")
    with pytest.raises(ValueError, match="no soportado"):
        read_storage_inventory(_Fetch(), "redshift", "public")
    assert read_storage_inventory(_Fetch(), "hsqldb", "PUBLIC") == {"primary": []}


def test_async_inventory_matches_sync() -> None:
    async def fetch(sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        return [("fila",)]

    assert asyncio.run(aread_storage_inventory(fetch, "mariadb", "db")) == read_storage_inventory(
        _Fetch(), "mariadb", "db"
    )


@pytest.mark.parametrize("engine", ["postgresql", "oracle", "sqlserver", "sqlite", "hsqldb"])
def test_native_table_ddl_sql_binds_schema_and_table(engine: str) -> None:
    sql = native_table_ddl_sql(engine)
    assert sql is not None and "{tabla}" not in sql
    assert "table_name" in placeholders(sql)


def test_native_table_ddl_text() -> None:
    assert native_table_ddl([]) == ""
    assert native_table_ddl([(None,)]) == ""
    assert native_table_ddl([("\n  CREATE TABLE t",)]) == "\n  CREATE TABLE t"
    assert native_table_ddl_sql("mysql") is None
