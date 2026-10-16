"""``BulkCrud(prefetch_blocks=True)`` (S-4 de bulk, sesión 2026-10-01m).

Prepara el lote siguiente en un hilo con una cola de 2 mientras se envía el actual. Debe dejar la BD exactamente igual
que sin prefetch, conservar la posición de las notas de error y no dejar hilos vivos si el envío o la preparación fallan.
"""

from __future__ import annotations

import threading

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.exc import IntegrityError

import util_bbdd.bulk.crud as crud_module

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution.insert_strategies import InsertStrategyResolver, MySQLDriverExecutemanyStrategy
from util_bbdd.bulk.options import BatchOptions, ExecutionOptions

pytestmark = pytest.mark.unit


def _engine(tmp_path: Path, name: str) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / name}")
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(10))).create(eng)
    return eng


def _frame(ids: list[int], v: str = "v") -> pd.DataFrame:
    return pd.DataFrame({"id": ids, "v": [f" {v}{i} " for i in ids]})


def _rows(engine: Engine) -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text("SELECT id, v FROM items ORDER BY id"))]


def _prefetch_threads() -> int:
    return sum(1 for t in threading.enumerate() if t.name == "bulk-prefetch" and t.is_alive())


def _scenario(engine: Engine, *, prefetch: bool, columns: bool) -> list[tuple[Any, ...]]:
    resolver = InsertStrategyResolver(default_strategy=MySQLDriverExecutemanyStrategy()) if columns else None
    crud = BulkCrud(
        engine,
        batch=BatchOptions(chunk_size=3, prefetch_blocks=prefetch),
        execution=ExecutionOptions(insert_resolver=resolver),
    )
    crud.bulk_insert_from_df(_frame(list(range(1, 11))), "items", False)
    crud.bulk_update_from_df(_frame([2, 4, 6, 8, 10], "u"), "items", False)
    crud.bulk_insert_from_chunks(iter([_frame([11, 12]), _frame([]), _frame(list(range(13, 21)))]), "items")
    crud.bulk_delete_from_df(_frame([1, 3])[["id"]], "items", False)
    return _rows(engine)


@pytest.mark.parametrize("columns", [False, True], ids=["registros", "columnas"])
def test_same_result_with_and_without_prefetch(tmp_path: Path, columns: bool) -> None:
    plain = _scenario(_engine(tmp_path, "plain.db"), prefetch=False, columns=columns)
    prefetched = _scenario(_engine(tmp_path, "prefetch.db"), prefetch=True, columns=columns)

    assert prefetched == plain
    assert len(plain) == 18
    assert _prefetch_threads() == 0


def test_blocks_are_prepared_in_the_prefetch_thread(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    threads: set[str] = set()
    original = crud_module.dataframe_to_sql_records

    def _spy(df: pd.DataFrame, **kwargs: Any) -> Any:
        threads.add(threading.current_thread().name)
        return original(df, **kwargs)

    monkeypatch.setattr(crud_module, "dataframe_to_sql_records", _spy)
    BulkCrud(_engine(tmp_path, "t.db"), batch=BatchOptions(chunk_size=2, prefetch_blocks=True)).bulk_insert_from_df(
        _frame(list(range(1, 8))), "items", False
    )

    assert threads == {"bulk-prefetch"}


def test_failed_send_keeps_note_and_stops_the_thread(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "fail.db")
    crud = BulkCrud(engine, batch=BatchOptions(chunk_size=3, prefetch_blocks=True))
    crud.bulk_insert_from_df(_frame([7]), "items", False)

    with pytest.raises(IntegrityError) as info:
        crud.bulk_insert_from_df(_frame(list(range(1, 31))), "items", False)

    assert "bulk INSERT en 'items': falló el lote 2 (filas 6–8 de la entrada, base 0)" in info.value.__notes__
    assert _prefetch_threads() == 0
    assert _rows(engine) == [(7, "v7")]


def test_failed_preparation_reaches_the_caller_with_its_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    original = crud_module.dataframe_to_sql_records

    def _fails_on_third(df: pd.DataFrame, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 3:
            raise KeyError("columna rara")
        return original(df, **kwargs)

    monkeypatch.setattr(crud_module, "dataframe_to_sql_records", _fails_on_third)
    engine = _engine(tmp_path, "prep.db")

    with pytest.raises(KeyError, match="columna rara"):
        BulkCrud(engine, batch=BatchOptions(chunk_size=2, prefetch_blocks=True)).bulk_insert_from_df(
            _frame(list(range(1, 11))), "items", False
        )

    assert _prefetch_threads() == 0
    assert _rows(engine) == []  # atómico: los lotes ya enviados se deshacen


def test_default_is_off(tmp_path: Path) -> None:
    assert BulkCrud(_engine(tmp_path, "d.db"))._prefetch_blocks is False
