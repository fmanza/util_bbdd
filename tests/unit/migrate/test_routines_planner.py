"""Tests para la integración de routines en MigrationPlanner._build_plan()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from util_bbdd.migrate import MigrationPlanner
from util_bbdd.migrate.ir.models import CanonicalRoutine, MigrationWarning

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _mock_oracle_manager_with_routines(
    routine_rows: list[tuple] | None = None,
    body_rows: list[tuple] | None = None,
) -> MagicMock:
    """Manager Oracle que devuelve tablas vacías y routines configurables."""
    manager = MagicMock()
    routine_rows = routine_rows or []
    body_rows = body_rows or []

    def side_effect(sql: str, params: dict):  # type: ignore[no-untyped-def]
        s = sql.lower()
        if "all_objects" in s and "routine" in s.lower():
            return iter(routine_rows)
        if "all_source" in s:
            return iter(body_rows)
        if "all_tables" in s:
            return iter([])
        if "all_tab_columns" in s:
            return iter([])
        return iter([])

    manager.execute_custom_many.side_effect = side_effect
    return manager


def _canonical_routine(name: str = "SP_TEST") -> CanonicalRoutine:
    return CanonicalRoutine(
        name=name,
        original_name=name,
        schema="MY_SCHEMA",
        routine_type="PROCEDURE",
        body="BEGIN\n  NULL;\nEND;",
        return_type="",
        comment="",
        warnings=[],
    )


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestPlannerRoutinesIntegration:
    def test_plan_includes_empty_routines_when_no_routines(self) -> None:
        """_build_plan() siempre incluye el campo routines aunque esté vacío."""
        extractor = MagicMock()
        extractor.extract_tables.return_value = []
        extractor.extract_views.return_value = []
        extractor.extract_routines.return_value = []

        with patch("util_bbdd.migrate.planner.OracleSchemaExtractor", return_value=extractor):
            planner = MigrationPlanner(source_engine="oracle", target_engine="mariadb")
            plan = planner.plan(MagicMock(), schema="MY_SCHEMA")

        assert hasattr(plan, "routines")
        assert plan.routines == []

    def test_plan_includes_routines_when_extractor_returns_them(self) -> None:
        """_build_plan() incluye routines extraídas por el extractor."""
        extractor = MagicMock()
        extractor.extract_tables.return_value = []
        extractor.extract_views.return_value = []
        extractor.extract_routines.return_value = [_canonical_routine("SP_ONE")]

        with patch("util_bbdd.migrate.planner.OracleSchemaExtractor", return_value=extractor):
            planner = MigrationPlanner(source_engine="oracle", target_engine="mariadb")
            plan = planner.plan(MagicMock(), schema="MY_SCHEMA")

        assert len(plan.routines) == 1
        assert plan.routines[0].name == "SP_ONE"

    def test_transform_routines_generates_review_warning(self) -> None:
        """transform_routines() debe añadir MigrationWarning de revisión manual."""
        extractor = MagicMock()
        extractor.extract_tables.return_value = []
        extractor.extract_views.return_value = []
        r = _canonical_routine("SP_WARN")
        extractor.extract_routines.return_value = [r]

        with patch("util_bbdd.migrate.planner.OracleSchemaExtractor", return_value=extractor):
            planner = MigrationPlanner(source_engine="oracle", target_engine="mariadb")
            plan = planner.plan(MagicMock(), schema="MY_SCHEMA")

        assert len(plan.routines) == 1
        # El transformer añade un MigrationWarning de revisión manual
        assert any("manual" in w.message.lower() for w in plan.routines[0].warnings)

    def test_plan_warnings_include_routine_warnings(self) -> None:
        """Las warnings de routines se propagan a plan.warnings."""
        extractor = MagicMock()
        extractor.extract_tables.return_value = []
        extractor.extract_views.return_value = []
        w = MigrationWarning(
            table="SP_BAD",
            column=None,
            category="ROUTINE",
            target_type="(no body)",
            message="Body no disponible.",
            severity="WARNING",
        )
        r = CanonicalRoutine(
            name="SP_BAD",
            original_name="SP_BAD",
            schema="MY_SCHEMA",
            routine_type="PROCEDURE",
            body="",
            return_type="",
            comment="",
            warnings=[w],
        )
        extractor.extract_routines.return_value = [r]

        with patch("util_bbdd.migrate.planner.OracleSchemaExtractor", return_value=extractor):
            planner = MigrationPlanner(source_engine="oracle", target_engine="mariadb")
            plan = planner.plan(MagicMock(), schema="MY_SCHEMA")

        assert any("Body no disponible" in pw.message for pw in plan.warnings)

    def test_plan_from_mariadb_includes_routines(self) -> None:
        """plan_from_mariadb() también pasa routines al plan."""
        extractor = MagicMock()
        extractor.extract_tables.return_value = []
        extractor.extract_views.return_value = []
        extractor.extract_routines.return_value = [_canonical_routine("FN_TEST")]

        with patch("util_bbdd.migrate.planner.MariaDBSchemaExtractor", return_value=extractor):
            planner = MigrationPlanner(source_engine="mariadb", target_engine="postgresql")
            plan = planner.plan(MagicMock(), schema="db1")

        assert len(plan.routines) == 1

    def test_plan_emit_ddl_with_routines(self) -> None:
        """emit_ddl() incluye el DDL de routines al final del script."""
        extractor = MagicMock()
        extractor.extract_tables.return_value = []
        extractor.extract_views.return_value = []
        extractor.extract_routines.return_value = [_canonical_routine()]

        with patch("util_bbdd.migrate.planner.OracleSchemaExtractor", return_value=extractor):
            planner = MigrationPlanner(source_engine="oracle", target_engine="mariadb")
            plan = planner.plan(MagicMock(), schema="MY_SCHEMA")

        ddl = plan.emit_ddl()
        # La routine tiene body: aparece en el script, comentada (hotfix R4: Oracle → MariaDB no puede crearla)
        assert "-- BEGIN" in ddl
        assert "NULL" in ddl
        assert plan.emit_statements() and not any(
            line.strip() and not line.strip().startswith("--")
            for stmt in plan.emit_statements()
            for line in stmt.splitlines()
        ), "execute() no debe enviar la rutina"
