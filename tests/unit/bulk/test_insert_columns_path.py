"""INSERT por columnas en las estrategias crudas (B-03 del performance-audit de bulk 2026-10-01).

COPY, ``execute_values`` y el ``executemany`` de PyMySQL envían tuplas al driver. Antes, ``BulkCrud`` construía un
``dict`` por fila y la estrategia lo deshacía; ahora las tuplas salen de las columnas (``zip(*columnas)``). Las filas que
recibe el driver deben ser exactamente las mismas, y la vía por columnas no debe construir ningún ``dict`` por fila
(``SqlColumns[i]`` lo haría y anularía la mejora: riesgo R-2 del AUDIT_PLAN).
"""

from __future__ import annotations

import datetime
import decimal

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, LargeBinary, MetaData, String, Table, create_engine, insert, text

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution.insert_strategies import (
    InsertStrategyResolver,
    MySQLDriverExecutemanyStrategy,
    PostgresCopyStrategy,
    PostgreSQLExecuteValuesStrategy,
)
from util_bbdd.bulk._support.sql_helpers import SqlColumns
from util_bbdd.bulk.normalize import dataframe_to_sql_columns, dataframe_to_sql_records
from util_bbdd.bulk.options import BatchOptions, ExecutionOptions

pytestmark = pytest.mark.unit

_TABLE = Table("t", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(20)))


def _mixed_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "i": np.arange(4),
            "f": [1.5, np.nan, 3.0, None],
            "s": [" a ", None, "c", "d "],
            "d": pd.to_datetime(["2026-01-01", None, "2026-01-03", "2026-01-04"]),
            "o": [decimal.Decimal("1.10"), None, datetime.date(2026, 1, 1), b"\xff"],
            "b": [True, False, True, False],
        }
    )


def _copy_connection() -> tuple[MagicMock, MagicMock]:
    connection = MagicMock()
    connection.in_transaction.return_value = True
    copy_obj = MagicMock()
    connection.connection.cursor.return_value.copy.return_value.__enter__.return_value = copy_obj
    connection.dialect.identifier_preparer.format_table.return_value = '"t"'
    connection.dialect.identifier_preparer.quote.side_effect = lambda c: f'"{c}"'
    return connection, copy_obj


def test_copy_rows_are_identical_for_records_and_columns() -> None:
    df = _mixed_frame()
    by_records, copy_records = _copy_connection()
    PostgresCopyStrategy().execute(connection=by_records, stmt=insert(_TABLE), records=dataframe_to_sql_records(df))
    by_columns, copy_columns = _copy_connection()
    PostgresCopyStrategy().execute_columns(
        connection=by_columns, stmt=insert(_TABLE), block=SqlColumns(*dataframe_to_sql_columns(df))
    )

    rows_records = [c.args[0] for c in copy_records.write_row.call_args_list]
    rows_columns = [c.args[0] for c in copy_columns.write_row.call_args_list]
    assert rows_records == rows_columns
    assert [[type(v) for v in r] for r in rows_records] == [[type(v) for v in r] for r in rows_columns]
    assert by_columns.connection.cursor.return_value.copy.call_args.args[0] == (
        'COPY "t" ("i", "f", "s", "d", "o", "b") FROM STDIN'
    )


@pytest.mark.parametrize(
    "strategy", [PostgresCopyStrategy, PostgreSQLExecuteValuesStrategy, MySQLDriverExecutemanyStrategy]
)
def test_raw_strategies_support_columns(strategy: type) -> None:
    assert strategy.supports_columns is True


def test_empty_block_does_nothing() -> None:
    connection, copy_obj = _copy_connection()
    PostgresCopyStrategy().execute_columns(connection=connection, stmt=insert(_TABLE), block=SqlColumns(["id"], [[]]))
    connection.connection.cursor.assert_not_called()


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'columns.db'}")
    Table(
        "items",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("v", String(20)),
        Column("blob", LargeBinary),
    ).create(eng)
    return eng


def _crud(engine: Engine, chunk_size: int = 3) -> BulkCrud:
    # MySQLDriverExecutemanyStrategy envía tuplas con exec_driver_sql y admite paramstyle qmark (SQLite).
    resolver = InsertStrategyResolver(default_strategy=MySQLDriverExecutemanyStrategy())
    return BulkCrud(
        engine, batch=BatchOptions(chunk_size=chunk_size), execution=ExecutionOptions(insert_resolver=resolver)
    )


def _rows(engine: Engine) -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text("SELECT id, v, blob FROM items ORDER BY id"))]


def _frame(ids: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"id": ids, "v": [f" v{i} " for i in ids], "blob": [b"q" if i % 2 else None for i in ids]})


def test_from_df_uses_columns_without_building_dicts(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_dicts(self: SqlColumns, index: Any) -> Any:
        raise AssertionError("la vía por columnas no debe construir un dict por fila")

    monkeypatch.setattr(SqlColumns, "__getitem__", _no_dicts)
    _crud(engine).bulk_insert_from_df(_frame(list(range(1, 8))), "items", False)

    assert _rows(engine) == [(i, f"v{i}", b"q" if i % 2 else None) for i in range(1, 8)]


def test_from_chunks_splits_large_chunks_into_blocks(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    sizes: list[int] = []
    original = MySQLDriverExecutemanyStrategy.execute_columns

    def _spy(self: Any, *, connection: Any, stmt: Any, block: SqlColumns) -> None:
        sizes.append(len(block))
        original(self, connection=connection, stmt=stmt, block=block)

    monkeypatch.setattr(MySQLDriverExecutemanyStrategy, "execute_columns", _spy)
    total = _crud(engine).bulk_insert_from_chunks([_frame(list(range(1, 8))), _frame([8, 9])], "items")

    assert total == 9
    assert sizes == [3, 3, 1, 2]
    assert [r[0] for r in _rows(engine)] == list(range(1, 10))


def test_columns_and_records_paths_store_the_same(tmp_path: Path) -> None:
    results = []
    for name, resolver in (
        ("columns", InsertStrategyResolver(default_strategy=MySQLDriverExecutemanyStrategy())),
        ("records", None),
    ):
        eng = create_engine(f"sqlite:///{tmp_path / f'{name}.db'}")
        Table(
            "items",
            MetaData(),
            Column("id", Integer, primary_key=True),
            Column("v", String(20)),
            Column("blob", LargeBinary),
        ).create(eng)
        BulkCrud(
            eng, batch=BatchOptions(chunk_size=2), execution=ExecutionOptions(insert_resolver=resolver)
        ).bulk_insert_from_df(_frame(list(range(1, 6))), "items", False)
        results.append(_rows(eng))

    assert results[0] == results[1]
