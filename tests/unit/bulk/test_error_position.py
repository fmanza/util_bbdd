"""Posición del lote fallido en el error (B-15a del performance-audit de bulk 2026-10-01).

El error del driver no decía en qué lote de una carga grande había fallado. Ahora la excepción lleva una nota
(``add_note``) con la operación, la tabla, el número de lote y las filas de la entrada; el tipo y ``str(exc)`` no cambian.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.exc import IntegrityError

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution.executors import batch_failure_note

pytestmark = pytest.mark.unit

_BAD_ID = 7  # con chunk_size=3: lote 2, filas 6–8


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'position.db'}")
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(20))).create(eng)
    with eng.begin() as conn:
        for op in ("UPDATE", "DELETE"):
            conn.execute(
                text(
                    f"CREATE TRIGGER no_{op.lower()} BEFORE {op} ON items WHEN old.id = {_BAD_ID} "
                    "BEGIN SELECT RAISE(ABORT, 'fila protegida'); END"
                )
            )
    return eng


def _frame(ids: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"id": ids, "v": [f"v{i}" for i in ids]})


def _notes(exc: BaseException) -> list[str]:
    return list(getattr(exc, "__notes__", []))


def test_insert_note_points_to_failing_batch(engine: Engine) -> None:
    crud = BulkCrud(engine, chunk_size=3)
    crud.bulk_insert_from_df(_frame([_BAD_ID]), "items", False)

    with pytest.raises(IntegrityError) as info:
        crud.bulk_insert_from_df(_frame(list(range(1, 10))), "items", False)

    assert _notes(info.value) == ["bulk INSERT en 'items': falló el lote 2 (filas 6–8 de la entrada, base 0)"]


def test_update_note_points_to_failing_batch(engine: Engine) -> None:
    crud = BulkCrud(engine, chunk_size=3)
    crud.bulk_insert_from_df(_frame(list(range(1, 10))), "items", False)

    with pytest.raises(Exception, match="fila protegida") as info:
        crud.bulk_update_from_df(_frame(list(range(1, 10))).assign(v="x"), "items", False)

    assert _notes(info.value) == ["bulk UPDATE en 'items': falló el lote 2 (filas 6–8 de la entrada, base 0)"]


def test_delete_note_points_to_failing_batch(engine: Engine) -> None:
    crud = BulkCrud(engine, chunk_size=3)
    crud.bulk_insert_from_df(_frame(list(range(1, 10))), "items", False)

    with pytest.raises(Exception, match="fila protegida") as info:
        crud.bulk_delete_from_df(_frame(list(range(1, 10)))[["id"]], "items", False)

    assert _notes(info.value) == ["bulk DELETE en 'items': falló el lote 2 (filas 6–8 de la entrada, base 0)"]


def test_streaming_note_counts_rows_of_previous_chunks(engine: Engine) -> None:
    crud = BulkCrud(engine, chunk_size=100)
    crud.bulk_insert_from_df(_frame([_BAD_ID]), "items", False)
    chunks = [_frame([1, 2]), _frame([]), _frame([3, 4, 5]), _frame([6, _BAD_ID, 8])]

    with pytest.raises(IntegrityError) as info:
        crud.bulk_insert_from_chunks(chunks, "items")

    assert _notes(info.value) == ["bulk INSERT en 'items': falló el lote 3 (filas 5–7 de la entrada, base 0)"]


def test_note_keeps_type_and_message() -> None:
    original = ValueError("mensaje original")
    with pytest.raises(ValueError) as info, batch_failure_note("INSERT", "t", 0, 0, 1):
        raise original

    assert info.value is original
    assert str(info.value) == "mensaje original"


def test_successful_batch_adds_no_note() -> None:
    with batch_failure_note("INSERT", "t", 0, 0, 1):
        pass
