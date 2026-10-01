"""``ParallelBulkLoader(on_error="isolate", rejects_csv_path, max_rejects)`` (Fase 3, sesión 2026-10-01t).

Cada partición aparta sus filas con errores de datos a un CSV común (columna ``particion``, posición dentro de la
partición) y aplica el resto. Un intento que ya escribió rechazos no se reintenta (D-2: los duplicaría).
"""

from __future__ import annotations

import csv

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, ForeignKey, Integer, MetaData, String, Table, create_engine, event, text

from util_bbdd.bulk import ParallelBulkLoader

pytestmark = pytest.mark.unit


def _engine(tmp_path: Path, *, foreign_keys: bool = False) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    if foreign_keys:

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_connection: Any, _record: Any) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    metadata = MetaData()
    Table("items", metadata, Column("id", Integer, primary_key=True), Column("v", String(10), nullable=False))
    Table("child", metadata, Column("id", Integer, primary_key=True), Column("item_id", ForeignKey("items.id")))
    metadata.create_all(eng)
    return eng


def _frame(ids: list[int], v: str = "v", none_at: tuple[int, ...] = ()) -> pd.DataFrame:
    return pd.DataFrame({"id": ids, "v": [None if i in none_at else f"{v}{i}" for i in ids]})


def _ids(engine: Engine) -> list[int]:
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT id FROM items ORDER BY id"))]


def _rejects(path: Path) -> list[tuple[str, int, int]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [(r["operacion"], int(r["particion"]), int(r["fila"])) for r in csv.DictReader(handle, delimiter="\t")]


def _reader(*chunks: pd.DataFrame) -> Callable[[], Iterator[pd.DataFrame]]:
    return lambda: iter(chunks)


def _loader(engine: Engine, tmp_path: Path, **kwargs: Any) -> ParallelBulkLoader:
    kwargs.setdefault("max_workers", 1)  # SQLite: un solo escritor
    kwargs.setdefault("chunk_size", 2)
    return ParallelBulkLoader(engine, on_error="isolate", rejects_csv_path=tmp_path / "rejects.csv", **kwargs)


def test_load_rejects_rows_per_partition(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    audit = tmp_path / "audit.csv"
    loader = _loader(engine, tmp_path, audit_csv_path=audit)

    result = loader.load(
        "items",
        [
            _reader(_frame([1, 2, 3], none_at=(2,))),
            _reader(_frame([4, 5])),
            _reader(_frame([6, 7]), _frame([8, 9, 10], none_at=(10,))),
        ],
    )

    assert not result.partition_errors
    assert _ids(engine) == [1, 3, 4, 5, 6, 7, 8, 9]
    assert sorted(_rejects(tmp_path / "rejects.csv")) == [("INSERT", 0, 1), ("INSERT", 2, 4)]
    assert result.rows_rejected == 2
    assert [pr.rows_rejected for pr in sorted(result.partition_results, key=lambda pr: pr.index)] == [1, 0, 1]
    assert result.audited_rows + result.rows_rejected == result.total_rows == 10


def test_update_and_delete_reject_rows(tmp_path: Path) -> None:
    engine = _engine(tmp_path, foreign_keys=True)
    ParallelBulkLoader(engine, max_workers=1).load("items", [_reader(_frame(list(range(1, 9))))])
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO child (id, item_id) VALUES (1, 7)"))
    loader = _loader(engine, tmp_path)

    updated = loader.update("items", [_reader(_frame([1, 2], "u")), _reader(_frame([3, 4], "u", none_at=(4,)))])
    deleted = loader.delete("items", [_reader(pd.DataFrame({"id": [5, 6]})), _reader(pd.DataFrame({"id": [7, 8]}))])

    assert updated.rows_rejected == 1 and deleted.rows_rejected == 1
    assert _ids(engine) == [1, 2, 3, 4, 7]
    assert sorted(_rejects(tmp_path / "rejects.csv")) == [("DELETE", 1, 0), ("UPDATE", 1, 1)]


class _FailingOnce:
    """Lector que en la primera llamada entrega ``first`` chunks y luego lanza; en las siguientes, todo."""

    def __init__(self, chunks: list[pd.DataFrame], first: int) -> None:
        self.chunks = chunks
        self.first = first
        self.calls = 0

    def __call__(self) -> Iterator[pd.DataFrame]:
        self.calls += 1
        if self.calls == 1:
            yield from self.chunks[: self.first]
            raise ConnectionResetError("corte simulado")
        yield from self.chunks


def test_attempt_with_rejects_is_not_retried(tmp_path: Path) -> None:
    """D-2: el intento ya escribió un rechazo; reintentarlo lo duplicaría en el CSV."""
    engine = _engine(tmp_path)
    reader = _FailingOnce([_frame([1, 2], none_at=(2,)), _frame([3])], first=1)
    loader = _loader(engine, tmp_path, max_retries=3, retry_on=lambda _exc: True, retry_backoff=(0, 0))

    result = loader.load("items", [reader])

    assert reader.calls == 1
    assert len(result.partition_errors) == 1 and "duplicaría" in result.partition_errors[0]
    assert _rejects(tmp_path / "rejects.csv") == [("INSERT", 0, 1)]
    assert _ids(engine) == []  # atómica: el fallo deshizo la partición


def test_attempt_without_rejects_is_retried_and_positions_skip_committed_rows(tmp_path: Path) -> None:
    """R-1: con cadencia, el reintento salta las filas confirmadas; la posición del rechazo sigue siendo la de la partición."""
    engine = _engine(tmp_path)
    reader = _FailingOnce([_frame([1, 2]), _frame([3, 4], none_at=(4,))], first=1)
    loader = _loader(
        engine, tmp_path, commit_every_n_chunks=1, max_retries=1, retry_on=lambda _exc: True, retry_backoff=(0, 0)
    )

    result = loader.load("items", [reader])

    assert reader.calls == 2
    assert not result.partition_errors
    assert _ids(engine) == [1, 2, 3]
    assert _rejects(tmp_path / "rejects.csv") == [("INSERT", 0, 3)]  # 2 saltadas + posición 1 del resto


def test_max_rejects_applies_per_partition(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    loader = _loader(engine, tmp_path, max_rejects=1)

    result = loader.load("items", [_reader(_frame([1, 2, 3], none_at=(1, 3))), _reader(_frame([4, 5], none_at=(5,)))])

    errors = {pr.index: pr.error for pr in result.partition_results}
    assert errors[0] is not None and errors[1] is None
    assert _ids(engine) == [4]
    assert sorted(_rejects(tmp_path / "rejects.csv")) == [("INSERT", 0, 0), ("INSERT", 1, 1)]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"on_error": "skip"},
        {"on_error": "isolate"},
        {"rejects_csv_path": Path("r.csv")},
        {"on_error": "isolate", "rejects_csv_path": Path("r.csv"), "max_rejects": -1},
    ],
)
def test_invalid_parameters_fail_before_the_pool(tmp_path: Path, kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        ParallelBulkLoader(_engine(tmp_path), **kwargs)


def test_raise_is_unchanged(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    result = ParallelBulkLoader(engine, max_workers=1).load("items", [_reader(_frame([1, 2], none_at=(2,)))])

    assert len(result.partition_errors) == 1
    assert result.rows_rejected == 0
    assert _ids(engine) == []
