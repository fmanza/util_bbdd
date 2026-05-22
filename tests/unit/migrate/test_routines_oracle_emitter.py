"""Tests para _emit_create_routine() y emit() con routines en Oracle."""

from __future__ import annotations

from util_bbdd.migrate.emitters.oracle import OracleDDLEmitter
from util_bbdd.migrate.ir.models import CanonicalRoutine, MigrationWarning


def _emitter() -> OracleDDLEmitter:
    return OracleDDLEmitter()


def _routine(
    name: str = "SP_TEST",
    routine_type: str = "PROCEDURE",
    body: str = "PROCEDURE SP_TEST AS\nBEGIN\n  NULL;\nEND;",
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


class TestOracleRoutineEmitter:
    def test_emit_procedure_prepends_create_or_replace(self) -> None:
        ddl = _emitter().emit(tables=[], routines=[_routine()])
        assert "CREATE OR REPLACE" in ddl
        assert "PROCEDURE SP_TEST" in ddl

    def test_stub_when_no_body(self) -> None:
        r = _routine(body="")
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "TODO" in ddl
        assert "body not available" in ddl

    def test_package_member_emits_comment_only(self) -> None:
        r = _routine(is_package_member=True, package_name="PKG_UTIL", name="SP_FOO")
        ddl = _emitter().emit(tables=[], routines=[r])
        assert "PACKAGE MEMBER" in ddl
        assert "PKG_UTIL" in ddl
        lines_without_comment = [l for l in ddl.splitlines() if not l.strip().startswith("--")]
        assert not any("CREATE" in l for l in lines_without_comment)

    def test_emit_without_routines_backward_compat(self) -> None:
        ddl = _emitter().emit(tables=[])
        assert isinstance(ddl, str)

    def test_emit_statements_includes_routine(self) -> None:
        r = _routine()
        stmts = _emitter().emit_statements(tables=[], routines=[r])
        combined = "\n".join(stmts)
        assert "CREATE OR REPLACE" in combined

    def test_multiple_routines_emitted(self) -> None:
        routines = [_routine("SP_A"), _routine("SP_B")]
        stmts = _emitter().emit_statements(tables=[], routines=routines)
        combined = "\n".join(stmts)
        assert combined.count("CREATE OR REPLACE") == 2
