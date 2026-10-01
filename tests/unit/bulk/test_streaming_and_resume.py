"""Fase 2 del performance-audit de bulk 2026-10-01: streaming (B-08), checkpoints y reanudación (B-11) y UPDATE/DELETE
paralelos (B-05).

- ``bulk_update_from_chunks`` / ``bulk_delete_from_chunks``: mismo estado final que ``*_from_df``, una sesión, iterable
  perezoso y cerrado al terminar; la cadencia del DELETE sigue de un chunk al siguiente.
- ``last_operation_rows_committed``: prefijo confirmado de la última operación, sin las filas de operaciones anteriores
  que un commit de esta confirmó (R-3 del AUDIT_PLAN).
- ``ParallelBulkLoader``: ``commit_every_n_chunks`` + ``max_retries`` ya no son incompatibles: el reintento reanuda.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError

from util_bbdd.bulk import BulkCrud, ParallelBulkLoader
from util_bbdd.bulk._execution.parallel_loader import _skip_rows
from util_bbdd.bulk._execution.session import RowLedger

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'stream.db'}")
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(20))).create(eng)
    return eng


def _frame(ids: list[int], v: str = "v") -> pd.DataFrame:
    return pd.DataFrame({"id": ids, "v": [f"{v}{i}" for i in ids]})


def _rows(engine: Engine) -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text("SELECT id, v FROM items ORDER BY id"))]


def _protect(engine: Engine, op: str, row_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE TRIGGER protect_{op.lower()} BEFORE {op} ON items WHEN old.id = {row_id} "
                "BEGIN SELECT RAISE(ABORT, 'fila protegida'); END"
            )
        )


class _Chunks:
    """Iterable de chunks que registra cuántos se han leído y si se cerró."""

    def __init__(self, frames: list[pd.DataFrame]) -> None:
        self._frames = frames
        self.read = 0
        self.closed = False

    def __iter__(self) -> Iterator[pd.DataFrame]:
        for frame in self._frames:
            self.read += 1
            yield frame

    def close(self) -> None:
        self.closed = True


# ------------------------------------------------------------------------------------------------- RowLedger (R-3)


def test_ledger_counts_operation_apart_from_session() -> None:
    ledger = RowLedger()
    ledger.start_operation()
    ledger.add(3)  # operación 1, sin confirmar
    ledger.start_operation()
    ledger.add(2)  # operación 2
    ledger.confirm()  # el commit confirma las 5 filas de la transacción

    assert (ledger.committed, ledger.op_committed) == (5, 2)
    ledger.add(4)
    ledger.discard()
    assert (ledger.committed, ledger.op_committed, ledger.op_pending) == (5, 2, 0)


# ------------------------------------------------------------------------------------- last_operation_rows_committed


def test_last_operation_rows_committed_is_the_confirmed_prefix(engine: Engine) -> None:
    _protect(engine, "UPDATE", 8)
    crud = BulkCrud(engine, chunk_size=2, commit_every_n_chunks=2)
    crud.bulk_insert_from_df(_frame(list(range(1, 11))), "items", False)

    with pytest.raises(Exception, match="fila protegida"):
        crud.bulk_update_from_df(_frame(list(range(1, 11)), "x"), "items", False)

    # Lotes de 2 y commit cada 2 lotes: filas 0–3 confirmadas; el lote de la fila 8 (posición 7) falla.
    assert crud.last_operation_rows_committed == 4
    assert [r[1] for r in _rows(engine)][:5] == ["x1", "x2", "x3", "x4", "v5"]
    crud.bulk_update_from_df(_frame(list(range(1, 11)), "x").iloc[4:].query("id != 8"), "items", False)
    assert [r[1] for r in _rows(engine)] == [f"x{i}" if i != 8 else "v8" for i in range(1, 11)]


def test_last_operation_rows_committed_is_zero_when_atomic(engine: Engine) -> None:
    crud = BulkCrud(engine, chunk_size=2)
    crud.bulk_insert_from_df(_frame([5]), "items", False)
    with pytest.raises(IntegrityError):
        crud.bulk_insert_from_df(_frame(list(range(1, 9))), "items", False)
    assert crud.last_operation_rows_committed == 0
    assert _rows(engine) == [(5, "v5")]


def test_previous_operation_rows_are_not_attributed(engine: Engine) -> None:
    """R-3: el commit periódico del DELETE confirma también el INSERT pendiente; no cuenta como fila del DELETE."""
    crud = BulkCrud(engine, chunk_size=2, commit_every_n_chunks=3)
    with crud.bulk_session():
        crud.bulk_insert_from_df(_frame([1, 2, 3, 4]), "items", False)  # 2 lotes, sin commit todavía
        crud.bulk_delete_from_df(_frame([1, 2, 3, 4, 5, 6])[["id"]], "items", False)  # 3 lotes → commit

    assert crud.rows_committed == 10
    assert crud.last_operation_rows_committed == 6


# ------------------------------------------------------------------------------------------------- *_from_chunks


def test_update_from_chunks_matches_from_df(engine: Engine, tmp_path: Path) -> None:
    other = create_engine(f"sqlite:///{tmp_path / 'other.db'}")
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(20))).create(other)
    for eng in (engine, other):
        BulkCrud(eng).bulk_insert_from_df(_frame(list(range(1, 11))), "items", False)
    update = _frame([1, 3, 3, 99, 7, 10], "u")

    chunks = _Chunks([update.iloc[:2], update.iloc[2:2], update.iloc[2:5], update.iloc[5:]])
    total = BulkCrud(engine, chunk_size=2).bulk_update_from_chunks(chunks, "items")
    BulkCrud(other, chunk_size=2).bulk_update_from_df(update, "items", False)

    assert total == 6
    assert _rows(engine) == _rows(other)
    assert chunks.closed


def test_delete_from_chunks_deletes_and_closes(engine: Engine) -> None:
    BulkCrud(engine).bulk_insert_from_df(_frame(list(range(1, 11))), "items", False)
    chunks = _Chunks([_frame([1, 2])[["id"]], _frame([])[["id"]], _frame([5, 6, 7])[["id"]]])

    total = BulkCrud(engine, chunk_size=2).bulk_delete_from_chunks(chunks, "items")

    assert total == 5
    assert [r[0] for r in _rows(engine)] == [3, 4, 8, 9, 10]
    assert chunks.closed


def test_stream_is_one_transaction_and_closes_on_failure(engine: Engine) -> None:
    BulkCrud(engine).bulk_insert_from_df(_frame(list(range(1, 11))), "items", False)
    _protect(engine, "DELETE", 9)
    chunks = _Chunks([_frame([1, 2])[["id"]], _frame([8, 9])[["id"]], _frame([10])[["id"]]])

    with pytest.raises(Exception, match="fila protegida") as info:
        BulkCrud(engine, chunk_size=1).bulk_delete_from_chunks(chunks, "items")

    assert len(_rows(engine)) == 10  # atómico: el chunk 0 también se deshace
    assert chunks.read == 2  # perezoso: el chunk 2 no se llegó a leer
    assert chunks.closed
    assert (
        "bulk DELETE en 'items': falló el lote 1 del chunk 1 (filas 3–3 de la entrada, base 0)" in info.value.__notes__
    )


def test_delete_cadence_continues_across_chunks(engine: Engine) -> None:
    """Con un lote por chunk y commit cada 2 lotes, el contador no puede reiniciarse en cada chunk (nunca confirmaría)."""
    BulkCrud(engine).bulk_insert_from_df(_frame(list(range(1, 11))), "items", False)
    _protect(engine, "DELETE", 5)
    crud = BulkCrud(engine, chunk_size=1, commit_every_n_chunks=2)

    with pytest.raises(Exception, match="fila protegida"):
        crud.bulk_delete_from_chunks(iter([_frame([i])[["id"]] for i in range(1, 7)]), "items")

    assert crud.last_operation_rows_committed == 4
    assert [r[0] for r in _rows(engine)] == [5, 6, 7, 8, 9, 10]


# ------------------------------------------------------------------------------------------------- _skip_rows


def test_skip_rows_cuts_across_chunks_and_closes() -> None:
    chunks = _Chunks([_frame([1, 2]), _frame([3, 4, 5]), _frame([6])])

    out = [list(c["id"]) for c in _skip_rows(chunks, 3)]

    assert out == [[4, 5], [6]]
    assert chunks.closed


# ------------------------------------------------------------------------------------------------- ParallelBulkLoader


def test_retry_resumes_after_committed_rows_without_duplicates(engine: Engine) -> None:
    calls = {"n": 0}
    frames = [_frame([i, i + 1]) for i in range(1, 11, 2)]  # 10 filas en 5 chunks

    def reader() -> Iterator[pd.DataFrame]:
        calls["n"] += 1
        for index, frame in enumerate(frames):
            if calls["n"] == 1 and index == 3:
                raise OperationalError("COPY", {}, Exception("conexión perdida"), connection_invalidated=True)
            yield frame

    loader = ParallelBulkLoader(engine, chunk_size=2, max_workers=1, commit_every_n_chunks=1, max_retries=1)
    loader._sleep = MagicMock()  # type: ignore[method-assign]

    result = loader.load("items", [reader])

    assert result.partition_errors == []
    assert result.total_rows == 10
    assert [r[0] for r in _rows(engine)] == list(range(1, 11))  # sin IntegrityError: no se repitió nada
    assert result.partition_results[0].retries == 1


def test_parallel_update_and_delete(engine: Engine) -> None:
    BulkCrud(engine).bulk_insert_from_df(_frame(list(range(1, 21))), "items", False)
    loader = ParallelBulkLoader(engine, chunk_size=3, max_workers=2)
    parts = [_frame(list(range(1, 11)), "u"), _frame(list(range(11, 21)), "u")]

    updated = loader.update("items", [lambda p=p: iter([p]) for p in parts], partition_ranges=[(1, 10), (11, 20)])
    assert (updated.total_rows, updated.partition_errors) == (20, [])
    assert {r[1][0] for r in _rows(engine)} == {"u"}

    doomed = [_frame([1, 2])[["id"]], _frame([19, 20])[["id"]]]
    deleted = loader.delete("items", [lambda d=d: iter([d]) for d in doomed])
    assert (deleted.total_rows, deleted.partition_errors) == (4, [])
    assert [r[0] for r in _rows(engine)] == list(range(3, 19))


def test_parallel_update_validates_ranges(engine: Engine) -> None:
    loader = ParallelBulkLoader(engine, max_workers=2)
    with pytest.raises(ValueError, match="solapa"):
        loader.update("items", [lambda: iter([]), lambda: iter([])], partition_ranges=[(1, 10), (5, 20)])


def test_postgresql_without_temp_updates_with_one_worker(caplog: pytest.LogCaptureFixture) -> None:
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = False
    engine.pool = None
    loader = ParallelBulkLoader(engine, max_workers=4)
    seen_workers: list[int] = []
    loader._load_partition = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda *a, **k: seen_workers.append(1) or MagicMock(rows=1, error=None)
    )

    import util_bbdd.bulk._execution.parallel_loader as module

    original = module.ThreadPoolExecutor
    captured: dict[str, int] = {}

    class _Pool(original):  # type: ignore[misc, valid-type]
        def __init__(self, max_workers: int) -> None:
            captured["max_workers"] = max_workers
            super().__init__(max_workers=max_workers)

    module.ThreadPoolExecutor = _Pool  # type: ignore[misc]
    try:
        loader.update("t", [lambda: iter([])] * 3)
    finally:
        module.ThreadPoolExecutor = original  # type: ignore[misc]

    assert captured["max_workers"] == 1
    assert any("privilegio TEMP" in r.getMessage() for r in caplog.records)


def test_parallel_delete_retries_deadlock_even_with_max_retries_zero(engine: Engine) -> None:
    """R-5: InnoDB dio deadlock (1213) en el DELETE paralelo con particiones contiguas; UPDATE/DELETE son idempotentes."""
    pymysql_err = pytest.importorskip("pymysql.err")
    BulkCrud(engine).bulk_insert_from_df(_frame(list(range(1, 11))), "items", False)
    calls = {"n": 0}

    def reader() -> Iterator[pd.DataFrame]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("DELETE", {}, pymysql_err.OperationalError(1213, "Deadlock found"))
        yield _frame([1, 2, 3])[["id"]]

    loader = ParallelBulkLoader(engine, max_workers=1)  # max_retries=0
    loader._sleep = MagicMock()  # type: ignore[method-assign]
    result = loader.delete("items", [reader])

    assert result.partition_errors == []
    assert result.partition_results[0].retries == 1
    assert [r[0] for r in _rows(engine)] == list(range(4, 11))


def test_load_keeps_max_retries_zero(engine: Engine) -> None:
    pymysql_err = pytest.importorskip("pymysql.err")

    def reader() -> Iterator[pd.DataFrame]:
        raise OperationalError("INSERT", {}, pymysql_err.OperationalError(1213, "Deadlock found"))
        yield  # pragma: no cover

    result = ParallelBulkLoader(engine, max_workers=1).load("items", [reader])
    assert len(result.partition_errors) == 1
    assert result.partition_results[0].retries == 0
