"""Tests para CanonicalRoutine IR y su integración en MigrationPlan."""

from __future__ import annotations

from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter
from util_bbdd.migrate.ir.models import (
    CanonicalRoutine,
    MigrationPlan,
    MigrationWarning,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _routine(
    name: str = "SP_TEST",
    routine_type: str = "PROCEDURE",
    body: str = "BEGIN\n  SELECT 1;\nEND",
    return_type: str = "",
    comment: str = "",
    warnings: list[MigrationWarning] | None = None,
    is_package_member: bool = False,
    package_name: str | None = None,
) -> CanonicalRoutine:
    return CanonicalRoutine(
        name=name,
        original_name=name,
        schema="MY_SCHEMA",
        routine_type=routine_type,
        body=body,
        return_type=return_type,
        comment=comment,
        warnings=warnings or [],
        is_package_member=is_package_member,
        package_name=package_name,
    )


def _plan_with_routines(routines: list[CanonicalRoutine]) -> MigrationPlan:
    emitter = MariaDBDDLEmitter(charset="utf8mb4", collation="utf8mb4_unicode_ci")
    return MigrationPlan(
        tables=[],
        warnings=[],
        source_schema="MY_SCHEMA",
        source_engine="oracle",
        target_engine="mariadb",
        emitter=emitter,
        routines=routines,
    )


# ─── Tests CanonicalRoutine ───────────────────────────────────────────────────


class TestCanonicalRoutineDefaults:
    def test_procedure_defaults(self) -> None:
        r = _routine()
        assert r.routine_type == "PROCEDURE"
        assert r.is_package_member is False
        assert r.package_name is None
        assert r.return_type == ""

    def test_function_return_type(self) -> None:
        r = _routine(name="FN_TEST", routine_type="FUNCTION", return_type="NUMBER")
        assert r.return_type == "NUMBER"

    def test_package_member(self) -> None:
        r = _routine(is_package_member=True, package_name="PKG_UTIL")
        assert r.is_package_member is True
        assert r.package_name == "PKG_UTIL"

    def test_warnings_mutable(self) -> None:
        r = _routine()
        r.warnings.append(
            MigrationWarning(
                table="SP_TEST",
                column=None,
                oracle_type="PROCEDURE",
                target_type="PROCEDURE",
                message="test",
                severity="INFO",
            )
        )
        assert len(r.warnings) == 1


# ─── Tests MigrationPlan con routines ────────────────────────────────────────


class TestMigrationPlanRoutines:
    def test_routines_default_empty(self) -> None:
        emitter = MariaDBDDLEmitter(charset="utf8mb4", collation="utf8mb4_unicode_ci")
        plan = MigrationPlan(
            tables=[],
            warnings=[],
            source_schema="S",
            source_engine="oracle",
            target_engine="mariadb",
            emitter=emitter,
        )
        assert plan.routines == []

    def test_emit_ddl_with_routines(self) -> None:
        plan = _plan_with_routines([_routine(body="BEGIN\n  SELECT 1;\nEND")])
        ddl = plan.emit_ddl()
        assert "BEGIN" in ddl
        assert "SELECT 1" in ddl

    def test_emit_ddl_empty_routines(self) -> None:
        plan = _plan_with_routines([])
        # Debe generarse sin error, aunque no haya tablas ni rutinas
        ddl = plan.emit_ddl()
        assert isinstance(ddl, str)

    def test_emit_statements_includes_routines(self) -> None:
        plan = _plan_with_routines([_routine(name="SP_ONE"), _routine(name="SP_TWO")])
        stmts = plan.emit_statements()
        bodies = "\n".join(stmts)
        assert "SP_ONE" not in bodies  # body verbatim, no el nombre wrapeado
        assert "BEGIN" in bodies

    def test_routine_stub_when_no_body(self) -> None:
        plan = _plan_with_routines([_routine(body="")])
        ddl = plan.emit_ddl()
        assert "TODO" in ddl
        assert "body not available" in ddl

    def test_package_member_emits_comment_only(self) -> None:
        r = _routine(is_package_member=True, package_name="PKG_UTIL", name="SP_FOO")
        plan = _plan_with_routines([r])
        ddl = plan.emit_ddl()
        assert "PACKAGE MEMBER" in ddl
        assert "PKG_UTIL" in ddl
        assert "manual migration required" in ddl
        assert "CREATE" not in ddl
