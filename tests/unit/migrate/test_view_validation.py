"""``validate_plan_views`` / ``MigrationPlan.validate_views`` (V3, sesión 2026-09-29c-migrate-views).

La rama transaccional se prueba con SQLite en memoria (admite savepoints) haciéndose pasar por PostgreSQL: el
emisor falso devuelve el DDL tal cual y la validación debe dejar el destino vacío.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine

from util_bbdd.migrate.views import validation
from util_bbdd.migrate.views.validation import ViewValidationResult, validate_plan_views


def _sqlite() -> Engine:
    """SQLite con DDL transaccional (receta de SQLAlchemy: pysqlite no abre transacción antes de un DDL)."""
    engine = create_engine("sqlite:///:memory:", connect_args={"isolation_level": None})
    event.listen(engine, "begin", lambda conn: conn.exec_driver_sql("BEGIN"))
    return engine


class _Emitter:
    def __init__(self) -> None:
        self.emitted_tables: list[Any] = []

    def emit_statements(self, tables: list[Any], views: list[Any], _other: list[Any]) -> list[str]:
        self.emitted_tables += tables
        return [t.ddl for t in tables] + [f"CREATE VIEW {v.name} AS {v.query}" for v in views]


def _plan(target_engine: str, views: list[tuple[str, str]], tables: list[str] | None = None) -> Any:
    return SimpleNamespace(
        target_engine=target_engine,
        emitter=_Emitter(),
        tables=[SimpleNamespace(ddl=ddl) for ddl in (tables or [])],
        views=[SimpleNamespace(name=name, query=query) for name, query in views],
    )


class TestTransactional:
    def test_requires_target(self) -> None:
        with pytest.raises(ValueError, match="necesita la conexión del destino"):
            validate_plan_views(_plan("postgresql", [("v", "SELECT 1")]))

    def test_valid_and_invalid_views_leave_nothing_behind(self) -> None:
        engine = _sqlite()
        plan = _plan(
            "sqlserver",
            [("v_ok", "SELECT id FROM t"), ("v_bad", "SELECT FROM WHERE"), ("v_empty", "")],
            tables=["CREATE TABLE t (id INTEGER)"],
        )
        results = validate_plan_views(plan, engine)
        assert [(r.view, r.valid, r.method) for r in results] == [
            ("v_ok", True, "transaction"),
            ("v_bad", False, "transaction"),
        ]
        assert results[1].error and "syntax error" in results[1].error
        assert inspect(engine).get_table_names() == [] and inspect(engine).get_view_names() == []

    def test_include_tables_false_does_not_create_tables(self) -> None:
        engine = _sqlite()
        plan = _plan("postgresql", [("v", "SELECT 1 AS x")], tables=["CREATE TABLE t (id INTEGER)"])
        assert validate_plan_views(plan, engine, include_tables=False)[0].valid is True
        assert plan.emitter.emitted_tables == []

    def test_accepts_manager_with_get_sqlalchemy_engine(self) -> None:
        engine = _sqlite()
        manager = SimpleNamespace(get_sqlalchemy_engine=lambda: engine)
        assert validate_plan_views(_plan("postgresql", [("v", "SELECT 1 AS x")]), manager)[0].valid is True


class TestNonTransactional:
    def test_syntax_check_with_sqlglot(self) -> None:
        pytest.importorskip("sqlglot")
        results = validate_plan_views(_plan("mysql", [("ok", "SELECT a FROM t"), ("bad", "SELECT (a FROM t")]))
        assert [(r.view, r.valid, r.method) for r in results] == [("ok", True, "syntax"), ("bad", False, "syntax")]

    def test_target_is_ignored(self) -> None:
        pytest.importorskip("sqlglot")
        assert validate_plan_views(_plan("oracle", [("v", "SELECT 1 FROM dual")]), object())[0].method == "syntax"

    def test_without_sqlglot_nothing_is_validated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(validation, "sqlglot_available", lambda: False)
        [result] = validate_plan_views(_plan("mariadb", [("v", "SELECT 1"), ("empty", "")]))
        assert result == ViewValidationResult(view="v", valid=None, method="none", error=result.error)
        assert result.error and "sqlglot" in result.error


def test_migration_plan_validate_views_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    from util_bbdd.migrate.ir.models import MigrationPlan

    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(validation, "validate_plan_views", lambda *a, **k: calls.append((a, k)) or ["ok"])
    plan = MigrationPlan.__new__(MigrationPlan)
    assert plan.validate_views("conn", include_tables=False) == ["ok"]
    assert calls == [((plan, "conn"), {"include_tables": False})]
