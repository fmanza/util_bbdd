"""Tests para reporters de plan de migración (text y markdown)."""

from __future__ import annotations

from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter
from util_bbdd.migrate.ir.models import (
    CanonicalRoutine,
    MigrationPlan,
    MigrationWarning,
)
from util_bbdd.migrate.reporters.markdown import format_plan_markdown
from util_bbdd.migrate.reporters.text import format_plan_text

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _emitter() -> MariaDBDDLEmitter:
    return MariaDBDDLEmitter(charset="utf8mb4", collation="utf8mb4_unicode_ci")


def _routine(
    name: str = "SP_TEST",
    routine_type: str = "PROCEDURE",
    body: str = "BEGIN\n  SELECT 1;\nEND",
    comment: str = "",
    warnings: list[MigrationWarning] | None = None,
    is_package_member: bool = False,
    package_name: str | None = None,
) -> CanonicalRoutine:
    return CanonicalRoutine(
        name=name,
        original_name=name,
        schema="SCHEMA",
        routine_type=routine_type,
        body=body,
        return_type="",
        comment=comment,
        warnings=warnings or [],
        is_package_member=is_package_member,
        package_name=package_name,
    )


def _plan(routines: list[CanonicalRoutine] | None = None) -> MigrationPlan:
    return MigrationPlan(
        tables=[],
        warnings=[],
        source_schema="SRC",
        source_engine="oracle",
        target_engine="mariadb",
        emitter=_emitter(),
        routines=routines or [],
    )


# ─── Markdown reporter ────────────────────────────────────────────────────────


class TestMarkdownReporterRoutines:
    def test_no_routines_no_section(self) -> None:
        result = format_plan_markdown(_plan())
        assert "## Rutinas (PROCEDURE/FUNCTION)" not in result

    def test_routines_count_in_header(self) -> None:
        plan = _plan([_routine()])
        result = format_plan_markdown(plan)
        assert "**Rutinas**: 1" in result

    def test_routines_section_heading(self) -> None:
        plan = _plan([_routine()])
        result = format_plan_markdown(plan)
        assert "## Rutinas (PROCEDURE/FUNCTION)" in result

    def test_routine_name_and_type(self) -> None:
        plan = _plan([_routine(name="GET_USER", routine_type="FUNCTION")])
        result = format_plan_markdown(plan)
        assert "### `GET_USER` (FUNCTION)" in result

    def test_routine_body_shown_in_code_block(self) -> None:
        body = "BEGIN\n  SELECT 1;\nEND"
        plan = _plan([_routine(body=body)])
        result = format_plan_markdown(plan)
        assert "```sql" in result
        assert body in result
        assert "```" in result

    def test_routine_no_body_shows_unavailable_note(self) -> None:
        plan = _plan([_routine(body="")])
        result = format_plan_markdown(plan)
        assert "Código no disponible" in result
        assert "```sql" not in result

    def test_routine_with_warning_shows_review_note(self) -> None:
        w = MigrationWarning(
            table="SP_TEST",
            column=None,
            category="ROUTINE",
            target_type="PROCEDURE",
            message="Requires manual adaptation",
            severity="WARNING",
        )
        plan = _plan([_routine(warnings=[w])])
        result = format_plan_markdown(plan)
        assert "Requiere revisión manual" in result

    def test_routine_package_member_shows_package_note(self) -> None:
        # Sin body: package spec o miembro sin fuente disponible
        plan = _plan([_routine(is_package_member=True, package_name="PKG_UTILS", body="")])
        result = format_plan_markdown(plan)
        assert "Miembro de PACKAGE" in result
        assert "PKG_UTILS" in result
        assert "```sql" not in result

    def test_package_body_member_with_body_shows_code_block(self) -> None:
        body = "CREATE OR REPLACE PACKAGE BODY PKG_UTIL AS\nPROCEDURE P1 IS BEGIN NULL; END;\nEND PKG_UTIL;"
        plan = _plan([_routine(is_package_member=True, body=body)])
        result = format_plan_markdown(plan)
        assert "Miembro de PACKAGE" in result
        assert "```sql" in result
        assert body in result

    def test_routine_shows_source_info_markdown(self) -> None:
        plan = _plan([_routine()])
        result = format_plan_markdown(plan)
        assert "**Fuente**" in result
        assert "ORACLE" in result
        assert "SCHEMA" in result

    def test_routine_comment_shown(self) -> None:
        plan = _plan([_routine(comment="Obtiene el usuario por ID")])
        result = format_plan_markdown(plan)
        assert "Obtiene el usuario por ID" in result

    def test_multiple_routines_all_shown(self) -> None:
        routines = [
            _routine(name="SP_ONE", routine_type="PROCEDURE"),
            _routine(name="FN_TWO", routine_type="FUNCTION"),
        ]
        result = format_plan_markdown(_plan(routines))
        assert "SP_ONE" in result
        assert "FN_TWO" in result

    def test_manual_review_global_warning_note_present(self) -> None:
        plan = _plan([_routine()])
        result = format_plan_markdown(plan)
        assert "revisión manual" in result.lower()


# ─── Text reporter ────────────────────────────────────────────────────────────


class TestTextReporterRoutines:
    def test_no_routines_no_section(self) -> None:
        result = format_plan_text(_plan())
        assert "RUTINAS (PROCEDURE/FUNCTION):" not in result

    def test_routines_count_in_header(self) -> None:
        plan = _plan([_routine()])
        result = format_plan_text(plan)
        assert "Rutinas: 1" in result

    def test_routines_section_heading(self) -> None:
        plan = _plan([_routine()])
        result = format_plan_text(plan)
        assert "RUTINAS (PROCEDURE/FUNCTION):" in result

    def test_routine_name_and_type(self) -> None:
        plan = _plan([_routine(name="GET_USER", routine_type="FUNCTION")])
        result = format_plan_text(plan)
        assert "FUNCTION: GET_USER" in result

    def test_routine_body_shown(self) -> None:
        body = "BEGIN\n  SELECT 1;\nEND"
        plan = _plan([_routine(body=body)])
        result = format_plan_text(plan)
        assert "SELECT 1;" in result

    def test_routine_no_body_shows_unavailable_note(self) -> None:
        plan = _plan([_routine(body="")])
        result = format_plan_text(plan)
        assert "CÓDIGO NO DISPONIBLE" in result

    def test_routine_with_warning_shows_review_note(self) -> None:
        w = MigrationWarning(
            table="SP_TEST",
            column=None,
            category="ROUTINE",
            target_type="PROCEDURE",
            message="Requires manual adaptation",
            severity="WARNING",
        )
        plan = _plan([_routine(warnings=[w])])
        result = format_plan_text(plan)
        assert "REQUIERE REVISIÓN MANUAL" in result

    def test_routine_package_member_shows_package_note(self) -> None:
        plan = _plan([_routine(is_package_member=True, package_name="PKG_UTILS")])
        result = format_plan_text(plan)
        assert "PACKAGE MEMBER" in result
        assert "PKG_UTILS" in result

    def test_package_body_member_with_body_shown(self) -> None:
        body = "CREATE OR REPLACE PACKAGE BODY PKG_UTIL AS\n  PROCEDURE P1 IS BEGIN NULL; END;\nEND;"
        plan = _plan([_routine(is_package_member=True, body=body)])
        result = format_plan_text(plan)
        assert "PACKAGE MEMBER" in result
        assert "CREATE OR REPLACE PACKAGE BODY" in result

    def test_routine_shows_source_info_text(self) -> None:
        plan = _plan([_routine()])
        result = format_plan_text(plan)
        assert "Fuente:" in result
        assert "ORACLE" in result
        assert "SCHEMA" in result

    def test_routine_comment_shown(self) -> None:
        plan = _plan([_routine(comment="Obtiene el usuario")])
        result = format_plan_text(plan)
        assert "Obtiene el usuario" in result

    def test_multiple_routines_all_shown(self) -> None:
        routines = [
            _routine(name="SP_ONE", routine_type="PROCEDURE"),
            _routine(name="FN_TWO", routine_type="FUNCTION"),
        ]
        result = format_plan_text(_plan(routines))
        assert "SP_ONE" in result
        assert "FN_TWO" in result

    def test_body_lines_indented(self) -> None:
        plan = _plan([_routine(body="BEGIN\n  NULL;\nEND")])
        result = format_plan_text(plan)
        assert "  BEGIN" in result
