"""Deuda A3 y A4 del audit-code de bulk 2026-10-01 (sesión 2026-10-01i).

- A3: ``bulk_insert_from_chunks``, ``bulk_update_from_chunks`` y ``bulk_delete_from_chunks`` abren su propia sesión.
  Dentro de una ``bulk_session`` ya abierta abrían una segunda conexión (en SQLite, ``database is locked``) y al salir
  dejaban la sesión externa sin conexión. Ahora fallan con ``RuntimeError`` antes de tocar nada.
- A4: si falla el COMMIT periódico de ``commit_every_n_chunks``, la nota del error no debe decir que falló el lote, que
  se había ejecutado bien.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.exc import OperationalError

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._support.persistence import BulkPersistenceManager

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'session.db'}")
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(10))).create(eng)
    return eng


def _frame(ids: list[int], v: str = "v") -> pd.DataFrame:
    return pd.DataFrame({"id": ids, "v": [v] * len(ids)})


def _rows(engine: Engine) -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text("SELECT id, v FROM items ORDER BY id"))]


_STREAMS: list[Any] = [
    pytest.param(lambda crud: crud.bulk_insert_from_chunks(iter([_frame([9])]), "items"), id="insert"),
    pytest.param(lambda crud: crud.bulk_update_from_chunks(iter([_frame([1], "u")]), "items"), id="update"),
    pytest.param(lambda crud: crud.bulk_delete_from_chunks(iter([_frame([2])[["id"]]]), "items"), id="delete"),
]


@pytest.mark.parametrize("stream", _STREAMS)
def test_from_chunks_inside_an_open_session_raises_and_keeps_the_session(
    engine: Engine, stream: Callable[[BulkCrud], Any]
) -> None:
    crud = BulkCrud(engine)
    crud.bulk_insert_from_df(_frame([1, 2, 3]), "items", False)

    with pytest.raises(RuntimeError, match="bulk_session"):
        with crud.bulk_session():
            crud.bulk_update_from_df(_frame([3], "x"), "items", False)
            try:
                stream(crud)
            finally:
                # La sesión externa sigue con su conexión: la operación siguiente va en la misma transacción.
                assert crud._session.active
            raise AssertionError("no debería llegar aquí")

    assert _rows(engine) == [(1, "v"), (2, "v"), (3, "v")]  # rollback de la sesión externa completa


def test_from_chunks_outside_a_session_still_works(engine: Engine) -> None:
    crud = BulkCrud(engine)
    assert crud.bulk_insert_from_chunks(iter([_frame([1, 2])]), "items") == 2
    assert crud.bulk_update_from_chunks(iter([_frame([1], "u")]), "items") == 1
    assert crud.bulk_delete_from_chunks(iter([_frame([2])[["id"]]]), "items") == 1
    assert _rows(engine) == [(1, "u")]


def test_failed_periodic_commit_is_not_blamed_on_the_batch(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    original = BulkPersistenceManager.commit
    calls = {"n": 0}

    def _commit(self: BulkPersistenceManager, connection: Any) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OperationalError("COMMIT", {}, Exception("conexión perdida en el commit"))
        original(self, connection)

    monkeypatch.setattr(BulkPersistenceManager, "commit", _commit)
    crud = BulkCrud(engine, chunk_size=2, commit_every_n_chunks=1)

    with pytest.raises(OperationalError) as info:
        crud.bulk_insert_from_df(_frame(list(range(1, 7))), "items", False)

    notes = info.value.__notes__
    assert any("falló el COMMIT periódico" in note for note in notes)
    batch_notes = [note for note in notes if note.startswith("bulk INSERT")]
    assert batch_notes == [
        "bulk INSERT en 'items': el lote 1 (filas 2–3 de la entrada, base 0) se ejecutó; falló el COMMIT periódico posterior"
    ]
