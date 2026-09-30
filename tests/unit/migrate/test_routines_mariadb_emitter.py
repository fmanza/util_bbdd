"""Tests para _emit_create_routine() y emit() con routines en MariaDB."""

from __future__ import annotations

from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter
from util_bbdd.migrate.ir.models import CanonicalRoutine, MigrationWarning


def _emitter() -> MariaDBDDLEmitter:
    return MariaDBDDLEmitter(charset="utf8mb4", collation="utf8mb4_unicode_ci")


def _routine(
    name: str = "SP_TEST",
    routine_type: str = "PROCEDURE",
    body: str = "BEGIN\n  SELECT 1;\nEND",
    return_type: str = "",
    is_package_member: bool = False,
    package_name: str | None = None,
    warnings: list[MigrationWarning] | None = None,
) -> CanonicalRoutine:
    return CanonicalRoutine(
        name=name,
        original_name=name,
        schema="MY_SCHEMA",
        routine_type=routine_type,
        body=body,
        return_type=return_type,
        comment="",
        warnings=warnings or [],
        is_package_member=is_package_member,
        package_name=package_name,
    )


class TestMariaDBRoutineEmitter:
    def test_emit_procedure_with_body(self) -> None:
        ddl = _emitter().emit(tables=[], routines=[_routine()])
        assert "BEGIN" in ddl
        assert "SELECT 1" in ddl

    def test_emit_function_with_return_type(self) -> None:
        r = _routine(name="FN_CALC", routine_type="FUNCTION", return_type="INT", body="BEGIN\n  RETURN 42;\nEND")
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "RETURN 42" in ddl

    def test_stub_when_no_body(self) -> None:
        r = _routine(body="")
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "TODO" in ddl
        assert "body not available" in ddl

    def test_package_member_includes_header_comment(self) -> None:
        r = _routine(is_package_member=True, package_name="PKG_UTIL", name="SP_FOO")
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "PACKAGE MEMBER" in ddl
        assert "PKG_UTIL" in ddl
        assert "manual migration required" in ddl

    def test_package_member_body_included_after_header(self) -> None:
        """El cuerpo de la rutina debe aparecer después del comentario de cabecera."""
        body = "BEGIN\n  SELECT 'hello';\nEND"
        r = _routine(is_package_member=True, package_name="PKG_UTIL", name="SP_FOO", body=body)
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "PACKAGE MEMBER" in ddl
        assert "PKG_UTIL" in ddl
        assert "hello" in ddl

    def test_package_member_stub_when_no_body(self) -> None:
        """Sin body, muestra stub TODO aunque sea package member."""
        r = _routine(is_package_member=True, package_name="PKG_UTIL", name="SP_EMPTY", body="")
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "PACKAGE MEMBER" in ddl
        assert "TODO" in ddl

    def test_emit_without_routines_backward_compat(self) -> None:
        # emit() sin routines no debe fallar
        ddl = _emitter().emit(tables=[])
        assert isinstance(ddl, str)

    def test_emit_statements_includes_routine(self) -> None:
        r = _routine()
        stmts = _emitter().emit_statements(tables=[], routines=[r])
        combined = "\n".join(stmts)
        assert "BEGIN" in combined

    def test_warning_in_routine_appears_as_comment(self) -> None:
        """El emitter emite un header genérico; las warnings individuales van a plan.warnings."""
        w = MigrationWarning(
            table="SP_TEST",
            column=None,
            category="ROUTINE",
            target_type="PROCEDURE",
            message="Revisar body manualmente.",
            severity="WARNING",
        )
        r = _routine(warnings=[w])
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "manual review" in ddl

    def test_multiple_routines_emitted(self) -> None:
        routines = [_routine("SP_A"), _routine("SP_B")]
        stmts = _emitter().emit_statements(tables=[], routines=routines)
        assert len([s for s in stmts if "BEGIN" in s]) == 2

    def test_routine_type_and_name_header_procedure(self) -> None:
        ddl = _emitter().emit(tables=[], routines=[_routine(name="SP_TEST", routine_type="PROCEDURE")])
        assert "-- PROCEDURE: `SP_TEST`" in ddl

    def test_routine_type_and_name_header_function(self) -> None:
        r = _routine(name="FN_CALC", routine_type="FUNCTION", body="BEGIN\n  RETURN 1;\nEND")
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "-- FUNCTION: `FN_CALC`" in ddl

    def test_routine_header_present_even_without_warnings(self) -> None:
        r = _routine(name="SP_NOWARNS", warnings=[])
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "-- PROCEDURE: `SP_NOWARNS`" in ddl
