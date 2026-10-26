"""Contrato de ``util_bbdd.progress``: evento, token de cancelación y ``ProgressReporter`` (G1, v4.1.0)."""

from __future__ import annotations

import ast
import logging
import pickle
import threading

from pathlib import Path

import pytest

from util_bbdd.exceptions import DatabaseException, OperationCancelledError
from util_bbdd.progress import CancellationToken, ProgressCallback, ProgressEvent, ProgressReporter

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------------------------------------------------
# ProgressEvent
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "total", "expected"),
    [(0, None, None), (3, 12, 0.25), (0, 0, 1.0), (12, 12, 1.0), (13, 12, 1.0)],
)
def test_fraction(current: int, total: int | None, expected: float | None) -> None:
    assert ProgressEvent("dump", "tables", current, total).fraction == expected


@pytest.mark.parametrize(("current", "total"), [(-1, None), (0, -1)])
def test_negative_counters_are_rejected(current: int, total: int | None) -> None:
    with pytest.raises(ValueError, match="negativo"):
        ProgressEvent("dump", "tables", current, total)


def test_event_is_immutable() -> None:
    event = ProgressEvent("bulk", "batches", 1, 2)
    with pytest.raises(AttributeError):
        event.current = 2  # type: ignore[misc]


def test_any_one_argument_callable_is_a_callback() -> None:
    events: list[ProgressEvent] = []
    assert isinstance(events.append, ProgressCallback)


# ---------------------------------------------------------------------------------------------------------------------
# CancellationToken
# ---------------------------------------------------------------------------------------------------------------------


def test_token_starts_active_and_cancel_is_idempotent() -> None:
    token = CancellationToken()
    assert not token.is_cancelled()
    token.raise_if_cancelled("dump")  # no lanza
    token.cancel()
    token.cancel()
    assert token.is_cancelled()
    assert repr(token) == "CancellationToken(cancelled=True)"


def test_raise_if_cancelled_carries_operation_and_phase() -> None:
    token = CancellationToken()
    token.cancel()
    with pytest.raises(OperationCancelledError) as info:
        token.raise_if_cancelled("dump", "tables")
    assert isinstance(info.value, DatabaseException)
    assert (info.value.cancelled_operation, info.value.phase) == ("dump", "tables")
    assert "dump" in str(info.value)


def test_cancel_from_another_thread_is_seen() -> None:
    token = CancellationToken()
    thread = threading.Thread(target=token.cancel)
    thread.start()
    thread.join()
    assert token.is_cancelled()


def test_cancelled_error_pickles_with_its_context() -> None:
    restored = pickle.loads(pickle.dumps(OperationCancelledError("x", phase="lotes", cancelled_operation="bulk")))
    assert (restored.phase, restored.cancelled_operation) == ("lotes", "bulk")


# ---------------------------------------------------------------------------------------------------------------------
# ProgressReporter
# ---------------------------------------------------------------------------------------------------------------------


def test_reporter_without_callback_or_token_does_nothing() -> None:
    reporter = ProgressReporter("doc")
    assert not reporter.enabled
    reporter.emit("word", 1, 2)
    reporter.check("word")
    assert not reporter.is_cancelled()


def test_reporter_builds_events_with_its_operation() -> None:
    events: list[ProgressEvent] = []
    reporter = ProgressReporter("compare", events.append)
    reporter.emit("tables", 0, 3)
    reporter.emit("tables", 1, 3, "clientes")
    assert events == [ProgressEvent("compare", "tables", 0, 3), ProgressEvent("compare", "tables", 1, 3, "clientes")]


def test_failing_callback_is_logged_once_and_dropped(caplog: pytest.LogCaptureFixture) -> None:
    calls: list[ProgressEvent] = []

    def broken(event: ProgressEvent) -> None:
        calls.append(event)
        raise RuntimeError("receptor roto")

    reporter = ProgressReporter("migrate", broken)
    with caplog.at_level(logging.WARNING):
        reporter.emit("statements", 1, 5)
        reporter.emit("statements", 2, 5)
    assert len(calls) == 1
    assert not reporter.enabled
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].exc_info is not None


def test_reporter_check_raises_when_token_is_cancelled() -> None:
    token = CancellationToken()
    reporter = ProgressReporter("graph", cancel_token=token)
    reporter.check("tables")
    token.cancel()
    assert reporter.is_cancelled()
    with pytest.raises(OperationCancelledError) as info:
        reporter.check("tables")
    assert (info.value.cancelled_operation, info.value.phase) == ("graph", "tables")


def test_progress_imports_only_core() -> None:
    """Capa 2 (Regla #6): ``progress`` solo puede importar ``_core``; no conoce a sus consumidores."""
    package = Path(__file__).resolve().parents[3] / "src" / "util_bbdd" / "progress"
    imported: set[str] = set()
    for path in package.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 2 and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("util_bbdd."):
                imported.add(node.module.split(".")[1])
    assert imported <= {"_core"}
