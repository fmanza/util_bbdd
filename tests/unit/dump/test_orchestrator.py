"""Tests unitarios para DumpOrchestrator, DumpConfig, topological sort y helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from util_bbdd.dump._sql_utils import quote_identifier as _qi, quote_table as _qt
from util_bbdd.dump.orchestrator import (
    DumpConfig,
    DumpOrchestrator,
    DumpResult,
)

# ---------------------------------------------------------------------------
# Helpers de fabricación de mocks
# ---------------------------------------------------------------------------


def _make_engine(dialect_name: str = "postgresql") -> MagicMock:
    engine = MagicMock()
    engine.dialect.name = dialect_name
    engine.dialect.identifier_preparer.quote.side_effect = lambda n: n
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.execute.return_value.scalar_one.return_value = 0
    engine.connect.return_value = conn
    engine.begin.return_value = conn
    return engine


def _make_inspector(
    tables: list[str],
    columns_map: dict[str, list[str]] | None = None,
    fks: dict | None = None,
) -> MagicMock:
    insp = MagicMock()
    insp.get_table_names.return_value = tables
    columns_map = columns_map or {}
    fks = fks or {}

    def _get_columns(table: str, schema: str | None = None) -> list[dict]:
        return [{"name": c} for c in columns_map.get(table, ["id", "name"])]

    def _get_foreign_keys(table: str, schema: str | None = None) -> list[dict]:
        return fks.get(table, [])

    insp.get_columns.side_effect = _get_columns
    insp.get_foreign_keys.side_effect = _get_foreign_keys
    return insp


# ---------------------------------------------------------------------------
# DumpConfig
# ---------------------------------------------------------------------------


class TestDumpConfig:
    def test_defaults(self):
        src = _make_engine()
        dst = _make_engine()
        cfg = DumpConfig(source_engine=src, target_engine=dst)

        assert cfg.source_schema is None
        assert cfg.target_schema is None
        assert cfg.tables is None
        assert cfg.chunk_size == 5000
        assert cfg.truncate_target is True
        assert isinstance(cfg.output_dir, Path)

    def test_custom_values(self):
        src = _make_engine()
        dst = _make_engine()
        cfg = DumpConfig(
            source_engine=src,
            target_engine=dst,
            source_schema="public",
            target_schema="dbo",
            tables=["orders", "customers"],
            chunk_size=1000,
            truncate_target=False,
        )
        assert cfg.tables == ["orders", "customers"]
        assert cfg.truncate_target is False


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------


class TestTopologicalSort:
    def test_no_fks_returns_tables_in_original_order(self):
        insp = _make_inspector([], fks={})
        tables = ["a", "b", "c"]
        order, cycles = DumpOrchestrator._topological_sort(tables, insp, None)
        assert set(order) == {"a", "b", "c"}
        assert cycles == []

    def test_single_fk_dependency(self):
        # orders → customers: customers should come first
        fks = {"orders": [{"referred_table": "customers", "constrained_columns": ["customer_id"]}]}
        insp = _make_inspector([], fks=fks)
        tables = ["orders", "customers"]
        order, cycles = DumpOrchestrator._topological_sort(tables, insp, None)

        assert order.index("customers") < order.index("orders")
        assert cycles == []

    def test_chain_dependency(self):
        # c → b → a: order should be a, b, c
        fks = {
            "c": [{"referred_table": "b"}],
            "b": [{"referred_table": "a"}],
        }
        insp = _make_inspector([], fks=fks)
        tables = ["c", "b", "a"]
        order, cycles = DumpOrchestrator._topological_sort(tables, insp, None)

        assert order == ["a", "b", "c"]
        assert cycles == []

    def test_cycle_detected(self):
        # a → b, b → a: both in cycle
        fks = {
            "a": [{"referred_table": "b"}],
            "b": [{"referred_table": "a"}],
        }
        insp = _make_inspector([], fks=fks)
        tables = ["a", "b"]
        order, cycles = DumpOrchestrator._topological_sort(tables, insp, None)

        assert set(order) == {"a", "b"}
        assert len(cycles) == 1
        assert set(cycles[0]) == {"a", "b"}

    def test_self_reference_ignored(self):
        # employee.manager_id → employee (self-ref): no cycle
        fks = {"employee": [{"referred_table": "employee"}]}
        insp = _make_inspector([], fks=fks)
        tables = ["employee", "department"]
        order, cycles = DumpOrchestrator._topological_sort(tables, insp, None)

        assert cycles == []
        assert set(order) == {"employee", "department"}

    def test_mixed_cycle_and_independent_tables(self):
        fks = {
            "a": [{"referred_table": "b"}],
            "b": [{"referred_table": "a"}],
        }
        insp = _make_inspector([], fks=fks)
        tables = ["a", "b", "c"]  # c is independent
        order, cycles = DumpOrchestrator._topological_sort(tables, insp, None)

        assert "c" in order
        assert set(cycles[0]) == {"a", "b"}

    def test_multiple_disconnected_cycles_reported_separately(self):
        # Two independent cycles: a<->b and c<->d — must appear as separate groups.
        fks = {
            "a": [{"referred_table": "b"}],
            "b": [{"referred_table": "a"}],
            "c": [{"referred_table": "d"}],
            "d": [{"referred_table": "c"}],
        }
        insp = _make_inspector([], fks=fks)
        tables = ["a", "b", "c", "d"]
        order, cycles = DumpOrchestrator._topological_sort(tables, insp, None)

        assert set(order) == {"a", "b", "c", "d"}
        assert len(cycles) == 2
        cycle_sets = [frozenset(c) for c in cycles]
        assert frozenset({"a", "b"}) in cycle_sets
        assert frozenset({"c", "d"}) in cycle_sets


# ---------------------------------------------------------------------------
# Quoting helpers
# ---------------------------------------------------------------------------


class TestQuotingHelpers:
    def test_qi_delegates_to_preparer(self):
        engine = _make_engine()
        engine.dialect.identifier_preparer.quote.side_effect = lambda n: f'"{n}"'
        assert _qi("order", engine) == '"order"'

    def test_qt_no_schema(self):
        engine = _make_engine()
        engine.dialect.identifier_preparer.quote.side_effect = lambda n: n
        assert _qt("my_table", None, engine) == "my_table"

    def test_qt_with_schema(self):
        engine = _make_engine()
        engine.dialect.identifier_preparer.quote.side_effect = lambda n: f"[{n}]"
        assert _qt("orders", "dbo", engine) == "[dbo].[orders]"


# ---------------------------------------------------------------------------
# DumpOrchestrator._common_columns
# ---------------------------------------------------------------------------


class TestCommonColumns:
    def _make_orchestrator(self, src_cols: list[str], dst_cols: list[str]) -> DumpOrchestrator:
        src_engine = _make_engine()
        dst_engine = _make_engine()
        cfg = DumpConfig(source_engine=src_engine, target_engine=dst_engine)
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = MagicMock()
        orch._dst_insp = MagicMock()
        orch._src_insp.get_columns.return_value = [{"name": c} for c in src_cols]
        orch._dst_insp.get_columns.return_value = [{"name": c} for c in dst_cols]
        return orch

    def test_all_common(self):
        orch = self._make_orchestrator(["id", "name"], ["id", "name"])
        common, skipped, name_map = orch._common_columns("t", "t")
        assert common == ["id", "name"]
        assert skipped == []
        assert name_map == {"id": "id", "name": "name"}

    def test_some_skipped(self):
        orch = self._make_orchestrator(["id", "name", "extra_col"], ["id", "name"])
        common, skipped, _ = orch._common_columns("t", "t")
        assert "extra_col" in skipped
        assert "extra_col" not in common

    def test_empty_intersection(self):
        orch = self._make_orchestrator(["col_src"], ["col_dst"])
        common, skipped, _ = orch._common_columns("t", "t")
        assert common == []
        assert skipped == ["col_src"]

    def test_case_insensitive_match(self):
        # Source returns uppercase (Oracle), dest lowercase (PostgreSQL)
        orch = self._make_orchestrator(["ID", "NAME"], ["id", "name"])
        common, skipped, name_map = orch._common_columns("t", "t")
        assert common == ["ID", "NAME"]
        assert skipped == []
        # name_map debe mapear al case del destino para INSERT correcto
        assert name_map == {"ID": "id", "NAME": "name"}

    def test_case_map_used_as_identity_when_case_matches(self):
        orch = self._make_orchestrator(["userid", "email"], ["userid", "email"])
        _, _, name_map = orch._common_columns("t", "t")
        assert name_map == {"userid": "userid", "email": "email"}

    def test_cross_engine_different_table_names_queried_separately(self):
        """_common_columns consulta el inspector destino con el nombre canónico destino."""
        orch = self._make_orchestrator(["id", "name"], ["id", "name"])
        # src_table="Orders" (SQL Server), dst_table="orders" (PostgreSQL)
        orch._src_insp.get_columns.return_value = [{"name": "id"}, {"name": "name"}]
        orch._dst_insp.get_columns.return_value = [{"name": "id"}, {"name": "name"}]
        common, skipped, _ = orch._common_columns("Orders", "orders")
        assert common == ["id", "name"]
        assert skipped == []
        # Verificar que cada inspector recibió su nombre canónico
        orch._src_insp.get_columns.assert_called_with("Orders", schema=None)
        orch._dst_insp.get_columns.assert_called_with("orders", schema=None)


# ---------------------------------------------------------------------------
# DumpOrchestrator.run() — integración con mocks completos
# ---------------------------------------------------------------------------


class TestDumpOrchestratorRun:
    def _build_orchestrator(
        self,
        src_tables: list[str],
        dst_tables: list[str],
        src_cols: dict[str, list[str]] | None = None,
        dst_cols: dict[str, list[str]] | None = None,
        fks: dict | None = None,
        truncate: bool = False,
    ) -> DumpOrchestrator:
        src_cols = src_cols or {t: ["id", "name"] for t in src_tables}
        dst_cols = dst_cols or {t: ["id", "name"] for t in dst_tables}

        src_engine = _make_engine()
        dst_engine = _make_engine()
        cfg = DumpConfig(
            source_engine=src_engine,
            target_engine=dst_engine,
            truncate_target=truncate,
        )

        src_insp = _make_inspector(src_tables, src_cols, fks)
        dst_insp = _make_inspector(dst_tables, dst_cols)

        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = src_insp
        orch._dst_insp = dst_insp
        return orch

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.orchestrator.BulkCrud")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("dump_report.xlsx"))
    @patch("pandas.read_sql", return_value=iter([]))
    def test_run_returns_dump_result(self, mock_read_sql, mock_report, mock_bulk, mock_mgr_cls):
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        orch = self._build_orchestrator(
            src_tables=["customers"],
            dst_tables=["customers"],
        )
        result = orch.run()

        assert isinstance(result, DumpResult)
        assert len(result.table_results) >= 1

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("dump_report.xlsx"))
    @patch("pandas.read_sql", return_value=iter([]))
    def test_missing_table_reported(self, mock_read_sql, mock_report, mock_mgr_cls):
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        # orders is in source but not in destination
        orch = self._build_orchestrator(
            src_tables=["customers", "orders"],
            dst_tables=["customers"],
        )
        result = orch.run()

        missing = [r for r in result.table_results if r.status == "missing_target"]
        assert any(r.table_name == "orders" for r in missing)

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("dump_report.xlsx"))
    @patch("pandas.read_sql", return_value=iter([]))
    def test_skipped_when_no_common_columns(self, mock_read_sql, mock_report, mock_mgr_cls):
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        orch = self._build_orchestrator(
            src_tables=["t"],
            dst_tables=["t"],
            src_cols={"t": ["col_src"]},
            dst_cols={"t": ["col_dst"]},  # no overlap
        )
        result = orch.run()

        skipped = [r for r in result.table_results if r.status == "skipped"]
        assert len(skipped) == 1
        assert skipped[0].table_name == "t"


# ---------------------------------------------------------------------------
# DumpOrchestrator._cleanup — truncate y delete
# ---------------------------------------------------------------------------


class TestCleanup:
    def _make_orchestrator(self, dialect: str) -> DumpOrchestrator:
        src = _make_engine()
        dst = _make_engine(dialect)
        cfg = DumpConfig(source_engine=src, target_engine=dst, truncate_target=True)
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = MagicMock()
        orch._dst_insp = MagicMock()
        return orch

    def _executed_sql(self, orch: DumpOrchestrator) -> list[str]:
        engine: MagicMock = orch._cfg.target_engine  # type: ignore[assignment]
        return [str(call[0][0]) for call in engine.connect.return_value.__enter__.return_value.execute.call_args_list]

    def test_truncate_used_for_non_mssql(self):
        orch = self._make_orchestrator("postgresql")
        orch._cleanup(["customers", "orders"], skip=set())
        sql_stmts = self._executed_sql(orch)
        assert all("TRUNCATE TABLE" in s for s in sql_stmts)
        assert len(sql_stmts) == 2

    def test_truncate_used_for_mssql_no_fk_references(self):
        """Tabla SQL Server sin FK entrantes → TRUNCATE (optimización híbrida)."""
        orch = self._make_orchestrator("mssql")
        # Sin FK entrantes detectadas → TRUNCATE
        orch._dst_insp.get_table_names.return_value = ["customers"]
        orch._dst_insp.get_foreign_keys.return_value = []
        orch._cleanup(["customers"], skip=set())
        sql_stmts = self._executed_sql(orch)
        assert len(sql_stmts) == 1
        assert "TRUNCATE TABLE" in sql_stmts[0]

    def test_delete_used_for_mssql_referenced_table(self):
        """Tabla SQL Server referenciada por FK de otra tabla → DELETE."""
        orch = self._make_orchestrator("mssql")
        orch._dst_insp.get_table_names.return_value = ["customers", "orders"]
        orch._dst_insp.get_foreign_keys.side_effect = lambda t, schema=None: (
            [{"referred_table": "customers"}] if t == "orders" else []
        )
        orch._cleanup(["customers"], skip=set())
        sql_stmts = self._executed_sql(orch)
        assert len(sql_stmts) == 1
        assert "DELETE FROM" in sql_stmts[0]

    def test_skip_set_excludes_tables(self):
        orch = self._make_orchestrator("postgresql")
        orch._cleanup(["customers", "orders"], skip={"orders"})
        sql_stmts = self._executed_sql(orch)
        assert len(sql_stmts) == 1
        assert "orders" not in sql_stmts[0]

    def test_truncate_called_during_run_when_truncate_target_true(self):
        from unittest.mock import patch

        src = _make_engine()
        dst = _make_engine()
        cfg = DumpConfig(source_engine=src, target_engine=dst, truncate_target=True)
        src_insp = _make_inspector(["customers"], {"customers": ["id", "name"]})
        dst_insp = _make_inspector(["customers"], {"customers": ["id", "name"]})
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = src_insp
        orch._dst_insp = dst_insp

        with (
            patch("util_bbdd.dump.orchestrator.ConstraintManager") as mock_mgr_cls,
            patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx")),
            patch("pandas.read_sql", return_value=iter([])),
            patch.object(orch, "_cleanup") as mock_cleanup,
        ):
            mock_mgr = MagicMock()
            mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
            mock_mgr.__exit__ = MagicMock(return_value=False)
            mock_mgr.constraint_results = []
            mock_mgr_cls.return_value = mock_mgr
            orch.run()

        mock_cleanup.assert_called_once()


# ---------------------------------------------------------------------------
# DumpOrchestrator — propagación de target_schema al INSERT (T4)
# ---------------------------------------------------------------------------


class TestTargetSchemaPropagation:
    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("pandas.read_sql")
    @patch("util_bbdd.dump.orchestrator.BulkCrud")
    def test_target_schema_passed_to_bulk_insert(self, mock_bulk_cls, mock_read_sql, mock_report, mock_mgr_cls):
        import pandas as pd

        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        df_chunk = pd.DataFrame({"id": [1], "name": ["x"]})
        mock_read_sql.return_value = iter([df_chunk])
        mock_crud = MagicMock()
        mock_bulk_cls.return_value = mock_crud

        src = _make_engine()
        dst = _make_engine()
        cfg = DumpConfig(
            source_engine=src,
            target_engine=dst,
            target_schema="staging",
            truncate_target=False,
        )
        src_insp = _make_inspector(["orders"], {"orders": ["id", "name"]})
        dst_insp = _make_inspector(["orders"], {"orders": ["id", "name"]})
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = src_insp
        orch._dst_insp = dst_insp
        orch.run()

        call_args = mock_crud.bulk_insert_from_df.call_args
        assert call_args is not None
        tabla_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("tabla_destino", "")
        assert tabla_arg == "staging.orders"

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("pandas.read_sql")
    @patch("util_bbdd.dump.orchestrator.BulkCrud")
    def test_dest_table_uses_logical_name_for_bulk_insert(
        self, mock_bulk_cls, mock_read_sql, mock_report, mock_mgr_cls
    ):
        """TC1: bulk_insert_from_df recibe nombre lógico (schema.tabla sin quoting de dialecto).
        reflect_table() en BulkCrud espera 'schema.tabla', no '[schema].[tabla]' ni `tabla`.
        El quoting de dialecto solo aplica al SQL directo (SELECT), no a la reflexión de tabla."""
        import pandas as pd

        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        df_chunk = pd.DataFrame({"id": [1]})
        mock_read_sql.return_value = iter([df_chunk])
        mock_crud = MagicMock()
        mock_bulk_cls.return_value = mock_crud

        src = _make_engine()
        dst = _make_engine()
        # Engine con quoting de SQL Server (simula dialecto que añade corchetes)
        dst.dialect.identifier_preparer.quote.side_effect = lambda n: f"[{n}]"

        cfg = DumpConfig(
            source_engine=src,
            target_engine=dst,
            target_schema="order",  # keyword reservada en SQL
            truncate_target=False,
        )
        src_insp = _make_inspector(["user"], {"user": ["id"]})  # "user" también es keyword
        dst_insp = _make_inspector(["user"], {"user": ["id"]})
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = src_insp
        orch._dst_insp = dst_insp
        orch.run()

        call_args = mock_crud.bulk_insert_from_df.call_args
        assert call_args is not None
        tabla_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("tabla_destino", "")
        # Debe ser el nombre lógico (schema.tabla), NO la forma quoted del dialecto
        assert tabla_arg == "order.user"

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("pandas.read_sql")
    @patch("util_bbdd.dump.orchestrator.BulkCrud")
    def test_chunk_error_sets_error_status_and_correct_row_count(
        self, mock_bulk_cls, mock_read_sql, mock_report, mock_mgr_cls
    ):
        """TC5: error en chunk 2 de 2 → status=error, bulk_insert llamado dos veces."""
        import pandas as pd

        from sqlalchemy.exc import SQLAlchemyError

        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        chunk1 = pd.DataFrame({"id": [1, 2]})
        chunk2 = pd.DataFrame({"id": [3, 4]})
        mock_read_sql.return_value = iter([chunk1, chunk2])

        mock_crud = MagicMock()
        # Primer chunk OK, segundo falla con SQLAlchemyError
        mock_crud.bulk_insert_from_df.side_effect = [None, SQLAlchemyError("FK violation")]
        mock_bulk_cls.return_value = mock_crud

        cfg = DumpConfig(
            source_engine=_make_engine(),
            target_engine=_make_engine(),
            truncate_target=False,
        )
        src_insp = _make_inspector(["t"], {"t": ["id"]})
        dst_insp = _make_inspector(["t"], {"t": ["id"]})
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = src_insp
        orch._dst_insp = dst_insp
        result = orch.run()

        t_result = next(r for r in result.table_results if r.table_name == "t")
        assert t_result.status == "error"
        assert "FK violation" in t_result.error_msg
        assert mock_crud.bulk_insert_from_df.call_count == 2


# ---------------------------------------------------------------------------
# DumpOrchestrator._get_source_tables — determinismo con sorted (O3)
# ---------------------------------------------------------------------------


class TestGetSourceTables:
    def test_explicit_tables_returned_sorted(self):
        engine = _make_engine()
        cfg = DumpConfig(
            source_engine=engine,
            target_engine=engine,
            tables=["z_table", "a_table", "m_table"],
        )
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = MagicMock()

        result = orch._get_source_tables()

        assert result == ["a_table", "m_table", "z_table"]

    def test_without_explicit_tables_delegates_to_inspector(self):
        engine = _make_engine()
        cfg = DumpConfig(source_engine=engine, target_engine=engine)
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = MagicMock()
        orch._src_insp.get_table_names.return_value = ["c", "a", "b"]

        result = orch._get_source_tables()

        # Inspector order preserved (no sort applied)
        assert result == ["c", "a", "b"]


# ---------------------------------------------------------------------------
# DumpOrchestrator — comparación cross-engine (case-insensitive)
# ---------------------------------------------------------------------------


class TestCrossEngineTableMatching:
    """Verifica que la comparación de tablas entre motores distintos (case mismatch)
    no declare tablas como faltantes cuando existen bajo distinto case."""

    def _make_cross_engine_orchestrator(
        self,
        src_tables: list[str],
        dst_tables: list[str],
        truncate: bool = False,
    ) -> DumpOrchestrator:
        src_cols = {t: ["id", "name"] for t in src_tables}
        dst_cols = {t: ["id", "name"] for t in dst_tables}

        src_engine = _make_engine("mssql")
        dst_engine = _make_engine("postgresql")
        cfg = DumpConfig(source_engine=src_engine, target_engine=dst_engine, truncate_target=truncate)

        src_insp = _make_inspector(src_tables, src_cols)
        dst_insp = _make_inspector(dst_tables, dst_cols)

        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = src_insp
        orch._dst_insp = dst_insp
        return orch

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("pandas.read_sql", return_value=iter([]))
    def test_no_missing_when_same_tables_differ_only_in_case(self, mock_read_sql, mock_report, mock_mgr_cls):
        """SQL Server devuelve 'Orders','Customers'; PostgreSQL 'orders','customers'.
        Ninguna tabla debe aparecer como missing_target."""
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        orch = self._make_cross_engine_orchestrator(
            src_tables=["Orders", "Customers"],
            dst_tables=["orders", "customers"],
        )
        result = orch.run()

        missing = [r for r in result.table_results if r.status == "missing_target"]
        assert missing == [], f"No debería haber tablas faltantes, encontradas: {[r.table_name for r in missing]}"

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("pandas.read_sql", return_value=iter([]))
    def test_genuinely_missing_table_still_reported(self, mock_read_sql, mock_report, mock_mgr_cls):
        """Una tabla que realmente no existe en destino debe seguir reportándose."""
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        orch = self._make_cross_engine_orchestrator(
            src_tables=["Orders", "Inventory"],  # Inventory no existe en dst
            dst_tables=["orders"],
        )
        result = orch.run()

        missing = [r for r in result.table_results if r.status == "missing_target"]
        assert len(missing) == 1
        assert missing[0].table_name == "Inventory"

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("pandas.read_sql", return_value=iter([]))
    def test_effective_dst_order_uses_canonical_dst_names(self, mock_read_sql, mock_report, mock_mgr_cls):
        """ConstraintManager.disable_all debe recibir los nombres canónicos del destino."""
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        orch = self._make_cross_engine_orchestrator(
            src_tables=["Orders"],
            dst_tables=["orders"],
        )
        orch.run()

        # ConstraintManager.disable_all debe recibir nombre destino "orders", no "Orders"
        disable_call_args = mock_mgr.disable_all.call_args
        assert disable_call_args is not None
        tables_arg = disable_call_args[1].get("tables") or disable_call_args[0][0]
        assert tables_arg == ["orders"], f"Se esperaba ['orders'], se recibió {tables_arg}"

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("pandas.read_sql", return_value=iter([]))
    def test_same_engine_no_regression(self, mock_read_sql, mock_report, mock_mgr_cls):
        """Mismo motor (mismo case en nombres) no introduce regresiÃ³n."""
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        src_engine = _make_engine("postgresql")
        dst_engine = _make_engine("postgresql")
        cfg = DumpConfig(source_engine=src_engine, target_engine=dst_engine, truncate_target=False)
        src_insp = _make_inspector(["customers", "orders"], {"customers": ["id"], "orders": ["id"]})
        dst_insp = _make_inspector(["customers", "orders"], {"customers": ["id"], "orders": ["id"]})
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = src_insp
        orch._dst_insp = dst_insp
        result = orch.run()

        missing = [r for r in result.table_results if r.status == "missing_target"]
        success_or_skipped = [r for r in result.table_results if r.status in ("success", "skipped")]
        assert missing == []
        assert len(success_or_skipped) == 2


# ---------------------------------------------------------------------------
# Propuesta C — collect_row_counts
# ---------------------------------------------------------------------------


class TestCollectRowCounts:
    def test_dump_config_collect_row_counts_defaults_true(self) -> None:
        """DumpConfig.collect_row_counts es True por defecto."""
        engine = _make_engine()
        cfg = DumpConfig(source_engine=engine, target_engine=engine)
        assert cfg.collect_row_counts is True

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("pandas.read_sql", return_value=iter([]))
    @patch("util_bbdd.dump.orchestrator.BulkCrud")
    def test_collect_row_counts_false_returns_minus_one(
        self, mock_bulk_cls, mock_read_sql, mock_report, mock_mgr_cls
    ) -> None:
        """collect_row_counts=False → source_rows y target_rows_* son -1."""
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr
        mock_bulk_cls.return_value = MagicMock()

        cfg = DumpConfig(
            source_engine=_make_engine(),
            target_engine=_make_engine(),
            truncate_target=False,
            collect_row_counts=False,
        )
        src_insp = _make_inspector(["customers"], {"customers": ["id"]})
        dst_insp = _make_inspector(["customers"], {"customers": ["id"]})
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = src_insp
        orch._dst_insp = dst_insp

        with patch.object(orch, "_safe_count") as mock_safe_count:
            result = orch.run()

        mock_safe_count.assert_not_called()
        t = next(r for r in result.table_results if r.table_name == "customers")
        assert t.source_rows == -1
        assert t.target_rows_before == -1
        assert t.target_rows_after == -1

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("pandas.read_sql", return_value=iter([]))
    @patch("util_bbdd.dump.orchestrator.BulkCrud")
    def test_process_table_calls_bulk_session(self, mock_bulk_cls, mock_read_sql, mock_report, mock_mgr_cls) -> None:
        """bulk_session() se llama al menos una vez durante el procesado de la tabla."""
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        mock_crud = MagicMock()
        mock_bulk_cls.return_value = mock_crud

        cfg = DumpConfig(
            source_engine=_make_engine(),
            target_engine=_make_engine(),
            truncate_target=False,
        )
        src_insp = _make_inspector(["orders"], {"orders": ["id"]})
        dst_insp = _make_inspector(["orders"], {"orders": ["id"]})
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = src_insp
        orch._dst_insp = dst_insp
        orch.run()

        mock_crud.bulk_session.assert_called_once()


# ---------------------------------------------------------------------------
# Optimización: el volcado NO ejecuta comparación de esquemas (cascada N+1)
# ---------------------------------------------------------------------------


class TestSchemaComparisonRemoved:
    """El dump deriva las columnas inexistentes de ``skipped_columns``, sin ``SchemaComparator``."""

    def test_orchestrator_module_does_not_reference_schema_comparator(self) -> None:
        """Regresión de rendimiento: reintroducir ``SchemaComparator`` en el orquestador
        devolvería la cascada N+1 de introspección (índices, FKs de destino, comentarios y
        vistas) que el volcado de datos no necesita."""
        import util_bbdd.dump.orchestrator as orch_mod

        assert not hasattr(orch_mod, "SchemaComparator")
        assert not hasattr(orch_mod, "SchemaDiff")

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.orchestrator.BulkCrud")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("pandas.read_sql", return_value=iter([]))
    def test_report_built_from_skipped_columns_without_diff(
        self, mock_read_sql, mock_report, mock_bulk_cls, mock_mgr_cls
    ) -> None:
        """El informe se construye con ``table_results`` (que incluye ``skipped_columns``)
        y sin argumento ``diff``: la columna presente en origen y ausente en destino viaja
        por la ruta de carga, no por una comparación de esquemas independiente."""
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr
        mock_bulk_cls.return_value = MagicMock()

        cfg = DumpConfig(
            source_engine=_make_engine(),
            target_engine=_make_engine(),
            truncate_target=False,
        )
        # 'extra_col' existe en origen pero no en destino → debe terminar en skipped_columns
        src_insp = _make_inspector(["orders"], {"orders": ["id", "name", "extra_col"]})
        dst_insp = _make_inspector(["orders"], {"orders": ["id", "name"]})
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = src_insp
        orch._dst_insp = dst_insp
        orch.run()

        assert mock_report.call_args is not None
        kwargs = mock_report.call_args.kwargs
        assert "diff" not in kwargs, "El informe no debe recibir un SchemaDiff"
        orders = next(r for r in kwargs["table_results"] if r.table_name == "orders")
        assert "extra_col" in orders.skipped_columns
