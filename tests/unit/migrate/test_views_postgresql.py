"""Tests para migración de vistas Oracle → PostgreSQL."""

from __future__ import annotations

from util_bbdd.migrate.emitters.postgresql import PostgreSQLDDLEmitter
from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalTable, CanonicalView, MigrationWarning
from util_bbdd.migrate.transformers._view_rewriter import rewrite_oracle_view
from util_bbdd.migrate.transformers.oracle_to_postgresql import OracleToPostgreSQLTransformer

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
        target_type="INTEGER",
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


def _emitter(pg_schema: str | None = None) -> PostgreSQLDDLEmitter:
    return PostgreSQLDDLEmitter(pg_schema=pg_schema)


# ─── Tests: rewrite_oracle_view para PostgreSQL ───────────────────────────────


class TestRewriteOracleViewPostgreSQL:
    def _rw(self, query: str) -> CanonicalView:
        v = _view(query=query)
        return rewrite_oracle_view(
            v, sysdate_fn="NOW()", systimestamp_fn="NOW()", user_fn="CURRENT_USER", schema="MY_SCHEMA"
        )

    def test_sysdate_to_now(self) -> None:
        result = self._rw("SELECT SYSDATE FROM t")
        assert "NOW()" in result.query
        assert "SYSDATE" not in result.query

    def test_user_to_current_user(self) -> None:
        result = self._rw("SELECT USER FROM DUAL")
        assert "CURRENT_USER" in result.query

    def test_nvl_to_coalesce(self) -> None:
        result = self._rw("SELECT NVL(col, 'N/A') FROM t")
        assert "COALESCE(" in result.query

    def test_from_dual_removed(self) -> None:
        result = self._rw("SELECT NOW() FROM DUAL")
        assert "DUAL" not in result.query

    def test_hint_stripped(self) -> None:
        result = self._rw("SELECT /*+ PARALLEL(t, 4) */ id FROM t")
        assert "/*+" not in result.query
        assert "PARALLEL" not in result.query

    def test_listagg_generates_warning(self) -> None:
        result = self._rw("SELECT LISTAGG(name, ',') WITHIN GROUP (ORDER BY id) FROM t")
        labels = [w.oracle_type for w in result.warnings]
        assert "LISTAGG" in labels

    def test_start_with_generates_warning(self) -> None:
        result = self._rw("SELECT id FROM t START WITH parent_id IS NULL CONNECT BY PRIOR id = parent_id")
        labels = [w.oracle_type for w in result.warnings]
        assert "START WITH" in labels
        assert "CONNECT BY" in labels


# ─── Tests: transform_views ───────────────────────────────────────────────────


class TestOracleToPostgreSQLTransformViews:
    def setup_method(self) -> None:
        self.transformer = OracleToPostgreSQLTransformer()

    def test_returns_correct_count(self) -> None:
        views = [_view("V1"), _view("V2")]
        assert len(self.transformer.transform_views(views)) == 2

    def test_sysdate_rewritten_to_now(self) -> None:
        views = [_view(query="SELECT SYSDATE FROM t")]
        result = self.transformer.transform_views(views)
        assert "NOW()" in result[0].query

    def test_long_name_truncated_at_63(self) -> None:
        long_name = "VW_" + "X" * 65
        views = [_view(name=long_name)]
        result = self.transformer.transform_views(views)
        assert len(result[0].name) <= 63
        assert any(w.oracle_type == "IDENTIFIER" for w in result[0].warnings)

    def test_empty_list(self) -> None:
        assert self.transformer.transform_views([]) == []


# ─── Tests: _emit_create_view ─────────────────────────────────────────────────


class TestPostgreSQLEmitCreateView:
    def setup_method(self) -> None:
        self.emitter = _emitter()

    def test_create_or_replace_view(self) -> None:
        v = _view(query="SELECT id FROM employees")
        ddl = self.emitter._emit_create_view(v)
        assert 'CREATE OR REPLACE VIEW "VW_TEST" AS' in ddl
        assert "SELECT id FROM employees" in ddl

    def test_double_quote_escaping(self) -> None:
        v = _view(name='my"view', query="SELECT 1")
        ddl = self.emitter._emit_create_view(v)
        assert '"my""view"' in ddl

    def test_comment_emitted(self) -> None:
        v = _view(comment="Vista de pedidos")
        ddl = self.emitter._emit_create_view(v)
        assert "-- COMMENT: Vista de pedidos" in ddl

    def test_manual_review_note_when_warnings(self) -> None:
        w = MigrationWarning(
            table="VW_TEST",
            column=None,
            oracle_type="CONNECT BY",
            target_type="(revisión manual)",
            message="x",
            severity="WARNING",
        )
        v = _view(warnings=[w])
        ddl = self.emitter._emit_create_view(v)
        assert "-- NOTE: requires manual review" in ddl

    def test_no_note_without_warnings(self) -> None:
        v = _view()
        assert "-- NOTE:" not in self.emitter._emit_create_view(v)


# ─── Tests: emit_statements con vistas ────────────────────────────────────────


class TestPostgreSQLEmitStatementsWithViews:
    def setup_method(self) -> None:
        self.emitter = _emitter()

    def test_views_after_tables(self) -> None:
        tables = [_table("EMP")]
        views = [_view("VW_EMP", "SELECT id FROM EMP")]
        stmts = self.emitter.emit_statements(tables, views)
        table_idx = next(i for i, s in enumerate(stmts) if "CREATE TABLE" in s)
        view_idx = next(i for i, s in enumerate(stmts) if "CREATE OR REPLACE VIEW" in s)
        assert view_idx > table_idx

    def test_views_after_search_path(self) -> None:
        emitter = _emitter(pg_schema="myschema")
        stmts = emitter.emit_statements([_table()], [_view("VW", "SELECT 1")])
        search_path_idx = next(i for i, s in enumerate(stmts) if "search_path" in s)
        view_idx = next(i for i, s in enumerate(stmts) if "CREATE OR REPLACE VIEW" in s)
        assert view_idx > search_path_idx

    def test_empty_query_view_skipped(self) -> None:
        stmts = self.emitter.emit_statements([], [_view(query="")])
        assert not any("CREATE OR REPLACE VIEW" in s for s in stmts)

    def test_no_views_param_backward_compat(self) -> None:
        stmts = self.emitter.emit_statements([_table()])
        assert not any("CREATE OR REPLACE VIEW" in s for s in stmts)

    def test_emit_includes_views(self) -> None:
        ddl = self.emitter.emit([_table()], [_view("VW_X", "SELECT 1")])
        assert 'CREATE OR REPLACE VIEW "VW_X"' in ddl
        assert ddl.endswith(";\n")

    def test_multiple_views_all_emitted(self) -> None:
        views = [_view("V1", "SELECT 1"), _view("V2", "SELECT 2")]
        stmts = self.emitter.emit_statements([], views)
        view_stmts = [s for s in stmts if "CREATE OR REPLACE VIEW" in s]
        assert len(view_stmts) == 2

    def test_dependent_view_emitted_after_base(self) -> None:
        v_base = _view("VW_BASE", "SELECT id FROM employees")
        v_top = _view("VW_TOP", "SELECT * FROM VW_BASE WHERE id > 0")
        stmts = self.emitter.emit_statements([], [v_top, v_base])
        view_stmts = [s for s in stmts if "CREATE OR REPLACE VIEW" in s]
        base_idx = next(i for i, s in enumerate(view_stmts) if "VW_BASE" in s)
        top_idx = next(i for i, s in enumerate(view_stmts) if "VW_TOP" in s)
        assert base_idx < top_idx

    def test_circular_views_get_aviso_comment(self) -> None:
        va = _view("VA", "SELECT * FROM VB")
        vb = _view("VB", "SELECT * FROM VA")
        stmts = self.emitter.emit_statements([], [va, vb])
        assert any("dependencia circular" in s for s in stmts)
