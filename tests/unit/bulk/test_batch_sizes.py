"""Lote por motor y operación cuando no se fija ``chunk_size`` (B-04, performance-audit de bulk 2026-10-01).

Barrido de 1M filas (mediana de 3): PostgreSQL INSERT/DELETE y SQL Server DELETE ganan un 10–20 % con lotes de 20 000;
el UPDATE de PostgreSQL por tabla temporal pierde un 31 %. Con ``commit_every_n_chunks`` o un ``chunk_size`` explícito
los lotes no dependen del motor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, create_engine, text

import util_bbdd.bulk.crud as crud_module

from util_bbdd.bulk import BulkCrud, ParallelBulkLoader
from util_bbdd.bulk._execution.insert_strategies import DefaultInsertStrategy
from util_bbdd.bulk._support.batch_sizes import DEFAULT_CHUNK_SIZE, resolve_batch_sizes

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("dialect", "expected"),
    [
        ("postgresql", {"insert": 20_000, "update": 5000, "delete": 20_000}),
        ("mssql", {"insert": 5000, "update": 5000, "delete": 20_000}),
        ("mysql", {"insert": 5000, "update": 5000, "delete": 5000}),
        ("mariadb", {"insert": 5000, "update": 5000, "delete": 5000}),
        ("oracle", {"insert": 5000, "update": 5000, "delete": 5000}),
        ("sqlite", {"insert": 5000, "update": 5000, "delete": 5000}),
    ],
)
def test_default_batch_sizes_by_engine(dialect: str, expected: dict[str, int]) -> None:
    assert resolve_batch_sizes(dialect, None, None) == expected


def test_cadence_keeps_uniform_default() -> None:
    assert resolve_batch_sizes("postgresql", None, 20) == {"insert": 5000, "update": 5000, "delete": 5000}


def test_explicit_chunk_size_applies_to_every_operation() -> None:
    assert resolve_batch_sizes("postgresql", 7000, None) == {"insert": 7000, "update": 7000, "delete": 7000}


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'sizes.db'}")
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(20))).create(eng)
    return eng


def test_bulkcrud_defaults(engine: Engine) -> None:
    crud = BulkCrud(engine)
    assert crud.chunk_size == DEFAULT_CHUNK_SIZE
    assert crud.batch_sizes == {"insert": 5000, "update": 5000, "delete": 5000}
    assert BulkCrud(engine, chunk_size=123).batch_sizes == {"insert": 123, "update": 123, "delete": 123}


def test_each_operation_uses_its_batch_size(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crud_module, "resolve_batch_sizes", lambda *a: {"insert": 4, "update": 2, "delete": 3})
    inserted: list[int] = []
    original = DefaultInsertStrategy.execute

    def _spy_insert(self: Any, *, connection: Any, stmt: Any, records: Any) -> None:
        inserted.append(len(records))
        original(self, connection=connection, stmt=stmt, records=records)

    monkeypatch.setattr(DefaultInsertStrategy, "execute", _spy_insert)
    crud = BulkCrud(engine, update_via_staging=False)
    df = pd.DataFrame({"id": range(1, 11), "v": ["a"] * 10})

    crud.bulk_insert_from_df(df, "items", False)
    updated = len(inserted)
    crud.bulk_update_from_df(df.assign(v="b"), "items", False)

    assert inserted[:updated] == [4, 4, 2]  # INSERT en lotes de 4
    assert inserted[updated:] == [2] * 5  # UPDATE en lotes de 2 (misma estrategia por defecto en SQLite)

    with pytest.raises(Exception) as info:  # la nota de error usa el lote del DELETE (3): lote 1 = filas 3–5
        with engine.begin() as conn:
            conn.execute(
                text("CREATE TRIGGER t BEFORE DELETE ON items WHEN old.id = 5 BEGIN SELECT RAISE(ABORT, 'x'); END")
            )
        crud.bulk_delete_from_df(df[["id"]], "items", False)
    assert "falló el lote 1 (filas 3–5 de la entrada, base 0)" in info.value.__notes__[0]


def test_parallel_loader_passes_none_to_each_bulkcrud(engine: Engine) -> None:
    loader = ParallelBulkLoader(engine, max_workers=1)
    assert loader._chunk_size is None
    result = loader.load("items", [lambda: iter([pd.DataFrame({"id": [1, 2], "v": ["a", "b"]})])])
    assert result.total_rows == 2
