"""Tests para _emit_create_routine() y emit() con routines en PostgreSQL."""

from __future__ import annotations

from util_bbdd.migrate.emitters.postgresql import PostgreSQLDDLEmitter
from util_bbdd.migrate.ir.models import CanonicalRoutine, MigrationWarning


def _emitter() -> PostgreSQLDDLEmitter:
    return PostgreSQLDDLEmitter()


def _routine(
    name: str = "sp_test",
    routine_type: str = "PROCEDURE",
    body: str = "BEGIN\n  PERFORM 1;\nEND;",
    return_type: str = "",
    is_package_member: bool = False,
    package_name: str | None = None,
    warnings: list[MigrationWarning] | None = None,
) -> CanonicalRoutine:
    return CanonicalRoutine(
        name=name,
        original_name=name,
        schema="my_schema",
        routine_type=routine_type,
        body=body,
        return_type=return_type,
        comment="",
        warnings=warnings or [],
        is_package_member=is_package_member,
        package_name=package_name,
    )


class TestPostgreSQLRoutineEmitter:
    def test_emit_procedure_with_body(self) -> None:
        ddl = _emitter().emit(tables=[], routines=[_routine()])
        assert "PERFORM 1" in ddl

    def test_stub_when_no_body(self) -> None:
        r = _routine(body="")
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "TODO" in ddl
        assert "body not available" in ddl

    def test_package_member_includes_header_comment(self) -> None:
        r = _routine(is_package_member=True, package_name="PKG_UTIL", name="sp_foo")
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "PACKAGE MEMBER" in ddl
        assert "PKG_UTIL" in ddl
        assert "manual migration required" in ddl

    def test_package_member_body_included_after_header(self) -> None:
        """El cuerpo de la rutina debe aparecer después del comentario de cabecera."""
        body = "BEGIN\n  PERFORM 'hello';\nEND"
        r = _routine(is_package_member=True, package_name="PKG_UTIL", name="sp_foo", body=body)
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "PACKAGE MEMBER" in ddl
        assert "PKG_UTIL" in ddl
        assert "hello" in ddl

    def test_package_member_stub_when_no_body(self) -> None:
        """Sin body, muestra stub TODO aunque sea package member."""
        r = _routine(is_package_member=True, package_name="PKG_UTIL", name="sp_empty", body="")
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "PACKAGE MEMBER" in ddl
        assert "TODO" in ddl

    def test_emit_without_routines_backward_compat(self) -> None:
        ddl = _emitter().emit(tables=[])
        assert isinstance(ddl, str)

    def test_emit_statements_includes_routine(self) -> None:
        r = _routine()
        stmts = _emitter().emit_statements(tables=[], routines=[r])
        combined = "\n".join(stmts)
        assert "PERFORM 1" in combined

    def test_multiple_routines_emitted(self) -> None:
        routines = [_routine("sp_a"), _routine("sp_b")]
        stmts = _emitter().emit_statements(tables=[], routines=routines)
        assert len([s for s in stmts if "PERFORM 1" in s]) == 2

    def test_routine_type_and_name_header_procedure(self) -> None:
        ddl = _emitter().emit(tables=[], routines=[_routine(name="sp_test", routine_type="PROCEDURE")])
        assert '-- PROCEDURE: "sp_test"' in ddl

    def test_routine_type_and_name_header_function(self) -> None:
        r = _routine(name="fn_calc", routine_type="FUNCTION", body="BEGIN\n  RETURN 1;\nEND;")
        ddl = _emitter().emit(tables=[], routines=[r])
        assert '-- FUNCTION: "fn_calc"' in ddl

    def test_routine_header_present_even_without_warnings(self) -> None:
        r = _routine(name="sp_nowarns", warnings=[])
        ddl = _emitter().emit(tables=[], routines=[r])
        assert '-- PROCEDURE: "sp_nowarns"' in ddl
