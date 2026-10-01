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
    payload = _openjson_payload([[1, "a'b ñ", None, decimal.Decimal("0E-10"), key]])
    assert json.loads(payload or "") == [1, "a'b ñ", None, "0.0000000000", str(key)]
    assert json.loads(_openjson_payload([[1, 2], ["x", None]]) or "") == [[1, "x"], [2, None]]
    assert _openjson_payload([[True]]) is None
    assert _openjson_payload([[decimal.Decimal("NaN")]]) is None
    assert _openjson_payload([[b"x"]]) is None
    assert _openjson_payload([[1], [b"x"]]) is None  # un valor no válido en cualquier columna


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
