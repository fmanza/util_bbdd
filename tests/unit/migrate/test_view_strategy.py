"""``view_strategy`` de MigrationPlanner (V1, sesión 2026-09-29c-migrate-views): resolución y efecto en el plan."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.migrate import MigrationPlanner
from util_bbdd.migrate.views import _dialects
from util_bbdd.migrate.views._dialects import resolve_view_strategy

from ._snapshot_source import col, fake_manager, pk, table, view


class TestResolveViewStrategy:
    def test_auto_transpiles_when_sqlglot_is_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_dialects, "sqlglot_available", lambda: True)
        assert resolve_view_strategy("auto") == "transpile"

    def test_auto_falls_back_to_passthrough_without_sqlglot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_dialects, "sqlglot_available", lambda: False)
        assert resolve_view_strategy("auto") == "passthrough"

    def test_transpile_requires_sqlglot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_dialects, "sqlglot_available", lambda: False)
        with pytest.raises(ImportError, match="util_bbdd\\[migrate\\]"):
            resolve_view_strategy("transpile")

    def test_passthrough_never_needs_sqlglot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_dialects, "sqlglot_available", lambda: False)
        assert resolve_view_strategy("PassThrough") == "passthrough"

    def test_invalid_strategy(self) -> None:
        with pytest.raises(ValueError, match="view_strategy"):
            resolve_view_strategy("rewrite")

    def test_planner_validates_strategy(self) -> None:
        with pytest.raises(ValueError, match="view_strategy"):
            MigrationPlanner(source_engine="mysql", target_engine="postgresql", view_strategy="x")  # type: ignore[arg-type]


def _mysql_manager(view_sql: str) -> MagicMock:
    """Manager MySQL simulado: una tabla ``t(id, alta)`` y una vista ``v``."""
    return fake_manager(
        "mysql",
        table("t"),
        col("t", "id", 1, "int", nullable=False),
        col("t", "alta", 2, "date"),
        col("v", "id", 1, "int", nullable=False),
        pk("t", "id"),
        view("v", view_sql),
    )


class TestPlannerViewStrategy:
    SQL = "select `db1`.`t`.`id` AS `id`,(`db1`.`t`.`alta` + interval 30 day) AS `vence` from `db1`.`t`"

    def test_transpile_rewrites_view_for_target(self) -> None:
        pytest.importorskip("sqlglot")
        plan = MigrationPlanner(source_engine="mysql", target_engine="sqlserver", view_strategy="transpile").plan(
            _mysql_manager(self.SQL), "db1"
        )
        view = plan.views[0]
        assert "DATEADD(DAY, 30," in view.query
        assert "`" not in view.query and "db1" not in view.query
        assert any(w.target_type == "VIEW (reescrita)" and w.severity == "INFO" for w in view.warnings)

    def test_passthrough_keeps_source_sql(self) -> None:
        plan = MigrationPlanner(source_engine="mysql", target_engine="sqlserver", view_strategy="passthrough").plan(
            _mysql_manager(self.SQL), "db1"
        )
        assert plan.views[0].query == self.SQL
        assert not any(w.target_type == "VIEW (reescrita)" for w in plan.views[0].warnings)
