"""PD-01 (performance-audit de dump 2026-09-25): columnas del DataFrame frente a columnas de la tabla con otro case.

``BulkCrud`` normaliza el case de las columnas del DataFrame por dialecto (minúsculas en SQLite/PostgreSQL/Oracle,
mayúsculas en SQL Server) y la validación comparaba con los nombres reflejados distinguiendo mayúsculas. Con una tabla
cuyas columnas no siguen ese case (``CustomerName`` en SQLite, ``customer_id`` en SQL Server) no casaba ninguna columna:
``No hay columnas válidas para INSERT``. SQLite reproduce el fallo sin servidor.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk import BulkCrud
from util_bbdd.dump import DumpConfig, DumpOrchestrator

pytestmark = pytest.mark.unit

_DDL = 'CREATE TABLE customers ("CustomerId" INTEGER PRIMARY KEY, "CustomerName" TEXT, "Country" TEXT)'


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    with eng.begin() as conn:
        conn.execute(text(_DDL))
    yield eng
    eng.dispose()


def _rows(engine: Engine) -> list[tuple[object, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text('SELECT * FROM customers ORDER BY "CustomerId"'))]


def _df() -> pd.DataFrame:
    return pd.DataFrame({"CustomerId": [1, 2], "CustomerName": ["a", "b"], "Country": ["ES", "FR"]})


def test_insert_update_delete_with_mixed_case_columns(engine: Engine) -> None:
    crud = BulkCrud(engine)

    crud.bulk_insert_from_df(_df(), "customers", generar_sql=False)
    assert _rows(engine) == [(1, "a", "ES"), (2, "b", "FR")]

    crud.bulk_update_from_df(pd.DataFrame({"CustomerId": [2], "CustomerName": ["B"]}), "customers", generar_sql=False)
    assert _rows(engine) == [(1, "a", "ES"), (2, "B", "FR")]

    crud.bulk_delete_from_df(pd.DataFrame({"CustomerId": [1]}), "customers", generar_sql=False)
    assert _rows(engine) == [(2, "B", "FR")]


def test_insert_from_chunks_with_mixed_case_columns(engine: Engine) -> None:
    df = _df()
    BulkCrud(engine).bulk_insert_from_chunks(iter([df.iloc[:1], df.iloc[1:]]), "customers")
    assert _rows(engine) == [(1, "a", "ES"), (2, "b", "FR")]


def test_caller_dataframe_is_not_renamed(engine: Engine) -> None:
    df = _df()
    BulkCrud(engine).bulk_insert_from_df(df, "customers", generar_sql=False)
    assert list(df.columns) == ["CustomerId", "CustomerName", "Country"]


def test_dump_to_mixed_case_target(tmp_path: Path, engine: Engine) -> None:
    src = create_engine(f"sqlite:///{tmp_path / 'src.sqlite'}")
    with src.begin() as conn:
        conn.execute(text("CREATE TABLE customers (customerid INTEGER PRIMARY KEY, customername TEXT, country TEXT)"))
        conn.execute(text("INSERT INTO customers VALUES (1, 'a', 'ES'), (2, 'b', 'FR')"))

    result = DumpOrchestrator(DumpConfig(source_engine=src, target_engine=engine, output_dir=tmp_path)).run()

    assert [r.status for r in result.table_results] == ["success"]
    assert _rows(engine) == [(1, "a", "ES"), (2, "b", "FR")]
    src.dispose()
