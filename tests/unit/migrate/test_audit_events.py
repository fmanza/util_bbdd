"""F4 (sesión 2026-10-02c): rastro de auditoría opcional de ``MigrationPlan`` (``execute``, ``validate_views``)."""

from __future__ import annotations

import logging

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sqlalchemy import create_engine

from util_bbdd._core.exceptions import DatabaseOperationError
from util_bbdd.audit import AuditEvent, MemoryAuditSink
from util_bbdd.migrate import MigrationPlan, MigrationWarning
from util_bbdd.migrate._audit_events import MigrationAuditEvents
from util_bbdd.migrate.views.validation import ViewValidationResult


def _plan(statements: list[str], warnings: list[MigrationWarning] | None = None) -> MigrationPlan:
    emitter = MagicMock()
    emitter.emit_statements.return_value = statements
    return MigrationPlan(
        tables=[],
        warnings=list(warnings or []),
        source_schema="S",
        source_engine="oracle",
        target_engine="sqlite",
        emitter=emitter,
    )


def _warning(severity: str = "WARNING", column: str | None = "ID") -> MigrationWarning:
    return MigrationWarning(
        table="USERS",
        column=column,
        category="TYPE",
        target_type="INT",
        message="Aviso",
        severity=severity,  # type: ignore[arg-type]
        source_type="NUMBER",
    )


def _by_kind(sink: MemoryAuditSink, kind: str) -> list[AuditEvent]:
    return [e for e in sink.events() if e.kind == kind]


def test_execute_registra_avisos_sentencias_y_cierre(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    sink = MemoryAuditSink()
    plan = _plan(["CREATE TABLE a (x INT)", "-- nota\nCREATE TABLE b (y INT)"], [_warning()])

    plan.execute(engine, audit_sink=sink)

    statements = _by_kind(sink, "statement")
    assert [(e.status, e.operation, e.message) for e in statements] == [
        ("ok", "CREATE", "CREATE TABLE a (x INT)"),
        ("ok", "CREATE", "CREATE TABLE b (y INT)"),
    ]
    assert [e.attribute("position") for e in statements] == [1, 2]
    (run,) = _by_kind(sink, "run")
    assert run.status == "ok"
    assert run.attribute("statements_ok") == 2
    assert len({e.run_id for e in sink.events()}) == 1  # un run_id para toda la ejecución
    assert [e.status for e in _by_kind(sink, "plan_warning")] == ["warning"]
    engine.dispose()


def test_execute_fallido_registra_la_sentencia_y_el_run(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    sink = MemoryAuditSink()
    plan = _plan(["CREATE TABLE a (x INT)", "CREATE TABLE a (x INT)", "CREATE TABLE c (z INT)"])

    with pytest.raises(DatabaseOperationError, match="Sentencia 2/3"):
        plan.execute(engine, audit_sink=sink)

    assert [e.status for e in _by_kind(sink, "statement")] == ["ok", "failed"]
    failed = _by_kind(sink, "statement")[1]
    assert failed.error_type == "OperationalError"
    (run,) = _by_kind(sink, "run")
    assert (run.status, run.error_type, run.attribute("statements_ok")) == ("failed", "MigrationStatementError", 1)
    engine.dispose()


def test_execute_con_execute_custom_one() -> None:
    target = MagicMock(spec=["execute_custom_one"])
    sink = MemoryAuditSink()

    _plan(["CREATE TABLE a (x INT)"]).execute(target, audit_sink=sink)

    assert [e.status for e in _by_kind(sink, "statement")] == ["ok"]
    assert [e.status for e in _by_kind(sink, "run")] == ["ok"]


def test_plan_bloqueado_registra_avisos_y_run_fallido() -> None:
    target = MagicMock()
    sink = MemoryAuditSink()
    plan = _plan(["CREATE TABLE a (x INT)"], [_warning("ERROR")])

    with pytest.raises(ValueError, match="ERROR"):
        plan.execute(target, audit_sink=sink)

    target.execute_custom_one.assert_not_called()
    assert [e.status for e in _by_kind(sink, "plan_warning")] == ["error"]
    (run,) = _by_kind(sink, "run")
    assert (run.status, run.error_type, run.attribute("statements_total")) == ("failed", "ValueError", 0)


def test_sin_audit_sink_no_cambia_nada() -> None:
    target = MagicMock(spec=["execute_custom_one"])
    _plan(["CREATE TABLE a (x INT)"]).execute(target)
    target.execute_custom_one.assert_called_once_with("CREATE TABLE a (x INT)", {})


class _BrokenSink:
    def write(self, events: Sequence[AuditEvent], /) -> None:
        raise OSError("disco lleno")

    def close(self) -> None:
        pass


def test_fallo_del_destino_no_interrumpe_la_migracion(caplog: pytest.LogCaptureFixture) -> None:
    target = MagicMock(spec=["execute_custom_one"])

    with caplog.at_level(logging.ERROR, logger="util_bbdd.migrate._audit_events"):
        _plan(["CREATE TABLE a (x INT)", "CREATE TABLE b (y INT)"]).execute(target, audit_sink=_BrokenSink())

    assert target.execute_custom_one.call_count == 2
    assert any("No se pudo escribir la auditoría de la migración" in r.getMessage() for r in caplog.records)


def test_audit_events_del_plan() -> None:
    plan = _plan([], [_warning("INFO", column=None), _warning("ERROR")])

    events = plan.audit_events()

    assert [(e.status, e.target, e.operation) for e in events] == [
        ("info", "USERS", "TYPE"),
        ("error", "USERS.ID", "TYPE"),
    ]
    assert events[0].attribute("source_engine") == "oracle"
    assert events[0].engine == "sqlite"


def test_view_validation_events() -> None:
    results = [
        ViewValidationResult(view="v_ok", valid=True, method="transaction"),
        ViewValidationResult(view="v_mal", valid=False, method="syntax", error="near X"),
        ViewValidationResult(view="v_nada", valid=None, method="none", error="sin sqlglot"),
    ]

    events = MigrationAuditEvents.view_validation(results, engine="mariadb", run_id="r1")

    assert [(e.target, e.status) for e in events] == [("v_ok", "ok"), ("v_mal", "failed"), ("v_nada", "skipped")]
    assert {e.run_id for e in events} == {"r1"}


def test_first_sql_line_trunca_y_salta_comentarios() -> None:
    statement = "-- comentario\n\n  ALTER TABLE t " + "x" * 300
    line = MigrationAuditEvents.first_sql_line(statement)
    assert line.startswith("ALTER TABLE t")
    assert len(line) == MigrationAuditEvents.STATEMENT_PREVIEW


def test_validate_views_con_audit_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    from util_bbdd.migrate.views import validation

    results = [ViewValidationResult(view="v", valid=False, method="syntax", error="near X")]
    monkeypatch.setattr(validation, "validate_plan_views", lambda plan, target, include_tables: results)
    sink = MemoryAuditSink()

    assert _plan([]).validate_views(None, audit_sink=sink) == results
    assert [(e.kind, e.target, e.status, e.message) for e in sink.events()] == [
        ("view_validation", "v", "failed", "near X")
    ]


def test_fallo_del_emisor_registra_el_run_fallido() -> None:
    """Hallazgo 2 del audit-code 2026-10-02c: antes no quedaba ningún evento run."""
    plan = _plan([])
    plan.emitter.emit_statements.side_effect = RuntimeError("tipo sin traducción")
    sink = MemoryAuditSink()

    with pytest.raises(RuntimeError, match="tipo sin traducción"):
        plan.execute(MagicMock(spec=["execute_custom_one"]), audit_sink=sink)

    (run,) = _by_kind(sink, "run")
    assert (run.status, run.error_type, run.attribute("statements_total")) == ("failed", "RuntimeError", 0)


def test_execute_custom_one_fallido_registra_la_sentencia() -> None:
    target = MagicMock(spec=["execute_custom_one"])
    target.execute_custom_one.side_effect = [None, RuntimeError("tabla existe")]
    sink = MemoryAuditSink()

    with pytest.raises(RuntimeError):
        _plan(["CREATE TABLE a (x INT)", "CREATE TABLE b (y INT)"]).execute(target, audit_sink=sink)

    assert [(e.status, e.error_type) for e in _by_kind(sink, "statement")] == [("ok", None), ("failed", "RuntimeError")]
