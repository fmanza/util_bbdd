"""U-M5 (G1 de util_bbdd_web): progreso y cancelación cooperativa en ``MigrationPlan.execute``."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from sqlalchemy import create_engine, text

from util_bbdd.audit import MemoryAuditSink
from util_bbdd.exceptions import MigrationStatementError, OperationCancelledError
from util_bbdd.migrate import MigrationPlan
from util_bbdd.progress import CancellationToken, ProgressEvent

STATEMENTS = ["CREATE TABLE a (x INT)", "-- nota\nCREATE TABLE b (y INT)", "CREATE TABLE c (z INT)"]


def _plan(statements: list[str]) -> MigrationPlan:
    emitter = MagicMock()
    emitter.emit_statements.return_value = statements
    return MigrationPlan(
        tables=[], warnings=[], source_schema="S", source_engine="oracle", target_engine="sqlite", emitter=emitter
    )


def _summary(events: list[ProgressEvent]) -> list[tuple[str, str, int, int | None, str]]:
    return [(e.operation, e.phase, e.current, e.total, e.message) for e in events]


def _tables(engine: Any) -> list[str]:
    with engine.connect() as conn:
        return [row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY 1"))]


def test_one_event_per_statement(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    events: list[ProgressEvent] = []
    _plan(STATEMENTS).execute(engine, on_progress=events.append)
    assert _summary(events) == [
        ("migrate", "statements", 0, 3, ""),
        ("migrate", "statements", 1, 3, "CREATE TABLE a (x INT)"),
        ("migrate", "statements", 2, 3, "CREATE TABLE b (y INT)"),
        ("migrate", "statements", 3, 3, "CREATE TABLE c (z INT)"),
    ]
    engine.dispose()


def test_failed_statement_also_reports_progress(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    events: list[ProgressEvent] = []
    with pytest.raises(MigrationStatementError):
        _plan(["CREATE TABLE a (x INT)", "CREATE TABLE a (x INT)"]).execute(engine, on_progress=events.append)
    assert [e.current for e in events] == [0, 1, 2]
    engine.dispose()


def test_dry_run_only_reports_the_start() -> None:
    events: list[ProgressEvent] = []
    _plan(STATEMENTS).execute(None, dry_run=True, on_progress=events.append)
    assert _summary(events) == [("migrate", "statements", 0, 3, "")]


def test_cancel_between_statements_keeps_the_applied_ones(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    token = CancellationToken()
    sink = MemoryAuditSink()

    def on_progress(event: ProgressEvent) -> None:
        if event.current == 1:
            token.cancel()

    with pytest.raises(OperationCancelledError) as caught:
        _plan(STATEMENTS).execute(engine, on_progress=on_progress, cancel_token=token, audit_sink=sink)

    assert (caught.value.cancelled_operation, caught.value.phase) == ("migrate", "statements")
    assert _tables(engine) == ["a"]  # la primera quedó aplicada; las demás no se enviaron
    (run,) = [e for e in sink.events() if e.kind == "run"]
    assert (run.status, run.error_type, run.attribute("statements_ok")) == ("failed", "OperationCancelledError", 1)
    engine.dispose()


def test_cancelled_before_start_sends_nothing(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    token = CancellationToken()
    token.cancel()
    with pytest.raises(OperationCancelledError):
        _plan(STATEMENTS).execute(engine, cancel_token=token)
    assert _tables(engine) == []
    engine.dispose()


def test_cancel_with_custom_one_target() -> None:
    target = MagicMock(spec=["execute_custom_one"])
    token = CancellationToken()
    target.execute_custom_one.side_effect = lambda sql, params: token.cancel()
    with pytest.raises(OperationCancelledError):
        _plan(STATEMENTS).execute(target, cancel_token=token)
    assert target.execute_custom_one.call_count == 1


def test_failing_callback_does_not_stop_execution(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")

    def broken(event: ProgressEvent) -> None:
        raise RuntimeError("callback roto")

    result = _plan(STATEMENTS).execute(engine, on_progress=broken)
    assert result.applied == 3
    engine.dispose()
