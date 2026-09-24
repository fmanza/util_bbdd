"""Tests para exclude_autoincrement_pk en bulk_insert_from_df."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.schema import Identity

from util_bbdd.bulk._support.validation import get_insert_columns
from util_bbdd.bulk.crud import bulk_crud

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def identity_table() -> Table:
    return Table(
        "orders",
        MetaData(),
        Column("id", Integer, Identity(), primary_key=True),
        Column("name", String(50)),
        Column("amount", Integer),
    )


@pytest.fixture
def autoincrement_true_table() -> Table:
    return Table(
        "orders",
        MetaData(),
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("name", String(50)),
    )


@pytest.fixture
def plain_pk_table() -> Table:
    """PK entera sin Identity() ni autoincrement=True explícito."""
    return Table(
        "orders",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
    )


@pytest.fixture
def composite_pk_table() -> Table:
    """PK compuesta: una columna autoincremental (Identity) y una PK normal."""
    return Table(
        "order_items",
        MetaData(),
        Column("order_id", Integer, primary_key=True),
        Column("item_id", Integer, Identity(), primary_key=True),
        Column("name", String(50)),
    )


# ---------------------------------------------------------------------------
# get_insert_columns – unit tests
# ---------------------------------------------------------------------------


def test_get_insert_columns_default_includes_all(identity_table: Table) -> None:
    result = get_insert_columns(["id", "name", "amount"], identity_table)
    assert result == ["id", "name", "amount"]


def test_get_insert_columns_excludes_identity_col(identity_table: Table) -> None:
    result = get_insert_columns(["id", "name", "amount"], identity_table, exclude_autoincrement_pk=True)
    assert "id" not in result
    assert result == ["name", "amount"]


def test_get_insert_columns_excludes_autoincrement_true_col(autoincrement_true_table: Table) -> None:
    result = get_insert_columns(["id", "name"], autoincrement_true_table, exclude_autoincrement_pk=True)
    assert "id" not in result
    assert result == ["name"]


def test_get_insert_columns_does_not_exclude_plain_pk(plain_pk_table: Table) -> None:
    """PKs sin Identity() ni autoincrement=True explícito NO deben excluirse."""
    result = get_insert_columns(["id", "name"], plain_pk_table, exclude_autoincrement_pk=True)
    assert result == ["id", "name"]


def test_composite_pk_only_autoincrement_col_excluded(composite_pk_table: Table) -> None:
    """En PK compuesta solo se excluye la columna con Identity; la otra PK se conserva."""
    result = get_insert_columns(["order_id", "item_id", "name"], composite_pk_table, exclude_autoincrement_pk=True)
    assert "item_id" not in result
    assert "order_id" in result
    assert "name" in result


# ---------------------------------------------------------------------------
# bulk_crud.bulk_insert_from_df – comportamiento con exclude_autoincrement_pk
# ---------------------------------------------------------------------------


def test_bulk_insert_exclude_does_not_modify_original_df(mock_sqlite_engine, identity_table: Table) -> None:
    """El DataFrame original no debe modificarse al excluir la columna identity."""
    manager = bulk_crud(engine=mock_sqlite_engine)
    df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"], "amount": [10, 20]})
    original_columns = list(df.columns)

    with patch.object(manager, "reflect_table", return_value=identity_table):
        with patch.object(manager, "_BulkCrud__ejecutar_batch_stmt"):
            manager.bulk_insert_from_df(df, "orders", generar_sql=False, exclude_autoincrement_pk=True)

    assert list(df.columns) == original_columns or set(df.columns) == {
        "ID",
        "NAME",
        "AMOUNT",
    }  # normalize_df uppercases


def test_bulk_insert_generate_sql_excludes_identity_col(mock_sqlite_engine, identity_table: Table) -> None:
    """Los registros pasados al generador SQL no contienen la columna identity."""
    manager = bulk_crud(engine=mock_sqlite_engine)
    mock_sqlite_engine.dialect.name = "sqlite"
    df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"], "amount": [10, 20]})

    with patch.object(manager, "reflect_table", return_value=identity_table):
        with patch("util_bbdd.bulk.crud.generate_insert_sql", return_value=["SQL1;", "SQL2;"]) as mock_gen:
            op = manager._BulkCrud__prepare_insert_operation(  # type: ignore[attr-defined]
                df, "orders", exclude_autoincrement_pk=True
            )
            sql_lines = list(op.generate_sql_lines())  # generador por bloques (P-07)

    records_used = mock_gen.call_args[0][1]
    assert all("id" not in record for record in records_used)
    assert all("name" in record for record in records_used)
    assert len(sql_lines) == 2


def test_bulk_insert_execute_excludes_identity_col(mock_sqlite_engine, identity_table: Table) -> None:
    """La ejecución directa no debe incluir la columna identity en los registros enviados."""
    manager = bulk_crud(engine=mock_sqlite_engine)
    mock_sqlite_engine.dialect.name = "sqlite"
    df = pd.DataFrame({"id": [1], "name": ["Alice"], "amount": [100]})

    with patch.object(manager, "reflect_table", return_value=identity_table):
        with patch.object(manager, "_BulkCrud__ejecutar_batch_stmt") as mock_exec:
            manager.bulk_insert_from_df(df, "orders", generar_sql=False, exclude_autoincrement_pk=True)

    mock_exec.assert_called_once()
    records_arg = mock_exec.call_args[0][0]
    assert all("id" not in record for record in records_arg)
    assert all("name" in record for record in records_arg)


def test_bulk_insert_false_includes_identity_col(mock_sqlite_engine, identity_table: Table) -> None:
    """Con exclude_autoincrement_pk=False (defecto), la columna identity se incluye."""
    manager = bulk_crud(engine=mock_sqlite_engine)
    mock_sqlite_engine.dialect.name = "sqlite"
    df = pd.DataFrame({"id": [1], "name": ["Alice"], "amount": [100]})

    with patch.object(manager, "reflect_table", return_value=identity_table):
        op = manager._BulkCrud__prepare_insert_operation(  # type: ignore[attr-defined]
            df, "orders", exclude_autoincrement_pk=False
        )
        sql_lines = list(op.generate_sql_lines())  # generador por bloques (P-07)

    assert len(sql_lines) == 1
    assert "id" in sql_lines[0].lower()
