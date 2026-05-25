"""Tests para el soporte de OVERRIDING SYSTEM VALUE en bulk_insert_from_df."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert
from sqlalchemy.schema import Identity

from util_bbdd.bulk._support.sql_helpers import (
    build_override_identity_text_stmt,
    generate_insert_sql,
    generate_insert_sql_override_identity,
)
from util_bbdd.bulk._support.validation import detect_always_identity_columns
from util_bbdd.bulk.crud import bulk_crud

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def always_identity_table() -> Table:
    return Table(
        "items",
        MetaData(),
        Column("id", Integer, Identity(always=True), primary_key=True),
        Column("name", String(50)),
    )


@pytest.fixture
def by_default_identity_table() -> Table:
    return Table(
        "items",
        MetaData(),
        Column("id", Integer, Identity(always=False), primary_key=True),
        Column("name", String(50)),
    )


@pytest.fixture
def no_identity_table() -> Table:
    return Table(
        "items",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
    )


# ---------------------------------------------------------------------------
# detect_always_identity_columns
# ---------------------------------------------------------------------------


def test_detect_always_identity_columns_detects_always_true(always_identity_table: Table) -> None:
    result = detect_always_identity_columns(["id", "name"], always_identity_table)

    assert result == ["id"]


def test_detect_always_identity_columns_ignores_by_default(by_default_identity_table: Table) -> None:
    result = detect_always_identity_columns(["id", "name"], by_default_identity_table)

    assert result == []


def test_detect_always_identity_columns_ignores_non_identity(no_identity_table: Table) -> None:
    result = detect_always_identity_columns(["id", "name"], no_identity_table)

    assert result == []


def test_detect_always_identity_columns_ignores_columns_absent_from_df(always_identity_table: Table) -> None:
    result = detect_always_identity_columns(["name"], always_identity_table)

    assert result == []


# ---------------------------------------------------------------------------
# generate_insert_sql_override_identity
# ---------------------------------------------------------------------------


def test_generate_insert_sql_override_identity_injects_clause(sqlite_engine, always_identity_table: Table) -> None:
    stmt = insert(always_identity_table)
    records = [{"id": 1, "name": "Alice"}]

    sql_lines = generate_insert_sql_override_identity(stmt, records, sqlite_engine.dialect)

    assert len(sql_lines) == 1
    assert "OVERRIDING SYSTEM VALUE" in sql_lines[0]
    assert sql_lines[0].index("OVERRIDING SYSTEM VALUE") < sql_lines[0].index("VALUES")


def test_generate_insert_sql_regular_has_no_override_clause(sqlite_engine, always_identity_table: Table) -> None:
    stmt = insert(always_identity_table)
    records = [{"id": 1, "name": "Alice"}]

    sql_lines = generate_insert_sql(stmt, records, sqlite_engine.dialect)

    assert "OVERRIDING SYSTEM VALUE" not in sql_lines[0]


def test_generate_insert_sql_override_identity_generates_one_line_per_record(
    sqlite_engine, always_identity_table: Table
) -> None:
    stmt = insert(always_identity_table)
    records = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    sql_lines = generate_insert_sql_override_identity(stmt, records, sqlite_engine.dialect)

    assert len(sql_lines) == 2
    assert all("OVERRIDING SYSTEM VALUE" in line for line in sql_lines)


# ---------------------------------------------------------------------------
# build_override_identity_text_stmt
# ---------------------------------------------------------------------------


def test_build_override_identity_text_stmt_contains_clause(sqlite_engine, always_identity_table: Table) -> None:
    stmt = build_override_identity_text_stmt(always_identity_table, ["id", "name"], sqlite_engine.dialect)

    sql = str(stmt)
    assert "OVERRIDING SYSTEM VALUE" in sql
    assert ":id" in sql
    assert ":name" in sql


# ---------------------------------------------------------------------------
# bulk_crud.bulk_insert_from_df – comportamiento PostgreSQL
# ---------------------------------------------------------------------------


def _make_pg_bulk_manager(mock_pg_engine: Any) -> bulk_crud:
    return bulk_crud(engine=mock_pg_engine)


def test_bulk_insert_raises_when_always_identity_and_no_override(
    mock_postgresql_engine, always_identity_table: Table
) -> None:
    manager = _make_pg_bulk_manager(mock_postgresql_engine)
    df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})

    with patch.object(manager, "reflect_table", return_value=always_identity_table):
        with pytest.raises(ValueError, match="GENERATED ALWAYS AS IDENTITY"):
            manager.bulk_insert_from_df(df, "items", generar_sql=False)


def test_bulk_insert_no_raise_when_always_identity_and_override_true(
    mock_postgresql_engine, always_identity_table: Table
) -> None:
    manager = _make_pg_bulk_manager(mock_postgresql_engine)
    df = pd.DataFrame({"id": [1], "name": ["Alice"]})

    with patch.object(manager, "reflect_table", return_value=always_identity_table):
        with patch("util_bbdd.bulk.crud.build_override_identity_text_stmt", return_value=MagicMock()):
            with patch.object(manager, "_BulkCrud__ejecutar_batch_stmt"):
                # No debe lanzar ValueError
                manager.bulk_insert_from_df(df, "items", generar_sql=False, override_identity=True)


def test_bulk_insert_no_raise_on_other_dialect_with_always_identity(
    mock_sqlite_engine, always_identity_table: Table
) -> None:
    manager = bulk_crud(engine=mock_sqlite_engine)
    df = pd.DataFrame({"id": [1], "name": ["Alice"]})

    with patch.object(manager, "reflect_table", return_value=always_identity_table):
        with patch.object(manager, "_BulkCrud__ejecutar_batch_stmt"):
            # Sin override_identity=True y sin PostgreSQL: no debe lanzar ValueError
            manager.bulk_insert_from_df(df, "items", generar_sql=False)


def test_bulk_insert_no_raise_when_by_default_identity_and_no_override(
    mock_postgresql_engine, by_default_identity_table: Table
) -> None:
    manager = _make_pg_bulk_manager(mock_postgresql_engine)
    df = pd.DataFrame({"id": [1], "name": ["Alice"]})

    with patch.object(manager, "reflect_table", return_value=by_default_identity_table):
        with patch.object(manager, "_BulkCrud__ejecutar_batch_stmt"):
            # GENERATED BY DEFAULT no debe bloquearse
            manager.bulk_insert_from_df(df, "items", generar_sql=False)
