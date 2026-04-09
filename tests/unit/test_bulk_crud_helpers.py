"""Unit tests for helper behavior in bulk_crud."""

from __future__ import annotations

import re

from collections.abc import Callable
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from sqlalchemy import create_engine

from util_bbdd.bulk._support.sql_helpers import compile_stmt_with_binary_support, format_sql_param_value
from util_bbdd.bulk.crud import bulk_crud


def _get_private_method(manager: bulk_crud, name: str) -> Callable[..., Any]:
    return cast(Callable[..., Any], getattr(manager, name))


class _FakeCompiled:
    def __init__(self) -> None:
        self.params = {"first": b"\xaa", "second": "O'Reilly"}

    def __str__(self) -> str:
        return "INSERT INTO t VALUES (%s, %s)"


class _BinaryFallbackStmt:
    def compile(self, dialect=None, compile_kwargs=None):  # noqa: ANN001, ANN201
        if compile_kwargs and compile_kwargs.get("literal_binds"):
            raise RuntimeError("BLOB literal rendering is not supported")
        return _FakeCompiled()


class _QmarkCompiled:
    def __init__(self) -> None:
        self.params = {"first": b"\xaa", "second": "O'Reilly"}
        self.positiontup = ["first", "second"]

    def __str__(self) -> str:
        return "INSERT INTO t VALUES (?, ?)"


class _QmarkBinaryFallbackStmt:
    def compile(self, dialect=None, compile_kwargs=None):  # noqa: ANN001, ANN201
        if compile_kwargs and compile_kwargs.get("literal_binds"):
            raise RuntimeError("binary literal rendering is not supported")
        return _QmarkCompiled()


class _NamedCompiled:
    def __init__(self) -> None:
        self.params = {"first": b"\xaa", "second": "O'Reilly"}

    def __str__(self) -> str:
        return "INSERT INTO t VALUES (:first, :second)"


class _NamedBinaryFallbackStmt:
    def compile(self, dialect=None, compile_kwargs=None):  # noqa: ANN001, ANN201
        if compile_kwargs and compile_kwargs.get("literal_binds"):
            raise RuntimeError("binary literal rendering is not supported")
        return _NamedCompiled()


class _LiteralStmt:
    def compile(self, dialect=None, compile_kwargs=None):  # noqa: ANN001, ANN201
        if compile_kwargs == {"literal_binds": True}:
            return "SELECT 1"
        raise AssertionError("Unexpected compilation mode")


class _NonBinaryFailingStmt:
    def compile(self, dialect=None, compile_kwargs=None):  # noqa: ANN001, ANN201
        raise RuntimeError("boom")


@pytest.fixture
def sqlite_bulk_manager() -> bulk_crud:
    return bulk_crud(engine=create_engine("sqlite:///:memory:"))


def test_detect_sqlserver_driver_sets_specific_db_info(mock_sqlserver_engine) -> None:
    mock_sqlserver_engine.url.drivername = "mssql+pymssql"

    manager = bulk_crud(engine=mock_sqlserver_engine)

    assert manager.db_info == "MSSQL (pymssql)"


def test_generar_nombre_sql_dinamico_contains_db_table_operation_and_timestamp() -> None:
    manager = bulk_crud(engine=create_engine("sqlite:///mydb.db"))

    sql_path = cast(Any, manager)._persistence.build_sql_filename("users", "INSERT")

    assert re.fullmatch(r"mydb\.db-users-insert_\d{8}_\d{6}\.sql", str(sql_path))


def test_validar_y_generar_path_sql_validates_input_type(sqlite_bulk_manager: bulk_crud) -> None:
    with pytest.raises(ValueError, match="path_sql es obligatorio"):
        _get_private_method(sqlite_bulk_manager, "_bulk_crud__validar_y_generar_path_sql")(None, "users", "insert")

    with pytest.raises(ValueError, match="instancia de Path"):
        _get_private_method(sqlite_bulk_manager, "_bulk_crud__validar_y_generar_path_sql")(
            "not-a-path", "users", "insert"
        )


def test_validar_y_generar_path_sql_joins_base_path_and_dynamic_name(
    tmp_path: Path, sqlite_bulk_manager: bulk_crud
) -> None:
    persistence = MagicMock()
    persistence.resolve_sql_output_path.return_value = tmp_path / "generated.sql"
    cast(Any, sqlite_bulk_manager)._persistence = persistence

    result = _get_private_method(sqlite_bulk_manager, "_bulk_crud__validar_y_generar_path_sql")(
        tmp_path, "users", "insert"
    )

    assert result == tmp_path / "generated.sql"
    persistence.resolve_sql_output_path.assert_called_once_with(tmp_path, "users", "insert")


def test_actualizar_df_replaces_nan_with_none(sqlite_bulk_manager: bulk_crud) -> None:
    df = pd.DataFrame({"col": [1, np.nan]})

    _get_private_method(sqlite_bulk_manager, "_bulk_crud__actualizar_df")(df)

    assert df.iloc[1, 0] is None


def test_format_param_value_handles_supported_types(sqlite_bulk_manager: bulk_crud) -> None:
    class _CustomObject:
        def __str__(self) -> str:
            return "custom'value"

    assert format_sql_param_value(None) == "NULL"
    assert format_sql_param_value(b"\x0a\xff") == "0x0AFF"
    assert format_sql_param_value(True) == "1"
    assert format_sql_param_value(False) == "0"
    assert format_sql_param_value(date(2024, 1, 2)) == "'2024-01-02'"
    assert format_sql_param_value(datetime(2024, 1, 2, 3, 4, 5)) == "'2024-01-02 03:04:05'"
    assert format_sql_param_value(time(10, 20, 30)) == "'10:20:30'"
    assert format_sql_param_value("O'Reilly") == "'O''Reilly'"
    assert format_sql_param_value(3.25) == "3.25"
    assert format_sql_param_value(_CustomObject()) == "'custom''value'"


def test_compilar_stmt_con_binarios_prefers_literal_binds(sqlite_bulk_manager: bulk_crud) -> None:
    compiled_sql = compile_stmt_with_binary_support(_LiteralStmt(), sqlite_bulk_manager.engine.dialect)
    assert compiled_sql == "SELECT 1;"


def test_compilar_stmt_con_binarios_falls_back_when_binary_literals_fail(sqlite_bulk_manager: bulk_crud) -> None:
    compiled_sql = compile_stmt_with_binary_support(_BinaryFallbackStmt(), sqlite_bulk_manager.engine.dialect)
    assert compiled_sql == "INSERT INTO t VALUES (0xAA, 'O''Reilly');"


def test_compilar_stmt_con_binarios_fallback_qmark(sqlite_bulk_manager: bulk_crud) -> None:
    compiled_sql = compile_stmt_with_binary_support(_QmarkBinaryFallbackStmt(), sqlite_bulk_manager.engine.dialect)
    assert compiled_sql == "INSERT INTO t VALUES (0xAA, 'O''Reilly');"


def test_compilar_stmt_con_binarios_fallback_named(sqlite_bulk_manager: bulk_crud) -> None:
    compiled_sql = compile_stmt_with_binary_support(_NamedBinaryFallbackStmt(), sqlite_bulk_manager.engine.dialect)
    assert compiled_sql == "INSERT INTO t VALUES (0xAA, 'O''Reilly');"


def test_compilar_stmt_con_binarios_reraises_non_binary_errors(sqlite_bulk_manager: bulk_crud) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        compile_stmt_with_binary_support(_NonBinaryFailingStmt(), sqlite_bulk_manager.engine.dialect)
