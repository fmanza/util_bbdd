"""DELETE de SQL Server con la PK del lote en un parámetro JSON (B-02 del performance-audit de bulk 2026-10-01).

Con ``IN`` de hasta 2000 marcadores, SQL Server compilaba un plan por forma de sentencia: 1K filas tardaban 0,16 s y
10K, 0,82 s. ``OPENJSON`` lleva el lote en un parámetro (10K: 0,04 s). La PK compuesta, que iba fila a fila, usa
``OPENJSON … WITH`` y un JOIN. Se mantiene la vía anterior para los tipos sin representación JSON exacta y las bases de
datos con nivel de compatibilidad < 130.
"""

from __future__ import annotations

import decimal
import json
import uuid

from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from sqlalchemy import Column, DateTime, Integer, MetaData, Numeric, String, Table, create_engine
from sqlalchemy.dialects import mssql

from util_bbdd.bulk._execution.batch import MSSQLOpenJsonDeleteStrategy
from util_bbdd.bulk._execution.delete_strategies import _openjson_payload

pytestmark = pytest.mark.unit

_META = MetaData()
_ITEMS = Table("items", _META, Column("id", Integer, primary_key=True), Column("v", String(20)), schema="dbo")
_CODES = Table("codes", _META, Column("code", String(30), primary_key=True))
_AMOUNTS = Table("amounts", _META, Column("amount", Numeric(12, 2), primary_key=True))
_PAIRS = Table("pairs", _META, Column("a", Integer, primary_key=True), Column("b", Integer, primary_key=True))
_DATES = Table("dates", _META, Column("d", DateTime, primary_key=True))


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    MSSQLOpenJsonDeleteStrategy._compatibility.clear()


def _connection(level: Any = 150) -> MagicMock:
    connection = MagicMock()
    connection.dialect = mssql.dialect()
    connection.engine = create_engine("mssql+pyodbc://u:p@h/db?driver=x")
    connection.execute.return_value.scalar.return_value = level
    return connection


def _executed_sql(connection: MagicMock) -> list[str]:
    return [str(call.args[0]) for call in connection.execute.call_args_list]


def test_single_pk_uses_one_json_parameter() -> None:
    connection = _connection()
    fallback = MagicMock()

    MSSQLOpenJsonDeleteStrategy(fallback).execute(
        connection=connection, table=_ITEMS, batch_df=pd.DataFrame({"id": np.arange(1, 4)}), pk_cols=["id"]
    )

    fallback.execute.assert_not_called()
    sql = _executed_sql(connection)[-1]
    assert sql == "DELETE FROM dbo.items WHERE id IN (SELECT CAST([value] AS INTEGER) FROM OPENJSON(:pk_json))"
    assert connection.execute.call_args.args[1] == {"pk_json": "[1, 2, 3]"}


def test_cast_uses_the_column_type() -> None:
    connection = _connection()
    MSSQLOpenJsonDeleteStrategy(MagicMock()).execute(
        connection=connection,
        table=_AMOUNTS,
        batch_df=pd.DataFrame({"amount": [decimal.Decimal("1.10")]}),
        pk_cols=["amount"],
    )
    assert "CAST([value] AS NUMERIC(12, 2))" in _executed_sql(connection)[-1]
    assert connection.execute.call_args.args[1] == {"pk_json": '["1.10"]'}


@pytest.mark.parametrize(
    ("table", "frame", "pk_cols"),
    [
        (_DATES, pd.DataFrame({"d": pd.to_datetime(["2026-01-01"])}), ["d"]),  # tipo sin JSON exacto
        (_ITEMS, pd.DataFrame({"id": [1.5]}), ["id"]),  # float
    ],
)
def test_unsupported_batches_use_fallback(table: Table, frame: pd.DataFrame, pk_cols: list[str]) -> None:
    connection = _connection()
    fallback = MagicMock()

    MSSQLOpenJsonDeleteStrategy(fallback).execute(connection=connection, table=table, batch_df=frame, pk_cols=pk_cols)

    fallback.execute.assert_called_once()
    assert not any("OPENJSON" in sql for sql in _executed_sql(connection))


@pytest.mark.parametrize("level", [120, None, "x"])
def test_low_or_unknown_compatibility_uses_fallback(level: Any) -> None:
    connection = _connection(level)
    fallback = MagicMock()

    MSSQLOpenJsonDeleteStrategy(fallback).execute(
        connection=connection, table=_ITEMS, batch_df=pd.DataFrame({"id": [1]}), pk_cols=["id"]
    )

    fallback.execute.assert_called_once()


def test_compatibility_query_error_uses_fallback() -> None:
    connection = _connection()
    connection.execute.side_effect = RuntimeError("sin permiso")
    fallback = MagicMock()

    MSSQLOpenJsonDeleteStrategy(fallback).execute(
        connection=connection, table=_ITEMS, batch_df=pd.DataFrame({"id": [1]}), pk_cols=["id"]
    )

    fallback.execute.assert_called_once()


def test_compatibility_is_read_once_per_engine() -> None:
    connection = _connection()
    strategy = MSSQLOpenJsonDeleteStrategy(MagicMock())
    for _ in range(3):
        strategy.execute(connection=connection, table=_ITEMS, batch_df=pd.DataFrame({"id": [1]}), pk_cols=["id"])

    assert sum("compatibility_level" in sql for sql in _executed_sql(connection)) == 1


def test_payload_values() -> None:
    key = uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert json.loads(_openjson_payload([[1, None]], [Integer()]) or "") == [1, None]
    assert json.loads(_openjson_payload([["a'b ñ"]], [NVARCHAR(10)]) or "") == ["a'b ñ"]
    assert json.loads(_openjson_payload([[decimal.Decimal("0E-10")]], [Numeric(20, 10)]) or "") == ["0.0000000000"]
    assert json.loads(_openjson_payload([[key]], [Uuid()]) or "") == [str(key)]
    assert json.loads(_openjson_payload([[1, 2], ["x", None]], [Integer(), String(5)]) or "") == [[1, "x"], [2, None]]
    assert _openjson_payload([[True]], [Integer()]) is None
    assert _openjson_payload([[decimal.Decimal("NaN")]], [Numeric(8, 2)]) is None
    assert _openjson_payload([[b"x"]], [String(5)]) is None
    assert _openjson_payload([[1], [b"x"]], [Integer(), String(5)]) is None  # un valor no válido en cualquier columna
    big = decimal.Decimal("1" * 36 + ".25")  # 38 dígitos: más que el contexto decimal por defecto (28)
    assert json.loads(_openjson_payload([[big]], [Numeric(38, 2)]) or "") == [format(big, "f")]


def test_composite_pk_joins_openjson_with_typed_columns() -> None:
    connection = _connection()
    fallback = MagicMock()

    MSSQLOpenJsonDeleteStrategy(fallback).execute(
        connection=connection, table=_PAIRS, batch_df=pd.DataFrame({"a": [1, 3], "b": [2, 4]}), pk_cols=["a", "b"]
    )

    fallback.execute.assert_not_called()
    assert _executed_sql(connection)[-1] == (
        "DELETE _bulk_del_t FROM pairs AS _bulk_del_t JOIN OPENJSON(:pk_json) "
        "WITH (a INTEGER '$[0]', b INTEGER '$[1]') AS _bulk_del_k "
        "ON _bulk_del_t.a = _bulk_del_k.a AND _bulk_del_t.b = _bulk_del_k.b"
    )
    assert connection.execute.call_args.args[1] == {"pk_json": "[[1, 2], [3, 4]]"}


def test_cast_drops_the_collation_of_reflected_text_columns() -> None:
    table = Table(
        "named", MetaData(), Column("k", String(30, collation="SQL_Latin1_General_CP1_CI_AS"), primary_key=True)
    )
    connection = _connection()

    MSSQLOpenJsonDeleteStrategy(MagicMock()).execute(
        connection=connection, table=table, batch_df=pd.DataFrame({"k": ["a"]}), pk_cols=["k"]
    )

    sql = _executed_sql(connection)[-1]
    assert "CAST([value] AS VARCHAR(30))" in sql
    assert "COLLATE" not in sql
    assert table.c.k.type.collation == "SQL_Latin1_General_CP1_CI_AS"  # el tipo de la tabla no se modifica


# ------------------------------------------------------------------ A1 (audit-code 2026-10-01): dominio de la PK
# OPENJSON convierte cada clave al tipo de la columna (CAST / WITH) y SQL Server trunca, redondea o sustituye caracteres
# sin error: con claves que no caben, se borraban otras filas. Esas claves deben ir por la vía anterior (IN), que compara
# el valor tal cual.

from sqlalchemy import NCHAR, NVARCHAR, SmallInteger, Uuid  # noqa: E402, F811
from sqlalchemy.dialects.mssql import TINYINT  # noqa: E402


@pytest.mark.parametrize(
    ("column_type", "value"),
    [
        (String(5), "abcdeXYZ"),  # más largo que la columna: CAST trunca
        (String(5), "α"),  # VARCHAR: fuera de ASCII, el code page puede sustituirlo ('α' → 'a')
        (NVARCHAR(2), "😀😀"),  # 4 unidades UTF-16 en NVARCHAR(2)
        (NCHAR(1), "ab"),
        (Numeric(8, 2), decimal.Decimal("1.105")),  # más decimales que la escala: CAST redondea
        (Numeric(4, 2), decimal.Decimal("100.5")),  # más dígitos enteros que precision - scale
        (Numeric(4, 2), 100),
        (Integer, 2**31),  # fuera de INT: CAST da error donde IN no borraba nada
        (SmallInteger, -(2**15) - 1),
        (TINYINT, 256),
        (TINYINT, -1),
        (Integer, "1"),  # tipo Python distinto del de la columna
        (String(5), 1),
        (Uuid, "12345678-1234-5678-1234-567812345678"),
        (Numeric(8, 2), True),
    ],
)
def test_values_outside_the_pk_domain_use_fallback(column_type: Any, value: Any) -> None:
    table = Table("domain", MetaData(), Column("k", column_type, primary_key=True))
    connection = _connection()
    fallback = MagicMock()

    MSSQLOpenJsonDeleteStrategy(fallback).execute(
        connection=connection, table=table, batch_df=pd.DataFrame({"k": [value]}, dtype=object), pk_cols=["k"]
    )

    fallback.execute.assert_called_once()
    assert not any("OPENJSON" in sql for sql in _executed_sql(connection))


@pytest.mark.parametrize(
    ("column_type", "value"),
    [
        (String(5), "abcde"),
        (String(5), "a'b%"),
        (String(None), "x" * 10_000),  # VARCHAR(MAX)
        (NVARCHAR(5), "αβγδε"),
        (Numeric(8, 2), decimal.Decimal("123456.78")),
        (Numeric(8, 2), decimal.Decimal("1.100")),  # ceros a la derecha: mismo valor con escala 2
        (Numeric(8, 2), 123),
        (Integer, 2**31 - 1),
        (TINYINT, 255),
        (Uuid, uuid.UUID(int=7)),
        (Integer, None),
    ],
)
def test_values_inside_the_pk_domain_use_openjson(column_type: Any, value: Any) -> None:
    table = Table("domain", MetaData(), Column("k", column_type, primary_key=True))
    connection = _connection()
    fallback = MagicMock()

    MSSQLOpenJsonDeleteStrategy(fallback).execute(
        connection=connection, table=table, batch_df=pd.DataFrame({"k": [value]}, dtype=object), pk_cols=["k"]
    )

    fallback.execute.assert_not_called()
    assert "OPENJSON" in _executed_sql(connection)[-1]


def test_composite_pk_falls_back_if_any_column_value_does_not_fit() -> None:
    table = Table("pair", MetaData(), Column("a", Integer, primary_key=True), Column("b", String(5), primary_key=True))
    connection = _connection()
    fallback = MagicMock()

    MSSQLOpenJsonDeleteStrategy(fallback).execute(
        connection=connection,
        table=table,
        batch_df=pd.DataFrame({"a": [1, 2], "b": ["ok", "abcdeXYZ"]}),
        pk_cols=["a", "b"],
    )

    fallback.execute.assert_called_once()
