"""U-M4 (G27 de util_bbdd_web): ``MigrationPlan.check_target`` y ``execute(dry_run=, stop_on_error=)``."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from sqlalchemy import create_engine, text

from util_bbdd.audit import AuditEvent, MemoryAuditSink
from util_bbdd.exceptions import DatabaseOperationError, MigrationStatementError
from util_bbdd.migrate import (
    CanonicalTable,
    CanonicalView,
    ExecutionResult,
    MigrationPlan,
    MigrationPlanner,
    TargetCheck,
    TargetConflict,
)

from ._snapshot_source import FakeSource, table, view


def _plan(
    statements: list[str] | None = None,
    *,
    tables: tuple[str, ...] = (),
    views: tuple[str, ...] = (),
    target_engine: str = "sqlite",
) -> MigrationPlan:
    emitter = MagicMock()
    emitter.emit_statements.return_value = statements or []
    return MigrationPlan(
        tables=[CanonicalTable(name, name, "S", [], [], [], [], "", []) for name in tables],
        warnings=[],
        source_schema="S",
        source_engine="oracle",
        target_engine=target_engine,
        emitter=emitter,
        views=[CanonicalView(name, name, "S", "SELECT 1", [], "", []) for name in views],
    )


def _run(sink: MemoryAuditSink) -> AuditEvent:
    (run,) = [e for e in sink.events() if e.kind == "run"]
    return run


# ─── check_target ────────────────────────────────────────────────────────────


def test_check_target_reports_existing_tables_and_views(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE clientes (id INTEGER)"))
        conn.execute(text("CREATE VIEW v_ventas AS SELECT 1 AS x"))
    plan = _plan(tables=("CLIENTES", "PEDIDOS", "V_VENTAS"), views=("V_CLIENTES",))

    check = plan.check_target(engine)

    assert isinstance(check, TargetCheck)
    assert check.schema == "main"
    assert check.conflicts == (
        TargetConflict("CLIENTES", "table", "clientes", "table"),
        TargetConflict("V_VENTAS", "table", "v_ventas", "view"),
    )
    assert not check.ok
    assert check.views == ()
    engine.dispose()


def test_check_target_without_conflicts_is_ok() -> None:
    source = FakeSource("mariadb", [table("otra"), view("otra_vista", "SELECT 1")])
    check = _plan(tables=("CLIENTES",), views=("V_CLIENTES",)).check_target(source)
    assert check.ok
    assert check.conflicts == ()


def test_check_target_reads_fresh_catalog_of_the_schema() -> None:
    source = FakeSource("mariadb", [table("clientes")])
    check = _plan(tables=("clientes",)).check_target(source, schema="destino")
    assert source.invalidations == ["destino"]
    assert check.schema == "destino"
    assert [c.name for c in check.conflicts] == ["clientes"]


def test_check_target_uses_pg_schema_by_default() -> None:
    plan = MigrationPlanner(target_engine="postgresql", pg_schema="destino").plan(
        _oracle_manager(), "S"
    )  # pg_schema del emitter
    source = FakeSource("postgresql")
    assert plan.check_target(source).schema == "destino"
    assert plan.check_target(source, schema="otro").schema == "otro"


def test_check_target_accepts_a_manager() -> None:
    manager = MagicMock(spec=["metadata_source"])
    manager.metadata_source = FakeSource("mariadb", [table("clientes")])
    assert [c.name for c in _plan(tables=("CLIENTES",)).check_target(manager).conflicts] == ["CLIENTES"]


def test_check_target_validates_views_on_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from util_bbdd.migrate.views.validation import ViewValidationResult

    results = [ViewValidationResult("V1", True, "syntax"), ViewValidationResult("V2", False, "syntax", "error")]
    calls: list[dict[str, Any]] = []

    def fake_validate(self: MigrationPlan, target: Any, **kwargs: Any) -> list[ViewValidationResult]:
        calls.append(kwargs)
        return results

    monkeypatch.setattr(MigrationPlan, "validate_views", fake_validate)
    check = _plan(views=("V1", "V2")).check_target(FakeSource("mariadb"), validate_views=True)
    assert calls == [{"include_tables": True}]
    assert check.invalid_views == (results[1],)
    assert not check.ok


def _oracle_manager() -> Any:
    from ._snapshot_source import col, fake_manager, pk

    return fake_manager(
        "oracle", table("T"), col("T", "ID", 1, "NUMBER(5)", "NUMBER", precision=5, scale=0), pk("T", "ID")
    )


# ─── execute(dry_run=, stop_on_error=) ──────────────────────────────────────


def test_dry_run_sends_nothing() -> None:
    target = MagicMock()
    sink = MemoryAuditSink()
    result = _plan(["CREATE TABLE a (x INT)", "-- solo comentario", "CREATE TABLE b (y INT)"]).execute(
        target, dry_run=True, audit_sink=sink
    )
    assert result == ExecutionResult(("CREATE TABLE a (x INT)", "CREATE TABLE b (y INT)"), 0, (), True)
    assert result.total == 2 and result.ok
    assert target.mock_calls == []
    run = _run(sink)
    assert (run.status, run.operation, run.attribute("dry_run")) == ("ok", "DRY_RUN", True)
    assert [e for e in sink.events() if e.kind == "statement"] == []


def test_dry_run_still_refuses_a_blocked_plan() -> None:
    plan = _plan(["CREATE TABLE a (x INT)"])
    plan.warnings.append(MagicMock(severity="ERROR", message="bloqueado"))
    with pytest.raises(ValueError, match="bloqueado"):
        plan.execute(None, dry_run=True)


def test_execute_returns_the_result(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    result = _plan(["CREATE TABLE a (x INT)", "CREATE TABLE b (y INT)"]).execute(engine)
    assert (result.applied, result.failures, result.dry_run) == (2, (), False)
    engine.dispose()


def test_failure_reports_position_and_statement(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    plan = _plan(["CREATE TABLE a (x INT)", "-- nota\nCREATE TABLE a (x INT)", "CREATE TABLE c (z INT)"])

    with pytest.raises(MigrationStatementError, match=r"Sentencia 2/3 del plan falló \(CREATE TABLE a") as caught:
        plan.execute(engine)

    exc = caught.value
    assert isinstance(exc, DatabaseOperationError)  # compatibilidad: lo que se lanzaba hasta 4.2.0
    assert (exc.position, exc.total, exc.statement) == (2, 3, "-- nota\nCREATE TABLE a (x INT)")
    assert exc.result.applied == 1
    (failure,) = exc.result.failures
    assert (failure.position, failure.error_type) == (2, "OperationalError")
    with engine.connect() as conn:  # la tercera no se envió
        assert conn.execute(text("SELECT name FROM sqlite_master WHERE name = 'c'")).fetchall() == []
    engine.dispose()


def test_stop_on_error_false_continues(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    sink = MemoryAuditSink()
    plan = _plan(["CREATE TABLE a (x INT)", "CREATE TABLE a (x INT)", "CREATE TABLE c (z INT)"])

    result = plan.execute(engine, stop_on_error=False, audit_sink=sink)

    assert result.applied == 2
    assert [f.position for f in result.failures] == [2]
    assert not result.ok
    with engine.connect() as conn:
        assert conn.execute(text("SELECT name FROM sqlite_master WHERE name = 'c'")).fetchall() == [("c",)]
    run = _run(sink)
    assert (run.status, run.attribute("statements_ok"), run.attribute("statements_failed")) == ("failed", 2, 1)
    engine.dispose()


def test_custom_one_target_keeps_its_error_with_a_note() -> None:
    target = MagicMock(spec=["execute_custom_one"])
    target.execute_custom_one.side_effect = [None, RuntimeError("tabla existe"), None]
    plan = _plan(["CREATE TABLE a (x INT)", "CREATE TABLE b (y INT)", "CREATE TABLE c (z INT)"])

    with pytest.raises(RuntimeError, match="tabla existe") as caught:
        plan.execute(target)
    assert caught.value.__notes__ == ["Sentencia 2/3 del plan: CREATE TABLE b (y INT)"]
    assert target.execute_custom_one.call_count == 2


def test_custom_one_target_stop_on_error_false() -> None:
    target = MagicMock(spec=["execute_custom_one"])
    target.execute_custom_one.side_effect = [RuntimeError("no"), None]
    result = _plan(["CREATE TABLE a (x INT)", "CREATE TABLE b (y INT)"]).execute(target, stop_on_error=False)
    assert result.applied == 1
    assert [(f.position, f.error_type, f.message) for f in result.failures] == [(1, "RuntimeError", "no")]
