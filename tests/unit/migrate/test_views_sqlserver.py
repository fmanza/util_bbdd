"""Tests para migración de vistas Oracle → SQL Server."""

from __future__ import annotations

from util_bbdd.migrate.emitters.sqlserver import SQLServerDDLEmitter
from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalTable, CanonicalView, MigrationWarning
from util_bbdd.migrate.transformers._view_rewriter import rewrite_oracle_view
from util_bbdd.migrate.transformers.oracle_to_sqlserver import OracleToSQLServerTransformer

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _view(
    name: str = "VW_TEST",
    query: str = "SELECT 1",
    comment: str = "",
    warnings: list[MigrationWarning] | None = None,
) -> CanonicalView:
    return CanonicalView(
        name=name,
        original_name=name,
        schema="MY_SCHEMA",
        query=query,
        columns=[],
        comment=comment,
        warnings=warnings or [],
    )


def _table(name: str = "T") -> CanonicalTable:
    col = CanonicalColumn(
        name="ID",
        original_name="ID",
        oracle_type="NUMBER",
        target_type="INT",
        nullable=False,
        default=None,
        comment="",
        ordinal=1,
    )
    return CanonicalTable(
        name=name,
        original_name=name,
        schema="S",
        columns=[col],
        primary_key=["ID"],
        indexes=[],
        foreign_keys=[],
        comment="",
        warnings=[],
    )


def _emitter() -> SQLServerDDLEmitter:
    return SQLServerDDLEmitter()


# ─── Tests: rewrite_oracle_view para SQL Server ───────────────────────────────


class TestRewriteOracleViewSQLServer:
    def _rw(self, query: str) -> CanonicalView:
        v = _view(query=query)
        return rewrite_oracle_view(
            v, sysdate_fn="GETDATE()", systimestamp_fn="SYSDATETIME()", user_fn="SYSTEM_USER", schema="MY_SCHEMA"
        )

    def test_sysdate_to_getdate(self) -> None:
        result = self._rw("SELECT SYSDATE FROM t")
        assert "GETDATE()" in result.query
        assert "SYSDATE" not in result.query

    def test_systimestamp_to_sysdatetime(self) -> None:
        result = self._rw("SELECT SYSTIMESTAMP FROM t")
        assert "SYSDATETIME()" in result.query

    def test_user_to_system_user(self) -> None:
        result = self._rw("SELECT USER FROM DUAL")
        assert "SYSTEM_USER" in result.query

    def test_nvl_to_coalesce(self) -> None:
        result = self._rw("SELECT NVL(a, 0) FROM t")
        assert "COALESCE(" in result.query

    def test_from_dual_removed(self) -> None:
        result = self._rw("SELECT GETDATE() FROM DUAL")
        assert "DUAL" not in result.query

    def test_hint_stripped(self) -> None:
        result = self._rw("SELECT /*+ INDEX(t idx) */ id FROM t")
        assert "/*+" not in result.query


# ─── Tests: transform_views ───────────────────────────────────────────────────


class TestOracleToSQLServerTransformViews:
    def setup_method(self) -> None:
        self.transformer = OracleToSQLServerTransformer()

    def test_returns_correct_count(self) -> None:
        views = [_view("V1"), _view("V2"), _view("V3")]
        assert len(self.transformer.transform_views(views)) == 3

    def test_sysdate_rewritten_to_getdate(self) -> None:
        views = [_view(query="SELECT SYSDATE FROM t")]
        result = self.transformer.transform_views(views)
        assert "GETDATE()" in result[0].query

    def test_long_name_truncated_at_128(self) -> None:
        long_name = "VW_" + "X" * 130
        views = [_view(name=long_name)]
        result = self.transformer.transform_views(views)
        assert len(result[0].name) <= 128
        assert any(w.oracle_type == "IDENTIFIER" for w in result[0].warnings)

    def test_empty_list(self) -> None:
        assert self.transformer.transform_views([]) == []


# ─── Tests: _emit_create_view ─────────────────────────────────────────────────


class TestSQLServerEmitCreateView:
    def setup_method(self) -> None:
        self.emitter = _emitter()

    def test_create_or_alter_view(self) -> None:
        v = _view(query="SELECT id FROM employees")
        ddl = self.emitter._emit_create_view(v)
        assert "CREATE OR ALTER VIEW [VW_TEST] AS" in ddl
        assert "SELECT id FROM employees" in ddl

    def test_bracket_escaping(self) -> None:
        v = _view(name="my view", query="SELECT 1")
        ddl = self.emitter._emit_create_view(v)
        assert "[my view]" in ddl

    def test_bracket_escaping_special_chars(self) -> None:
        v = _view(name="view]name", query="SELECT 1")
        ddl = self.emitter._emit_create_view(v)
        assert "[view]]name]" in ddl

    def test_comment_emitted(self) -> None:
        v = _view(comment="Vista de empleados")
        ddl = self.emitter._emit_create_view(v)
        assert "-- COMMENT: Vista de empleados" in ddl

    def test_manual_review_note_when_warnings(self) -> None:
        w = MigrationWarning(
            table="VW_TEST",
            column=None,
            oracle_type="ROWNUM",
            target_type="(revisión manual)",
            message="x",
            severity="WARNING",
        )
        v = _view(warnings=[w])
        ddl = self.emitter._emit_create_view(v)
        assert "-- NOTE: requires manual review" in ddl

    def test_no_note_without_warnings(self) -> None:
        v = _view()
        ddl = self.emitter._emit_create_view(v)
        assert "-- NOTE:" not in ddl


# ─── Tests: emit_statements con vistas ────────────────────────────────────────


class TestSQLServerEmitStatementsWithViews:
    def setup_method(self) -> None:
        self.emitter = _emitter()

    def test_views_after_tables(self) -> None:
        tables = [_table("EMP")]
        views = [_view("VW_EMP", "SELECT id FROM EMP")]
        stmts = self.emitter.emit_statements(tables, views)
        table_idx = next(i for i, s in enumerate(stmts) if "CREATE TABLE" in s)
        view_idx = next(i for i, s in enumerate(stmts) if "CREATE OR ALTER VIEW" in s)
        assert view_idx > table_idx

    def test_empty_query_view_skipped(self) -> None:
        stmts = self.emitter.emit_statements([], [_view(query="")])
        assert not any("CREATE OR ALTER VIEW" in s for s in stmts)

    def test_no_views_param_backward_compat(self) -> None:
        stmts = self.emitter.emit_statements([_table()])
        assert not any("CREATE OR ALTER VIEW" in s for s in stmts)

    def test_emit_includes_views(self) -> None:
        ddl = self.emitter.emit([_table()], [_view("VW_X", "SELECT 1")])
        assert "CREATE OR ALTER VIEW [VW_X]" in ddl
        assert ddl.endswith(";\n")
