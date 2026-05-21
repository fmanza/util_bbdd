"""Tests para migración de vistas Oracle → MariaDB.

Cubre: reescritura SQL best-effort, _emit_create_view, emit_statements con vistas,
transform_views (identifier truncation), MigrationPlan.views backward-compat.
"""

from __future__ import annotations

from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter, _topological_sort_views
from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalTable,
    CanonicalView,
    MigrationPlan,
    MigrationWarning,
)
from util_bbdd.migrate.transformers._view_rewriter import rewrite_oracle_view
from util_bbdd.migrate.transformers.oracle_to_mariadb import OracleToMariaDBTransformer

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _view(
    name: str = "VW_TEST",
    query: str = "SELECT 1 FROM DUAL",
    columns: list[str] | None = None,
    comment: str = "",
    warnings: list[MigrationWarning] | None = None,
) -> CanonicalView:
    return CanonicalView(
        name=name,
        original_name=name,
        schema="MY_SCHEMA",
        query=query,
        columns=columns or [],
        comment=comment,
        warnings=warnings or [],
    )


def _table(name: str = "T") -> CanonicalTable:
    col = CanonicalColumn(
        name="ID",
        original_name="ID",
        oracle_type="NUMBER",
        target_type="INT(11)",
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


def _emitter() -> MariaDBDDLEmitter:
    return MariaDBDDLEmitter(charset="utf8mb4", collation="utf8mb4_unicode_ci")


# ─── Tests: rewrite_oracle_view ───────────────────────────────────────────────


class TestRewriteOracleViewMariaDB:
    def _rw(self, query: str, schema: str = "MY_SCHEMA") -> CanonicalView:
        v = _view(query=query)
        return rewrite_oracle_view(
            v, sysdate_fn="NOW()", systimestamp_fn="NOW()", user_fn="CURRENT_USER()", schema=schema
        )

    def test_sysdate_replaced(self) -> None:
        result = self._rw("SELECT SYSDATE FROM DUAL")
        assert "NOW()" in result.query
        assert "SYSDATE" not in result.query

    def test_systimestamp_replaced(self) -> None:
        result = self._rw("SELECT SYSTIMESTAMP FROM DUAL")
        assert "NOW()" in result.query
        assert "SYSTIMESTAMP" not in result.query

    def test_user_replaced(self) -> None:
        result = self._rw("SELECT USER FROM DUAL")
        assert "CURRENT_USER()" in result.query

    def test_user_replacement_emits_warning(self) -> None:
        """TEST-08: cuando USER es sustituido debe emitirse MigrationWarning con oracle_type='USER'."""
        result = self._rw("SELECT USER FROM DUAL")
        user_warnings = [w for w in result.warnings if w.oracle_type == "USER"]
        assert user_warnings, "Debe emitirse MigrationWarning cuando USER es sustituido"
        assert user_warnings[0].severity == "WARNING"

    def test_no_user_in_query_no_user_warning(self) -> None:
        """TEST-08: si la query no contiene USER no se emite MigrationWarning de USER."""
        result = self._rw("SELECT id, name FROM employees")
        user_warnings = [w for w in result.warnings if w.oracle_type == "USER"]
        assert not user_warnings

    def test_nvl_replaced(self) -> None:
        result = self._rw("SELECT NVL(col, 0) FROM t")
        assert "COALESCE(col, 0)" in result.query
        assert "NVL(" not in result.query

    def test_nvl_case_insensitive(self) -> None:
        result = self._rw("SELECT nvl(a, b) FROM t")
        assert "COALESCE(" in result.query

    def test_from_dual_removed(self) -> None:
        result = self._rw("SELECT 1 FROM DUAL")
        assert "DUAL" not in result.query
        assert "FROM" not in result.query

    def test_hint_stripped(self) -> None:
        result = self._rw("SELECT /*+ FULL(t) */ id FROM t")
        assert "/*+" not in result.query
        assert "FULL(t)" not in result.query

    def test_schema_prefix_stripped(self) -> None:
        result = self._rw("SELECT MY_SCHEMA.EMPLOYEES.id FROM MY_SCHEMA.EMPLOYEES", schema="MY_SCHEMA")
        assert "MY_SCHEMA." not in result.query

    def test_schema_prefix_case_insensitive(self) -> None:
        result = self._rw("SELECT my_schema.t.id FROM my_schema.t", schema="MY_SCHEMA")
        assert "my_schema." not in result.query

    def test_rownum_generates_warning(self) -> None:
        result = self._rw("SELECT id FROM t WHERE ROWNUM <= 10")
        warning_labels = [w.oracle_type for w in result.warnings]
        assert "ROWNUM" in warning_labels
        assert result.warnings[0].severity == "WARNING"

    def test_connect_by_generates_warning(self) -> None:
        result = self._rw("SELECT id FROM t CONNECT BY PRIOR id = parent_id")
        labels = [w.oracle_type for w in result.warnings]
        assert "CONNECT BY" in labels

    def test_outer_join_generates_warning(self) -> None:
        result = self._rw("SELECT a.id FROM a, b WHERE a.id = b.id(+)")
        labels = [w.oracle_type for w in result.warnings]
        assert "outer join (+)" in labels

    def test_decode_generates_warning(self) -> None:
        result = self._rw("SELECT DECODE(status, 1, 'A', 'B') FROM t")
        labels = [w.oracle_type for w in result.warnings]
        assert "DECODE" in labels

    def test_no_warnings_for_simple_query(self) -> None:
        result = self._rw("SELECT id, name FROM employees")
        assert result.warnings == []

    def test_original_view_not_mutated(self) -> None:
        original = _view(query="SELECT SYSDATE FROM DUAL")
        rewrite_oracle_view(original, "NOW()", "NOW()", "CURRENT_USER()", "MY_SCHEMA")
        assert original.query == "SELECT SYSDATE FROM DUAL"


# ─── Tests: transform_views ───────────────────────────────────────────────────


class TestOracleToMariaDBTransformViews:
    def setup_method(self) -> None:
        self.transformer = OracleToMariaDBTransformer()

    def test_returns_same_count(self) -> None:
        views = [_view("V1"), _view("V2")]
        result = self.transformer.transform_views(views)
        assert len(result) == 2

    def test_sysdate_rewritten(self) -> None:
        views = [_view(query="SELECT SYSDATE FROM t")]
        result = self.transformer.transform_views(views)
        assert "NOW()" in result[0].query

    def test_empty_list(self) -> None:
        assert self.transformer.transform_views([]) == []

    def test_long_name_truncated(self) -> None:
        long_name = "V_" + "A" * 70
        views = [_view(name=long_name)]
        result = self.transformer.transform_views(views)
        assert len(result[0].name) <= 64
        assert any(w.oracle_type == "IDENTIFIER" for w in result[0].warnings)

    def test_short_name_unchanged(self) -> None:
        views = [_view(name="VW_SHORT")]
        result = self.transformer.transform_views(views)
        assert result[0].name == "VW_SHORT"
        assert not any(w.oracle_type == "IDENTIFIER" for w in result[0].warnings)


# ─── Tests: _emit_create_view ─────────────────────────────────────────────────


class TestMariaDBEmitCreateView:
    def setup_method(self) -> None:
        self.emitter = _emitter()

    def test_basic_view_ddl(self) -> None:
        v = _view(query="SELECT id, name FROM employees")
        ddl = self.emitter._emit_create_view(v)
        assert "CREATE OR REPLACE VIEW `VW_TEST` AS" in ddl
        assert "SELECT id, name FROM employees" in ddl

    def test_backtick_escaping(self) -> None:
        v = _view(name="order", query="SELECT 1")
        ddl = self.emitter._emit_create_view(v)
        assert "CREATE OR REPLACE VIEW `order` AS" in ddl

    def test_comment_emitted(self) -> None:
        v = _view(comment="Empleados activos")
        ddl = self.emitter._emit_create_view(v)
        assert "-- COMMENT: Empleados activos" in ddl

    def test_no_comment_when_empty(self) -> None:
        v = _view(comment="")
        ddl = self.emitter._emit_create_view(v)
        assert "-- COMMENT:" not in ddl

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

    def test_no_note_when_no_warnings(self) -> None:
        v = _view()
        ddl = self.emitter._emit_create_view(v)
        assert "-- NOTE:" not in ddl


# ─── Tests: emit_statements con vistas ────────────────────────────────────────


class TestMariaDBEmitStatementsWithViews:
    def setup_method(self) -> None:
        self.emitter = _emitter()

    def test_views_emitted_after_tables(self) -> None:
        tables = [_table("EMPLOYEES")]
        views = [_view("VW_EMP", query="SELECT id FROM EMPLOYEES")]
        stmts = self.emitter.emit_statements(tables, views)
        table_idx = next(i for i, s in enumerate(stmts) if "CREATE TABLE" in s)
        view_idx = next(i for i, s in enumerate(stmts) if "CREATE OR REPLACE VIEW" in s)
        assert view_idx > table_idx

    def test_view_with_empty_query_skipped(self) -> None:
        views = [_view(query="")]
        stmts = self.emitter.emit_statements([], views)
        assert not any("CREATE OR REPLACE VIEW" in s for s in stmts)

    def test_no_views_no_change(self) -> None:
        tables = [_table()]
        stmts_no_views = self.emitter.emit_statements(tables)
        stmts_empty_views = self.emitter.emit_statements(tables, [])
        assert stmts_no_views == stmts_empty_views

    def test_multiple_views_all_emitted(self) -> None:
        views = [_view("V1", "SELECT 1"), _view("V2", "SELECT 2")]
        stmts = self.emitter.emit_statements([], views)
        view_stmts = [s for s in stmts if "CREATE OR REPLACE VIEW" in s]
        assert len(view_stmts) == 2

    def test_emit_ddl_includes_views(self) -> None:
        tables = [_table()]
        views = [_view("VW_TEST", "SELECT id FROM T")]
        ddl = self.emitter.emit(tables, views)
        assert "CREATE OR REPLACE VIEW" in ddl
        assert ddl.endswith(";\n")


# ─── Tests: _topological_sort_views ──────────────────────────────────────────


class TestTopologicalSortViews:
    """Tests for _topological_sort_views (shared logic used by all three emitters)."""

    def test_empty_list(self) -> None:
        ordered, circular = _topological_sort_views([])
        assert ordered == []
        assert circular == []

    def test_single_view_no_deps(self) -> None:
        v = _view("V1", "SELECT 1")
        ordered, circular = _topological_sort_views([v])
        assert len(ordered) == 1
        assert circular == []

    def test_independent_views_all_ordered(self) -> None:
        views = [_view("VA", "SELECT 1"), _view("VB", "SELECT 2"), _view("VC", "SELECT 3")]
        ordered, circular = _topological_sort_views(views)
        assert len(ordered) == 3
        assert circular == []

    def test_chain_dependency_ordering(self) -> None:
        # VW_RESUMEN references VW_DETALLE → VW_DETALLE must come first
        v_detalle = _view("VW_DETALLE", "SELECT id, total FROM orders")
        v_resumen = _view("VW_RESUMEN", "SELECT * FROM VW_DETALLE WHERE total > 0")
        ordered, circular = _topological_sort_views([v_resumen, v_detalle])
        assert circular == []
        names = [v.name for v in ordered]
        assert names.index("VW_DETALLE") < names.index("VW_RESUMEN")

    def test_chain_three_levels(self) -> None:
        # C depends on B, B depends on A → order: A, B, C
        va = _view("VA", "SELECT 1")
        vb = _view("VB", "SELECT * FROM VA")
        vc = _view("VC", "SELECT * FROM VB")
        ordered, circular = _topological_sort_views([vc, vb, va])
        assert circular == []
        names = [v.name for v in ordered]
        assert names.index("VA") < names.index("VB") < names.index("VC")

    def test_diamond_dependency(self) -> None:
        # VD depends on VB and VC; VB and VC both depend on VA
        va = _view("VA", "SELECT 1")
        vb = _view("VB", "SELECT * FROM VA")
        vc = _view("VC", "SELECT * FROM VA")
        vd = _view("VD", "SELECT * FROM VB JOIN VC ON 1=1")
        ordered, circular = _topological_sort_views([vd, vc, vb, va])
        assert circular == []
        names = [v.name for v in ordered]
        assert names.index("VA") < names.index("VB")
        assert names.index("VA") < names.index("VC")
        assert names.index("VB") < names.index("VD")
        assert names.index("VC") < names.index("VD")

    def test_circular_dependency_detected(self) -> None:
        # VA references VB, VB references VA → both end up in circular
        va = _view("VA", "SELECT * FROM VB")
        vb = _view("VB", "SELECT * FROM VA")
        ordered, circular = _topological_sort_views([va, vb])
        assert ordered == []
        assert len(circular) == 2

    def test_circular_plus_independent(self) -> None:
        # VI is independent; VA and VB form a cycle
        vi = _view("VI", "SELECT 1")
        va = _view("VA", "SELECT * FROM VB")
        vb = _view("VB", "SELECT * FROM VA")
        ordered, circular = _topological_sort_views([vi, va, vb])
        assert len(ordered) == 1
        assert ordered[0].name == "VI"
        assert len(circular) == 2

    def test_case_insensitive_detection(self) -> None:
        # Reference in lowercase should still be detected
        v_base = _view("VW_BASE", "SELECT 1")
        v_top = _view("VW_TOP", "SELECT * FROM vw_base WHERE id > 0")
        ordered, circular = _topological_sort_views([v_top, v_base])
        assert circular == []
        names = [v.name for v in ordered]
        assert names.index("VW_BASE") < names.index("VW_TOP")

    def test_original_name_used_for_detection(self) -> None:
        # When the stored name differs from original_name (truncated), the query
        # contains the original Oracle name → dep must still be detected
        v_long = CanonicalView(
            name="VW_TRUNCATED",
            original_name="VW_VERY_LONG_ORIGINAL_NAME",
            schema="S",
            query="SELECT 1",
            columns=[],
            comment="",
            warnings=[],
        )
        v_ref = _view("VW_REF", "SELECT * FROM VW_VERY_LONG_ORIGINAL_NAME")
        ordered, circular = _topological_sort_views([v_ref, v_long])
        assert circular == []
        names = [v.name for v in ordered]
        assert names.index("VW_TRUNCATED") < names.index("VW_REF")


# ─── Tests: topological ordering via emit_statements ─────────────────────────


class TestMariaDBViewTopologicalEmit:
    def setup_method(self) -> None:
        self.emitter = _emitter()

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
        aviso_stmts = [s for s in stmts if "dependencia circular" in s]
        assert len(aviso_stmts) == 2

    def test_no_deps_no_aviso(self) -> None:
        views = [_view("V1", "SELECT 1"), _view("V2", "SELECT 2")]
        stmts = self.emitter.emit_statements([], views)
        assert not any("dependencia circular" in s for s in stmts)


# ─── Tests: MigrationPlan backward compatibility ──────────────────────────────


class TestMigrationPlanViewsBackwardCompat:
    def test_views_defaults_to_empty_list(self) -> None:
        plan = MigrationPlan(
            tables=[],
            warnings=[],
            source_schema="S",
            source_engine="oracle",
            target_engine="mariadb",
            emitter=_emitter(),
        )
        assert plan.views == []

    def test_emit_ddl_with_no_views(self) -> None:
        plan = MigrationPlan(
            tables=[_table()],
            warnings=[],
            source_schema="S",
            source_engine="oracle",
            target_engine="mariadb",
            emitter=_emitter(),
        )
        ddl = plan.emit_ddl()
        assert "CREATE TABLE" in ddl
        assert "CREATE OR REPLACE VIEW" not in ddl

    def test_emit_ddl_with_views(self) -> None:
        plan = MigrationPlan(
            tables=[_table()],
            warnings=[],
            source_schema="S",
            source_engine="oracle",
            target_engine="mariadb",
            emitter=_emitter(),
            views=[_view("VW_X", "SELECT 1")],
        )
        ddl = plan.emit_ddl()
        assert "CREATE OR REPLACE VIEW `VW_X`" in ddl
