"""Tests para el soporte de SET IDENTITY_INSERT ON/OFF en generación SQL de SQL Server."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.schema import Identity

from util_bbdd.bulk._support.sql_helpers import (
    should_wrap_identity_insert,
    wrap_identity_insert_sql,
)
from util_bbdd.bulk.crud import bulk_crud

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def identity_table() -> Table:
    return Table(
        "orders",
        MetaData(),
        Column("id", Integer, Identity(), primary_key=True),
        Column("name", String(50)),
    )


@pytest.fixture
def no_identity_table() -> Table:
    return Table(
        "orders",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
    )


def _mssql_dialect() -> Any:
    d = MagicMock()
    d.name = "mssql"
    d.identifier_preparer.format_table.return_value = "[dbo].[orders]"
    return d


def _sqlite_dialect() -> Any:
    d = MagicMock()
    d.name = "sqlite"
    return d


# ---------------------------------------------------------------------------
# should_wrap_identity_insert
# ---------------------------------------------------------------------------


def test_should_wrap_returns_true_for_mssql_with_identity_col(identity_table: Table) -> None:
    result = should_wrap_identity_insert(identity_table, ["id", "name"], _mssql_dialect())
    assert result is True


def test_should_wrap_returns_false_when_identity_col_absent_from_records(identity_table: Table) -> None:
    result = should_wrap_identity_insert(identity_table, ["name"], _mssql_dialect())
    assert result is False


def test_should_wrap_returns_false_for_mssql_without_identity_col(no_identity_table: Table) -> None:
    result = should_wrap_identity_insert(no_identity_table, ["id", "name"], _mssql_dialect())
    assert result is False


def test_should_wrap_returns_false_for_non_mssql_dialect(identity_table: Table) -> None:
    for dialect_name in ("sqlite", "postgresql", "oracle", "mysql"):
        d = MagicMock()
        d.name = dialect_name
        assert should_wrap_identity_insert(identity_table, ["id", "name"], d) is False


# ---------------------------------------------------------------------------
# wrap_identity_insert_sql
# ---------------------------------------------------------------------------


def test_wrap_adds_on_at_start_and_off_at_end() -> None:
    lines = ["INSERT INTO [dbo].[orders] ([id], [name]) VALUES (1, 'Alice');"]
    result = wrap_identity_insert_sql(lines, MagicMock(), _mssql_dialect())

    assert result[0] == "SET IDENTITY_INSERT [dbo].[orders] ON;"
    assert result[-1] == "SET IDENTITY_INSERT [dbo].[orders] OFF;"


def test_wrap_preserves_insert_lines_in_middle() -> None:
    lines = [
        "INSERT INTO [dbo].[orders] ([id], [name]) VALUES (1, 'Alice');",
        "INSERT INTO [dbo].[orders] ([id], [name]) VALUES (2, 'Bob');",
    ]
    result = wrap_identity_insert_sql(lines, MagicMock(), _mssql_dialect())

    assert len(result) == 4
    assert result[1] == lines[0]
    assert result[2] == lines[1]


def test_wrap_on_and_off_appear_exactly_once() -> None:
    lines = [f"INSERT INTO [dbo].[orders] VALUES ({i});" for i in range(5)]
    result = wrap_identity_insert_sql(lines, MagicMock(), _mssql_dialect())

    on_count = sum(1 for line in result if "IDENTITY_INSERT" in line and "ON" in line)
    off_count = sum(1 for line in result if "IDENTITY_INSERT" in line and "OFF" in line)
    assert on_count == 1
    assert off_count == 1


def test_wrap_uses_preparer_format_table() -> None:
    dialect = _mssql_dialect()
    dialect.identifier_preparer.format_table.return_value = "[myschema].[orders]"
    result = wrap_identity_insert_sql(["INSERT INTO ...;"], MagicMock(), dialect)

    assert "[myschema].[orders]" in result[0]
    assert "[myschema].[orders]" in result[-1]


# ---------------------------------------------------------------------------
# bulk_crud.bulk_insert_from_df – generación SQL con IDENTITY INSERT
# ---------------------------------------------------------------------------


def test_generate_sql_mssql_identity_wraps_with_on_off(mock_sqlserver_engine, identity_table: Table) -> None:
    manager = bulk_crud(engine=mock_sqlserver_engine)
    mock_sqlserver_engine.dialect.name = "mssql"
    mock_sqlserver_engine.dialect.identifier_preparer.format_table.return_value = "[dbo].[orders]"
    df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})

    with patch.object(manager, "reflect_table", return_value=identity_table):
        op = manager._bulk_crud__prepare_insert_operation(df, "orders")  # type: ignore[attr-defined]
        sql_lines = op.generate_sql_lines()

    assert sql_lines[0] == "SET IDENTITY_INSERT [dbo].[orders] ON;"
    assert sql_lines[-1] == "SET IDENTITY_INSERT [dbo].[orders] OFF;"
    assert len(sql_lines) == 4  # ON + 2 INSERTs + OFF


def test_generate_sql_mssql_no_identity_col_no_wrap(mock_sqlserver_engine, no_identity_table: Table) -> None:
    manager = bulk_crud(engine=mock_sqlserver_engine)
    mock_sqlserver_engine.dialect.name = "mssql"
    df = pd.DataFrame({"id": [1], "name": ["Alice"]})

    with patch.object(manager, "reflect_table", return_value=no_identity_table):
        op = manager._bulk_crud__prepare_insert_operation(df, "orders")  # type: ignore[attr-defined]
        sql_lines = op.generate_sql_lines()

    assert all("IDENTITY_INSERT" not in line for line in sql_lines)


def test_generate_sql_other_dialect_no_wrap(mock_sqlite_engine, identity_table: Table) -> None:
    manager = bulk_crud(engine=mock_sqlite_engine)
    df = pd.DataFrame({"id": [1], "name": ["Alice"]})

    with patch.object(manager, "reflect_table", return_value=identity_table):
        op = manager._bulk_crud__prepare_insert_operation(df, "orders")  # type: ignore[attr-defined]
        sql_lines = op.generate_sql_lines()

    assert all("IDENTITY_INSERT" not in line for line in sql_lines)


def test_execute_path_unchanged_does_not_call_wrap(mock_sqlserver_engine) -> None:
    """La ejecución directa generar_sql=False delega en SQLAlchemy sin wrapping."""
    # MSSQL normaliza columnas a mayúsculas; la tabla reflejada debe coincidir.
    mssql_table = Table(
        "orders",
        MetaData(),
        Column("ID", Integer, Identity(), primary_key=True),
        Column("NAME", String(50)),
    )
    manager = bulk_crud(engine=mock_sqlserver_engine)
    mock_sqlserver_engine.dialect.name = "mssql"
    df = pd.DataFrame({"ID": [1], "NAME": ["Alice"]})

    with patch.object(manager, "reflect_table", return_value=mssql_table):
        with patch.object(manager, "_bulk_crud__ejecutar_batch_stmt") as mock_exec:
            manager.bulk_insert_from_df(df, "orders", generar_sql=False)

    mock_exec.assert_called_once()
    # El stmt pasado a execute NO es un text() ni contiene wrapping
    stmt_arg = mock_exec.call_args[0][1]
    assert "IDENTITY_INSERT" not in str(stmt_arg)
