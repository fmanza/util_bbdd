"""Unit tests for helper behavior in bulk_crud."""

from __future__ import annotations

import re

from collections.abc import Callable
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from util_bbdd.bulk._support.sql_helpers import compile_stmt_with_binary_support, format_sql_param_value
from util_bbdd.bulk.crud import BulkCrud


def _get_private_method(manager: BulkCrud, name: str) -> Callable[..., Any]:
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


class _PercentSValueContainsPlaceholderCompiled:
    def __init__(self) -> None:
        # BLK-05: el valor del primer parámetro contiene literalmente "%s".
        self.params = {"first": "100%s off", "second": 42}

    def __str__(self) -> str:
        return "INSERT INTO t VALUES (%s, %s)"


class _PercentSValueContainsPlaceholderStmt:
    def compile(self, dialect=None, compile_kwargs=None):  # noqa: ANN001, ANN201
        if compile_kwargs and compile_kwargs.get("literal_binds"):
            raise RuntimeError("binary literal rendering is not supported")
        return _PercentSValueContainsPlaceholderCompiled()


class _QmarkValueContainsPlaceholderCompiled:
    def __init__(self) -> None:
        # BLK-05: el valor del primer parámetro contiene literalmente "?".
        self.params = {"first": "what?", "second": "next"}
        self.positiontup = ["first", "second"]

    def __str__(self) -> str:
        return "INSERT INTO t VALUES (?, ?)"


class _QmarkValueContainsPlaceholderStmt:
    def compile(self, dialect=None, compile_kwargs=None):  # noqa: ANN001, ANN201
        if compile_kwargs and compile_kwargs.get("literal_binds"):
            raise RuntimeError("binary literal rendering is not supported")
        return _QmarkValueContainsPlaceholderCompiled()


class _NamedValueContainsPlaceholderCompiled:
    def __init__(self) -> None:
        # BLK-05: el valor de "a" contiene literalmente ":b", el nombre del
        # siguiente parámetro nombrado.
        self.params = {"a": "see :b here", "b": 99}

    def __str__(self) -> str:
        return "INSERT INTO t VALUES (:a, :b)"


class _NamedValueContainsPlaceholderStmt:
    def compile(self, dialect=None, compile_kwargs=None):  # noqa: ANN001, ANN201
        if compile_kwargs and compile_kwargs.get("literal_binds"):
            raise RuntimeError("binary literal rendering is not supported")
        return _NamedValueContainsPlaceholderCompiled()


@pytest.fixture
def sqlite_bulk_manager() -> BulkCrud:
    return BulkCrud(engine=create_engine("sqlite:///:memory:"))


def test_detect_sqlserver_driver_sets_specific_db_info(mock_sqlserver_engine) -> None:
    mock_sqlserver_engine.url.drivername = "mssql+pymssql"

    manager = BulkCrud(engine=mock_sqlserver_engine)

    assert manager.db_info == "MSSQL (pymssql)"


def test_generar_nombre_sql_dinamico_contains_db_table_operation_and_timestamp() -> None:
    manager = BulkCrud(engine=create_engine("sqlite:///mydb.db"))

    sql_path = cast(Any, manager)._persistence.build_sql_filename("users", "INSERT")

    assert re.fullmatch(r"mydb\.db-users-insert_\d{8}_\d{6}\.sql", str(sql_path))


def test_validar_y_generar_path_sql_validates_input_type(sqlite_bulk_manager: BulkCrud) -> None:
    with pytest.raises(ValueError, match="path_sql es obligatorio"):
        _get_private_method(sqlite_bulk_manager, "_BulkCrud__validar_y_generar_path_sql")(None, "users", "insert")

    with pytest.raises(ValueError, match="instancia de Path"):
        _get_private_method(sqlite_bulk_manager, "_BulkCrud__validar_y_generar_path_sql")(
            "not-a-path", "users", "insert"
        )


def test_validar_y_generar_path_sql_joins_base_path_and_dynamic_name(
    tmp_path: Path, sqlite_bulk_manager: BulkCrud
) -> None:
    persistence = MagicMock()
    persistence.resolve_sql_output_path.return_value = tmp_path / "generated.sql"
    cast(Any, sqlite_bulk_manager)._persistence = persistence

    result = _get_private_method(sqlite_bulk_manager, "_BulkCrud__validar_y_generar_path_sql")(
        tmp_path, "users", "insert"
    )

    assert result == tmp_path / "generated.sql"
    persistence.resolve_sql_output_path.assert_called_once_with(tmp_path, "users", "insert")


def test_actualizar_df_normalizes_columns_nan_unchanged(sqlite_bulk_manager: BulkCrud) -> None:
    # __actualizar_df sólo normaliza casing; NaN→None ocurre en normalize_sql_literal.
    df = pd.DataFrame({"Col": [1, np.nan]})
    tabla = Table("t", MetaData(), Column("col", Integer))

    _get_private_method(sqlite_bulk_manager, "_BulkCrud__actualizar_df")(df, tabla)

    assert "col" in df.columns  # SQLite → lowercase
    assert pd.isna(df.iloc[1, 0])  # NaN no se convierte aquí


@pytest.mark.parametrize("dialect_name", ["mysql", "mariadb"])
def test_actualizar_df_mysql_mariadb_preserves_column_case(dialect_name: str) -> None:
    """MySQL/MariaDB: columnas no se normalizan (SQLAlchemy no las renormaliza en
    reflexión y el matching de columnas en MySQL/MariaDB es case-insensitive, pero
    Column.name reflejado preserva el case declarado). Forzar mayúsculas aquí
    rompería el match contra tablas con columnas en minúsculas (lo habitual)."""
    engine = MagicMock()
    engine.dialect.name = dialect_name
    manager = BulkCrud(engine=engine)
    df = pd.DataFrame({"UserId": [1], "user_name": ["a"], "MixedCase": [2]})
    tabla = Table("t", MetaData(), Column("UserId", Integer), Column("user_name", String), Column("MixedCase", Integer))

    _get_private_method(manager, "_BulkCrud__actualizar_df")(df, tabla)

    assert list(df.columns) == ["UserId", "user_name", "MixedCase"]


@pytest.mark.parametrize(
    ("dialect_name", "table_cols", "expected"),
    [
        # PD-01: SQL Server pasaba las columnas a MAYÚSCULAS y no casaban con una tabla en minúsculas o mixta.
        ("mssql", ["customer_id", "CustomerName"], ["customer_id", "CustomerName"]),
        # Mismo caso en PostgreSQL con columnas mixtas citadas (se pasaban a minúsculas).
        ("postgresql", ["customer_id", "CustomerName"], ["customer_id", "CustomerName"]),
        # Sin cambios cuando ya coinciden tras normalizar.
        ("mssql", ["CUSTOMER_ID", "CUSTOMERNAME"], ["CUSTOMER_ID", "CUSTOMERNAME"]),
        # Ambigua (dos columnas que solo difieren en mayúsculas): se deja como la normalización.
        ("mssql", ["customer_id", "Customer_Id", "customername"], ["CUSTOMER_ID", "customername"]),
    ],
)
def test_actualizar_df_aligns_columns_with_reflected_table(
    dialect_name: str, table_cols: list[str], expected: list[str]
) -> None:
    engine = MagicMock()
    engine.dialect.name = dialect_name
    manager = BulkCrud(engine=engine)
    df = pd.DataFrame({"Customer_ID": [1], "customerName": ["a"]})
    tabla = Table("t", MetaData(), *(Column(c, String) for c in table_cols))

    _get_private_method(manager, "_BulkCrud__actualizar_df")(df, tabla)

    assert list(df.columns) == expected


@pytest.mark.parametrize("dialect_name", ["mysql", "mariadb"])
def test_reflect_table_mysql_mariadb_preserves_table_name_case(dialect_name: str) -> None:
    """Mismo criterio que arriba, para el nombre de tabla pasado a Table(...,
    autoload_with=...): no se fuerza a mayúsculas, se preserva tal cual llega."""
    engine = MagicMock()
    engine.dialect.name = dialect_name
    manager = BulkCrud(engine=engine)

    with patch("util_bbdd.bulk.crud.Table") as table_cls:
        manager.reflect_table("MyTable")

    assert table_cls.call_args.args[0] == "MyTable"


@pytest.mark.parametrize("dialect_name", ["mysql", "mariadb"])
def test_reflect_table_mysql_mariadb_preserves_case_with_schema(dialect_name: str) -> None:
    engine = MagicMock()
    engine.dialect.name = dialect_name
    manager = BulkCrud(engine=engine)

    with patch("util_bbdd.bulk.crud.Table") as table_cls:
        manager.reflect_table("MySchema.MyTable")

    assert table_cls.call_args.args[0] == "MyTable"
    assert table_cls.call_args.kwargs["schema"] == "MySchema"


def test_format_param_value_handles_supported_types(sqlite_bulk_manager: BulkCrud) -> None:
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


def test_compilar_stmt_con_binarios_prefers_literal_binds(sqlite_bulk_manager: BulkCrud) -> None:
    compiled_sql = compile_stmt_with_binary_support(_LiteralStmt(), sqlite_bulk_manager.engine.dialect)
    assert compiled_sql == "SELECT 1;"


def test_compilar_stmt_con_binarios_falls_back_when_binary_literals_fail(sqlite_bulk_manager: BulkCrud) -> None:
    compiled_sql = compile_stmt_with_binary_support(_BinaryFallbackStmt(), sqlite_bulk_manager.engine.dialect)
    assert compiled_sql == "INSERT INTO t VALUES (0xAA, 'O''Reilly');"


def test_compilar_stmt_con_binarios_fallback_qmark(sqlite_bulk_manager: BulkCrud) -> None:
    compiled_sql = compile_stmt_with_binary_support(_QmarkBinaryFallbackStmt(), sqlite_bulk_manager.engine.dialect)
    assert compiled_sql == "INSERT INTO t VALUES (0xAA, 'O''Reilly');"


def test_compilar_stmt_con_binarios_fallback_named(sqlite_bulk_manager: BulkCrud) -> None:
    compiled_sql = compile_stmt_with_binary_support(_NamedBinaryFallbackStmt(), sqlite_bulk_manager.engine.dialect)
    assert compiled_sql == "INSERT INTO t VALUES (0xAA, 'O''Reilly');"


def test_compilar_stmt_con_binarios_percent_s_value_does_not_corrupt_next_placeholder(
    sqlite_bulk_manager: BulkCrud,
) -> None:
    """BLK-05 (AUDIT_CODE 2026-09-22): un valor que contiene literalmente "%s" no debe
    ser reescaneado como placeholder del siguiente parámetro."""
    compiled_sql = compile_stmt_with_binary_support(
        _PercentSValueContainsPlaceholderStmt(), sqlite_bulk_manager.engine.dialect
    )
    assert compiled_sql == "INSERT INTO t VALUES ('100%s off', 42);"


def test_compilar_stmt_con_binarios_qmark_value_does_not_corrupt_next_placeholder(
    sqlite_bulk_manager: BulkCrud,
) -> None:
    """BLK-05 (AUDIT_CODE 2026-09-22): un valor que contiene literalmente "?" no debe
    ser reescaneado como placeholder del siguiente parámetro."""
    compiled_sql = compile_stmt_with_binary_support(
        _QmarkValueContainsPlaceholderStmt(), sqlite_bulk_manager.engine.dialect
    )
    assert compiled_sql == "INSERT INTO t VALUES ('what?', 'next');"


def test_compilar_stmt_con_binarios_named_value_does_not_corrupt_later_placeholder(
    sqlite_bulk_manager: BulkCrud,
) -> None:
    """BLK-05 (AUDIT_CODE 2026-09-22): un valor que contiene literalmente ":otro_param"
    no debe ser reescaneado como placeholder de ese otro parámetro."""
    compiled_sql = compile_stmt_with_binary_support(
        _NamedValueContainsPlaceholderStmt(), sqlite_bulk_manager.engine.dialect
    )
    assert compiled_sql == "INSERT INTO t VALUES ('see :b here', 99);"


def test_compilar_stmt_con_binarios_reraises_non_binary_errors(sqlite_bulk_manager: BulkCrud) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        compile_stmt_with_binary_support(_NonBinaryFailingStmt(), sqlite_bulk_manager.engine.dialect)


# ---------------------------------------------------------------------------
# Propuesta B — bulk_session
# ---------------------------------------------------------------------------


def test_bulk_session_reuses_single_connection() -> None:
    """engine.begin() se abre 1 vez para 3 llamadas a bulk_insert_from_df dentro de bulk_session."""
    from unittest.mock import patch

    from sqlalchemy import Column, Integer, MetaData, Table

    engine = create_engine("sqlite:///:memory:")
    Table("widgets", MetaData(), Column("id", Integer, primary_key=True)).create(bind=engine)

    import pandas as pd

    crud = BulkCrud(engine=engine)

    open_count: list[int] = [0]
    original_begin = engine.begin

    def counting_begin():
        open_count[0] += 1
        return original_begin()

    with patch.object(engine, "begin", side_effect=counting_begin):
        with crud.bulk_session():
            for _ in range(3):
                crud.bulk_insert_from_df(pd.DataFrame({"id": []}), "widgets", generar_sql=False)

    assert open_count[0] == 1, f"Se esperaba 1 transacción, se abrieron {open_count[0]}"


def test_bulk_session_resets_active_connection_on_exit() -> None:
    """_active_connection vuelve a None al salir del bloque bulk_session."""
    engine = create_engine("sqlite:///:memory:")
    crud = BulkCrud(engine=engine)

    with crud.bulk_session():
        assert crud._session.active

    assert not crud._session.active


def test_bulk_session_atomic_false_does_not_inject_connection() -> None:
    """Con atomic=False, _active_connection nunca se inyecta (comportamiento legacy)."""
    engine = create_engine("sqlite:///:memory:")
    crud = BulkCrud(engine=engine)

    with crud.bulk_session(atomic=False):
        assert not crud._session.active
