"""U-V8 (G1 de util_bbdd_web): progreso y cancelación cooperativa en ``DumpOrchestrator.run``."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.audit import MemoryAuditSink
from util_bbdd.dump import ConstraintManager, DumpConfig, DumpOrchestrator
from util_bbdd.exceptions import OperationCancelledError
from util_bbdd.progress import CancellationToken, ProgressEvent

pytestmark = pytest.mark.unit


def _engines(tmp_path: Path) -> tuple[Engine, Engine]:
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    for engine in (src, dst):
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE a (id INTEGER PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE b (id INTEGER PRIMARY KEY)"))
    with src.begin() as conn:
        conn.execute(text("INSERT INTO a VALUES (1), (2), (3), (4), (5)"))
        conn.execute(text("INSERT INTO b VALUES (1)"))
    with dst.begin() as conn:
        conn.execute(text("INSERT INTO b VALUES (99)"))
    return src, dst


def _config(src: Engine, dst: Engine, tmp_path: Path, **extra: Any) -> DumpConfig:
    return DumpConfig(src, dst, output_dir=tmp_path, truncate_target=True, chunk_size=2, **extra)


def _ids(engine: Engine, table: str) -> list[int]:
    with engine.connect() as conn:
        return list(conn.execute(text(f"SELECT id FROM {table} ORDER BY id")).scalars())


def _summary(events: list[ProgressEvent]) -> list[tuple[str, int, int | None, str]]:
    assert {e.operation for e in events} <= {"dump"}
    return [(e.phase, e.current, e.total, e.message) for e in events]


def test_events_per_table_and_batch(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    events: list[ProgressEvent] = []

    DumpOrchestrator(_config(src, dst, tmp_path)).run(on_progress=events.append)

    assert _summary(events) == [
        ("tables", 0, 2, ""),
        ("rows", 2, 5, "a"),
        ("rows", 4, 5, "a"),
        ("rows", 5, 5, "a"),
        ("tables", 1, 2, "a"),
        ("rows", 1, 1, "b"),
        ("tables", 2, 2, "b"),
    ]


def test_rows_total_is_none_without_row_counts(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    events: list[ProgressEvent] = []

    DumpOrchestrator(_config(src, dst, tmp_path, collect_row_counts=False)).run(on_progress=events.append)

    assert {e.total for e in events if e.phase == "rows"} == {None}


def test_cancel_between_batches_restores_constraints_first(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    token = CancellationToken()
    sink = MemoryAuditSink()
    order: list[str] = []
    original_enable = ConstraintManager.enable_all

    def enable_all(manager: ConstraintManager) -> Any:
        order.append("enable_all")
        return original_enable(manager)

    def on_progress(event: ProgressEvent) -> None:
        if (event.phase, event.current, event.message) == ("rows", 2, "a"):
            token.cancel()

    with (
        patch.object(ConstraintManager, "enable_all", enable_all),
        pytest.raises(OperationCancelledError) as caught,
    ):
        try:
            DumpOrchestrator(_config(src, dst, tmp_path, audit_sink=sink)).run(
                on_progress=on_progress, cancel_token=token
            )
        finally:
            order.append("raised")

    assert (caught.value.cancelled_operation, caught.value.phase) == ("dump", "rows")
    assert order == ["enable_all", "raised"]  # las constraints se reactivan antes de que salga la excepción
    assert _ids(dst, "a") == []  # la tabla en curso se deshace (una transacción por tabla)
    assert _ids(dst, "b") == []  # vaciada al empezar y no cargada
    (run,) = [e for e in sink.events() if e.kind == "run"]
    assert (run.status, run.error_type) == ("failed", "OperationCancelledError")


def test_cancel_between_tables_keeps_the_finished_ones(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    token = CancellationToken()

    def on_progress(event: ProgressEvent) -> None:
        if (event.phase, event.current) == ("tables", 1):
            token.cancel()

    with pytest.raises(OperationCancelledError) as caught:
        DumpOrchestrator(_config(src, dst, tmp_path)).run(on_progress=on_progress, cancel_token=token)

    assert caught.value.phase == "tables"
    assert _ids(dst, "a") == [1, 2, 3, 4, 5]
    assert _ids(dst, "b") == []


def test_cancelled_before_start_touches_nothing(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    token = CancellationToken()
    token.cancel()
    events: list[ProgressEvent] = []

    with pytest.raises(OperationCancelledError):
        DumpOrchestrator(_config(src, dst, tmp_path)).run(on_progress=events.append, cancel_token=token)

    assert events == []
    assert _ids(dst, "b") == [99]  # ni siquiera se vació


def test_failing_callback_does_not_stop_the_dump(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)

    def broken(_event: ProgressEvent) -> None:
        raise RuntimeError("callback roto")

    result = DumpOrchestrator(_config(src, dst, tmp_path)).run(on_progress=broken)

    assert [r.status for r in result.table_results] == ["success", "success"]


def test_run_without_progress_is_unchanged(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    result = DumpOrchestrator(_config(src, dst, tmp_path)).run()
    assert _ids(dst, "a") == [1, 2, 3, 4, 5]
    assert [r.status for r in result.table_results] == ["success", "success"]
