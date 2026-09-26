"""Tests unitarios para DumpOrchestrator, DumpConfig, topological sort y helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import sqltypes

from util_bbdd._core.exceptions import DumpError
from util_bbdd.dump._models import IndexActionResult
from util_bbdd.dump._sql_utils import quote_identifier as _qi, quote_table as _qt
from util_bbdd.dump.orchestrator import (
    DumpConfig,
    DumpOrchestrator,
    DumpResult,
    TableDumpResult,
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
        src_engine = _make_engine()
        dst_engine = _make_engine()
        cfg = DumpConfig(source_engine=src_engine, target_engine=dst_engine)
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = MagicMock()
        orch._dst_insp = MagicMock()
        orch._src_insp.get_columns.return_value = [{"name": "id"}, {"name": "name"}]
        orch._dst_insp.get_columns.return_value = [{"name": "id"}, {"name": "name"}]
        # src_table="Orders" (SQL Server), dst_table="orders" (PostgreSQL)
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
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
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
        # El informe recibe el mismo resumen de auditoría que el resultado (None: sin bulk_audit_path).
        assert "audit_summary" in mock_report.call_args.kwargs
        assert mock_report.call_args.kwargs["audit_summary"] is result.audit_summary
        assert "pk_sync_results" in mock_report.call_args.kwargs
        assert mock_report.call_args.kwargs["pk_sync_results"] is result.pk_sync_results

    @patch("util_bbdd.dump.orchestrator.IndexManager")
    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.orchestrator.BulkCrud")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("dump_report.xlsx"))
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
    def test_manage_indexes_disables_and_reports(
        self, mock_read_sql, mock_report, mock_bulk, mock_mgr_cls, mock_index_cls
    ):
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        index_results = [IndexActionResult("customers", "ix_a", "postgresql", "recreated")]
        mock_index = MagicMock()
        mock_index.__enter__ = MagicMock(return_value=mock_index)
        mock_index.__exit__ = MagicMock(return_value=False)
        mock_index.index_results = index_results
        mock_index_cls.return_value = mock_index

        orch = self._build_orchestrator(src_tables=["customers"], dst_tables=["customers"])
        orch._cfg.manage_indexes = True
        result = orch.run()

        mock_index.disable_all.assert_called_once_with(tables=["customers"])
        assert result.index_results == index_results
        # El informe recibe los resultados de índices
        assert mock_report.call_args.kwargs["index_results"] == index_results

    @patch("util_bbdd.dump.orchestrator.IndexManager")
    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("dump_report.xlsx"))
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
    def test_manage_indexes_false_does_not_instantiate_index_manager(
        self, mock_read_sql, mock_report, mock_mgr_cls, mock_index_cls
    ):
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        orch = self._build_orchestrator(src_tables=["customers"], dst_tables=["customers"])
        result = orch.run()

        mock_index_cls.assert_not_called()
        assert result.index_results is None
        assert mock_report.call_args.kwargs["index_results"] is None

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("dump_report.xlsx"))
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
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

    def test_run_wraps_introspection_failure_in_dump_error(self):
        """FND-03/FND-04 (AUDIT_CODE 2026-09-22, decisión confirmada por el usuario):
        un fallo de introspección en FASE 1 (análisis inicial) es un fallo de
        orquestación no recuperable — debe surgir como DumpError, no como
        SQLAlchemyError crudo (a diferencia de los fallos por tabla individual)."""
        orch = self._build_orchestrator(src_tables=["customers"], dst_tables=["customers"])
        orch._dst_insp.get_table_names.side_effect = SQLAlchemyError("connection lost")

        with pytest.raises(DumpError, match="connection lost"):
            orch.run()

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("dump_report.xlsx"))
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
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

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("dump_report.xlsx"))
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
    def test_parallel_path_used_when_max_parallel_tables_gt_1(self, mock_read_sql, mock_report, mock_mgr_cls):
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        orch = self._build_orchestrator(src_tables=["customers", "products"], dst_tables=["customers", "products"])
        orch._cfg.max_parallel_tables = 2
        orch._load_parallel = MagicMock(return_value=[])  # type: ignore[method-assign]
        orch._reflect_loaded_tables = MagicMock()  # type: ignore[method-assign]
        orch.run()

        orch._load_parallel.assert_called_once()
        orch._reflect_loaded_tables.assert_called_once()

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("dump_report.xlsx"))
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
    def test_sequential_path_when_default(self, mock_read_sql, mock_report, mock_mgr_cls):
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        orch = self._build_orchestrator(src_tables=["customers"], dst_tables=["customers"])
        orch._load_parallel = MagicMock()  # type: ignore[method-assign]
        orch.run()

        orch._load_parallel.assert_not_called()

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("dump_report.xlsx"))
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
    def test_sequential_path_reflects_loaded_tables_for_pk_sync(self, mock_read_sql, mock_report, mock_mgr_cls):
        """PD-11: con parallel_pk_ranges > 1 las tablas se cargan con BulkCrud del ParallelBulkLoader; sin reflejarlas en
        la crud principal, la Fase 5a (PK sync) no encontraba ninguna. Antes solo se reflejaban con max_parallel_tables > 1."""
        mock_mgr = MagicMock()
        mock_mgr.__enter__ = MagicMock(return_value=mock_mgr)
        mock_mgr.__exit__ = MagicMock(return_value=False)
        mock_mgr.constraint_results = []
        mock_mgr_cls.return_value = mock_mgr

        orch = self._build_orchestrator(src_tables=["customers"], dst_tables=["customers"])
        orch._reflect_loaded_tables = MagicMock()  # type: ignore[method-assign]
        orch.run()

        orch._reflect_loaded_tables.assert_called_once()
        reflected_results = orch._reflect_loaded_tables.call_args.args[1]
        assert [r.table_name for r in reflected_results] == ["customers"]


# ---------------------------------------------------------------------------
# DumpOrchestrator — paralelización (Incremento 3a)
# ---------------------------------------------------------------------------


class TestTopologicalLevels:
    def test_independent_tables_same_level(self):
        insp = _make_inspector(["customers", "products"])
        levels = DumpOrchestrator._topological_levels(["customers", "products"], insp, None)
        assert levels == [["customers", "products"]]

    def test_dependent_table_next_level(self):
        insp = _make_inspector(
            ["customers", "products", "orders"],
            fks={"orders": [{"referred_table": "customers"}]},
        )
        levels = DumpOrchestrator._topological_levels(["customers", "products", "orders"], insp, None)
        assert levels == [["customers", "products"], ["orders"]]

    def test_chain_produces_one_table_per_level(self):
        insp = _make_inspector(
            ["a", "b", "c"],
            fks={"b": [{"referred_table": "a"}], "c": [{"referred_table": "b"}]},
        )
        levels = DumpOrchestrator._topological_levels(["a", "b", "c"], insp, None)
        assert levels == [["a"], ["b"], ["c"]]

    def test_cycle_tables_excluded(self):
        insp = _make_inspector(
            ["a", "b", "c"],
            fks={"a": [{"referred_table": "b"}], "b": [{"referred_table": "a"}]},
        )
        levels = DumpOrchestrator._topological_levels(["a", "b", "c"], insp, None)
        # a y b forman ciclo → excluidas; solo c (independiente) aparece
        assert levels == [["c"]]


class TestResolveMaxWorkers:
    def _orch_with_pools(self, src_cap: int | None, dst_cap: int | None) -> DumpOrchestrator:
        def _engine(cap: int | None) -> MagicMock:
            eng = MagicMock()
            if cap is None:
                eng.pool.size = "not-callable"
            else:
                eng.pool.size = MagicMock(return_value=cap)
                eng.pool._max_overflow = 0
            return eng

        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = DumpConfig(source_engine=_engine(src_cap), target_engine=_engine(dst_cap))
        return orch

    def test_requested_1_returns_1(self):
        orch = self._orch_with_pools(10, 10)
        assert orch._resolve_max_workers(1) == 1

    def test_degrades_to_min_pool_capacity(self, caplog):
        orch = self._orch_with_pools(8, 4)
        with caplog.at_level("WARNING"):
            assert orch._resolve_max_workers(6) == 4
        assert "se degrada" in caplog.text.lower()

    def test_respects_requested_when_pool_sufficient(self):
        orch = self._orch_with_pools(10, 10)
        assert orch._resolve_max_workers(4) == 4

    def test_respects_requested_when_capacity_unknown(self):
        orch = self._orch_with_pools(None, None)
        assert orch._resolve_max_workers(4) == 4

    def test_pool_capacity_includes_overflow(self):
        eng = MagicMock()
        eng.pool.size = MagicMock(return_value=5)
        eng.pool._max_overflow = 10
        assert DumpOrchestrator._pool_capacity(eng) == 15


class TestLoadParallel:
    def _build(self, src_tables, fks=None):
        src_cols = {t: ["id", "name"] for t in src_tables}
        dst_cols = {t: ["id", "name"] for t in src_tables}
        cfg = DumpConfig(source_engine=_make_engine(), target_engine=_make_engine(), max_parallel_tables=2)
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        orch._src_insp = _make_inspector(src_tables, src_cols, fks)
        orch._dst_insp = _make_inspector(src_tables, dst_cols)
        return orch

    def _stub_process(self, orch):
        def _fake(src_table, dst_table, position, in_cycle, crud, common, skipped, name_map, pk_range_col=None):
            return TableDumpResult(
                table_name=src_table,
                source_rows=0,
                target_rows_before=0,
                target_rows_after=0,
                status="success",
                skipped_columns=[],
                load_order_position=position,
                in_cycle=in_cycle,
            )

        orch._process_table_with_columns = MagicMock(side_effect=_fake)  # type: ignore[method-assign]
        orch._make_worker_crud = MagicMock(return_value=MagicMock())  # type: ignore[method-assign]

    def test_loads_all_tables_ordered_by_position(self):
        orch = self._build(["customers", "products", "orders"], fks={"orders": [{"referred_table": "customers"}]})
        self._stub_process(orch)
        src_to_dst = {t: t for t in ["customers", "products", "orders"]}

        results = orch._load_parallel(["customers", "products", "orders"], src_to_dst, set(), 2)

        assert [r.table_name for r in results] == ["customers", "products", "orders"]
        assert [r.load_order_position for r in results] == [0, 1, 2]
        assert orch._process_table_with_columns.call_count == 3

    def test_cycle_tables_loaded_sequentially(self):
        orch = self._build(["c", "a", "b"], fks={"a": [{"referred_table": "b"}], "b": [{"referred_table": "a"}]})
        self._stub_process(orch)
        src_to_dst = {t: t for t in ["c", "a", "b"]}

        results = orch._load_parallel(["c", "a", "b"], src_to_dst, {"a", "b"}, 2)

        names = {r.table_name for r in results}
        assert names == {"a", "b", "c"}
        # a y b marcadas in_cycle
        in_cycle = {r.table_name for r in results if r.in_cycle}
        assert in_cycle == {"a", "b"}


# ---------------------------------------------------------------------------
# DumpOrchestrator — paralelización por rangos de PK (Incremento 3b)
# ---------------------------------------------------------------------------


class TestComputeRangeBounds:
    def test_even_split_covers_full_range_without_gaps(self):
        bounds = DumpOrchestrator._compute_range_bounds(1, 10, 3)
        assert bounds == [(1, 5, False), (5, 9, False), (9, 10, True)]

    def test_last_range_is_inclusive(self):
        bounds = DumpOrchestrator._compute_range_bounds(1, 10, 3)
        assert bounds[-1][2] is True  # is_last → usa <=

    def test_fewer_rows_than_ranges(self):
        bounds = DumpOrchestrator._compute_range_bounds(1, 2, 5)
        assert bounds == [(1, 2, False), (2, 2, True)]

    def test_single_value(self):
        bounds = DumpOrchestrator._compute_range_bounds(7, 7, 4)
        assert bounds == [(7, 7, True)]

    def test_empty_when_hi_lt_lo(self):
        assert DumpOrchestrator._compute_range_bounds(10, 1, 3) == []


class TestSqliteSourceWarning:
    """PD-07: un origen SQLite entrega fechas como texto y DECIMAL como float; se avisa en el constructor."""

    @pytest.mark.parametrize(
        ("src", "dst", "expected"),
        [
            ("sqlite", "sqlite", "las tablas con columnas de fecha fallarán"),
            ("sqlite", "postgresql", "el destino las convierte"),
            ("postgresql", "sqlite", None),
        ],
    )
    def test_warning_depends_on_source_and_target(self, caplog, src, dst, expected):
        with caplog.at_level("WARNING", logger="util_bbdd.dump.orchestrator"):
            DumpOrchestrator._warn_sqlite_source(_make_engine(src), _make_engine(dst))
        if expected is None:
            assert "Origen SQLite" not in caplog.text
        else:
            assert "Origen SQLite" in caplog.text
            assert expected in caplog.text

    def test_constructor_warns_with_sqlite_source(self, caplog, tmp_path: Path):
        from sqlalchemy import create_engine

        src = create_engine(f"sqlite:///{tmp_path / 'a.db'}")
        dst = create_engine(f"sqlite:///{tmp_path / 'b.db'}")
        with caplog.at_level("WARNING", logger="util_bbdd.dump.orchestrator"):
            DumpOrchestrator(DumpConfig(source_engine=src, target_engine=dst, output_dir=tmp_path))
        assert "Origen SQLite" in caplog.text
        src.dispose()
        dst.dispose()


class TestLargeBatchWithLobsWarning:
    """Paso 2.3: el aviso de max_allowed_packet solo si alguna tabla destino tiene columnas TEXT/BLOB/JSON."""

    def _orch(self, dialect: str, column_types: dict[str, list[object]], **cfg: object) -> DumpOrchestrator:
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = DumpConfig(source_engine=_make_engine(), target_engine=_make_engine(dialect), **cfg)  # type: ignore[arg-type]
        orch._dst_insp = MagicMock()
        orch._dst_insp.get_columns.side_effect = lambda table, schema=None: [{"type": t} for t in column_types[table]]
        return orch

    def _warned(self, caplog, orch: DumpOrchestrator, tables: list[str]) -> bool:
        with caplog.at_level("WARNING", logger="util_bbdd.dump.orchestrator"):
            orch._warn_large_batch_with_lobs(tables)
        return "max_allowed_packet" in caplog.text

    @pytest.mark.parametrize("lob", [sqltypes.Text(), sqltypes.LargeBinary(), sqltypes.JSON()])
    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_warns_with_lob_columns(self, caplog, dialect, lob):
        orch = self._orch(dialect, {"a": [sqltypes.Integer()], "docs": [sqltypes.Integer(), lob]})
        assert self._warned(caplog, orch, ["a", "docs"])
        assert "docs" in caplog.text and " a," not in caplog.text

    def test_no_warning_without_lob_columns(self, caplog):
        orch = self._orch("mysql", {"a": [sqltypes.Integer(), sqltypes.String(50)]})
        assert not self._warned(caplog, orch, ["a"])

    def test_no_warning_with_small_batch(self, caplog):
        orch = self._orch("mysql", {"docs": [sqltypes.Text()]}, chunk_size=1000)
        assert not self._warned(caplog, orch, ["docs"])

    def test_no_warning_on_other_targets(self, caplog):
        orch = self._orch("postgresql", {"docs": [sqltypes.Text()]})
        assert not self._warned(caplog, orch, ["docs"])

    def test_introspection_error_is_skipped(self, caplog):
        orch = self._orch("mysql", {})
        orch._dst_insp.get_columns.side_effect = SQLAlchemyError("no se puede reflejar")
        assert not self._warned(caplog, orch, ["docs"])


class TestSlowPkRangesWarning:
    """Q4: con destino MySQL/MariaDB, parallel_pk_ranges > 1 es más lento que la carga secuencial; se avisa sin forzar."""

    def _orch(self, dialect: str) -> DumpOrchestrator:
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = DumpConfig(source_engine=_make_engine(), target_engine=_make_engine(dialect))
        orch._cfg.target_engine.pool.size = "x"  # capacidad no determinable: se respeta lo pedido
        orch._cfg.source_engine.pool.size = "x"
        return orch

    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_warns_but_keeps_requested_ranges(self, caplog, dialect):
        with caplog.at_level("WARNING", logger="util_bbdd.dump.orchestrator"):
            assert self._orch(dialect)._resolve_range_count(4, 1) == 4
        assert "parallel_pk_ranges=4" in caplog.text
        assert "más lenta" in caplog.text

    @pytest.mark.parametrize("dialect", ["postgresql", "mssql", "oracle"])
    def test_no_warning_on_other_targets(self, caplog, dialect):
        with caplog.at_level("WARNING", logger="util_bbdd.dump.orchestrator"):
            assert self._orch(dialect)._resolve_range_count(4, 1) == 4
        assert "más lenta" not in caplog.text

    def test_no_warning_without_ranges(self, caplog):
        with caplog.at_level("WARNING", logger="util_bbdd.dump.orchestrator"):
            assert self._orch("mysql")._resolve_range_count(1, 1) == 1
        assert caplog.text == ""


class TestSqliteTargetSingleWriter:
    """PD-06: SQLite admite un solo escritor; en paralelo, 'database is locked' y la tabla quedaba a medio cargar."""

    def _orch(self, dialect: str) -> DumpOrchestrator:
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = DumpConfig(source_engine=_make_engine(), target_engine=_make_engine(dialect))
        return orch

    def test_sqlite_target_forces_one_range_and_one_table_with_warning(self, caplog):
        orch = self._orch("sqlite")
        with caplog.at_level("WARNING", logger="util_bbdd.dump.orchestrator"):
            assert orch._resolve_range_count(4, 1) == 1
            assert orch._resolve_max_workers(3) == 1
        assert "parallel_pk_ranges=4" in caplog.text
        assert "max_parallel_tables=3" in caplog.text

    def test_other_targets_keep_requested_parallelism(self):
        orch = self._orch("postgresql")
        orch._cfg.target_engine.pool.size = "x"  # capacidad no determinable: se respeta lo pedido
        orch._cfg.source_engine.pool.size = "x"
        assert orch._resolve_range_count(4, 1) == 4
        assert orch._resolve_max_workers(3) == 3

    def test_sqlite_dump_with_parallel_options_loads_every_row(self, tmp_path: Path):
        from sqlalchemy import create_engine, text

        src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
        dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
        for eng in (src, dst):
            with eng.begin() as conn:
                conn.execute(text("CREATE TABLE a (id INTEGER PRIMARY KEY, v TEXT)"))
                conn.execute(text("CREATE TABLE b (id INTEGER PRIMARY KEY, v TEXT)"))
        with src.begin() as conn:
            for t in ("a", "b"):
                conn.execute(text(f"INSERT INTO {t} (id, v) VALUES (:i, 'x')"), [{"i": i} for i in range(1, 4001)])

        result = DumpOrchestrator(
            DumpConfig(
                source_engine=src,
                target_engine=dst,
                output_dir=tmp_path,
                chunk_size=100,
                parallel_pk_ranges=4,
                max_parallel_tables=2,
            )
        ).run()

        assert {r.status for r in result.table_results} == {"success"}
        with dst.connect() as conn:
            assert [conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in ("a", "b")] == [4000, 4000]
        src.dispose()
        dst.dispose()


class TestResolveRangeCount:
    def _orch(self, cap: int | None) -> DumpOrchestrator:
        def _engine() -> MagicMock:
            eng = MagicMock()
            if cap is None:
                eng.pool.size = "x"
            else:
                eng.pool.size = MagicMock(return_value=cap)
                eng.pool._max_overflow = 0
            return eng

        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = DumpConfig(source_engine=_engine(), target_engine=_engine())
        return orch

    def test_requested_1_returns_1(self):
        assert self._orch(10)._resolve_range_count(1, 4) == 1

    def test_degrades_so_product_fits_pool(self, caplog):
        # cap=8, table_workers=4 → allowed=2; requested=5 → degrada a 2
        with caplog.at_level("WARNING"):
            assert self._orch(8)._resolve_range_count(5, 4) == 2
        assert "degrada" in caplog.text.lower()

    def test_respects_when_product_fits(self):
        assert self._orch(20)._resolve_range_count(4, 4) == 4

    def test_respects_when_capacity_unknown(self):
        assert self._orch(None)._resolve_range_count(4, 4) == 4


class TestDetectPkRangeCol:
    def _orch(self, pk_cols: list[str], col_types: dict[str, object]) -> DumpOrchestrator:
        from sqlalchemy import Integer, String

        insp = MagicMock()
        insp.get_pk_constraint.return_value = {"constrained_columns": pk_cols}

        type_objs = {"int": Integer(), "str": String()}

        def _get_columns(table, schema=None):
            return [{"name": name, "type": type_objs[col_types[name]]} for name in col_types]

        insp.get_columns.side_effect = _get_columns
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = DumpConfig(source_engine=_make_engine(), target_engine=_make_engine())
        orch._src_insp = insp
        return orch

    def test_single_integer_pk_in_common_returns_col(self):
        orch = self._orch(["id"], {"id": "int", "name": "str"})
        assert orch._detect_pk_range_col("t", ["id", "name"]) == "id"

    def test_composite_pk_returns_none(self):
        orch = self._orch(["a", "b"], {"a": "int", "b": "int"})
        assert orch._detect_pk_range_col("t", ["a", "b"]) is None

    def test_non_integer_pk_returns_none(self):
        orch = self._orch(["code"], {"code": "str"})
        assert orch._detect_pk_range_col("t", ["code"]) is None

    def test_pk_not_in_common_returns_none(self):
        orch = self._orch(["id"], {"id": "int"})
        assert orch._detect_pk_range_col("t", ["name"]) is None


class TestLoadInPkRanges:
    def _orch(self, **cfg: object) -> DumpOrchestrator:
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = DumpConfig(source_engine=_make_engine(), target_engine=_make_engine(), **cfg)  # type: ignore[arg-type]
        orch._reset_audit_tracking()
        return orch

    def test_propagates_audit_strict_and_accumulates_loader_audit_failures(self):
        orch = self._orch(bulk_audit_strict=True)
        conn = orch._cfg.source_engine.connect.return_value
        conn.execute.return_value.one.return_value = (1, 9)

        from util_bbdd.bulk import ParallelLoadResult, PartitionResult

        with patch("util_bbdd.dump.orchestrator.ParallelBulkLoader") as loader_cls:
            loader_cls.return_value.load.return_value = ParallelLoadResult(
                partition_results=[
                    PartitionResult(
                        index=0,
                        rows=5,
                        elapsed_seconds=0.1,
                        audit_failures=2,
                        audited_rows=3,
                        unaudited_committed_rows=2,
                    ),
                    PartitionResult(
                        index=1,
                        rows=4,
                        elapsed_seconds=0.1,
                        audit_failures=1,
                        audited_rows=4,
                        audit_uncommitted_records=1,
                    ),
                ]
            )
            orch._load_in_pk_ranges("t", ["id"], {"id": "id"}, "id", "t", 2)
            orch._load_in_pk_ranges("t", ["id"], {"id": "id"}, "id", "t", 2)  # se acumula entre tablas

        assert loader_cls.call_args.kwargs["audit_strict"] is True
        counters = orch._audit_counters()
        assert (
            counters.audit_failures,
            counters.audited_rows,
            counters.unaudited_committed_rows,
            counters.audit_uncommitted_records,
        ) == (6, 14, 4, 2)

    def test_empty_table_returns_no_errors(self):
        orch = self._orch()
        conn = orch._cfg.source_engine.connect.return_value
        conn.execute.return_value.one.return_value = (None, None)

        with patch("util_bbdd.dump.orchestrator.ParallelBulkLoader") as loader_cls:
            errors = orch._load_in_pk_ranges("t", ["id"], {"id": "id"}, "id", "t", 3)

        assert errors == []
        # Tabla vacía: no se construye el loader
        loader_cls.assert_not_called()

    def test_delegates_to_parallel_loader_with_one_reader_per_range(self):
        orch = self._orch()
        conn = orch._cfg.source_engine.connect.return_value
        conn.execute.return_value.one.return_value = (1, 9)

        from util_bbdd.bulk import ParallelLoadResult

        with patch("util_bbdd.dump.orchestrator.ParallelBulkLoader") as loader_cls:
            loader = loader_cls.return_value
            loader.load.return_value = ParallelLoadResult(total_rows=9, partition_errors=[])
            errors = orch._load_in_pk_ranges("t", ["id", "name"], {"id": "id", "name": "name"}, "id", "t", 3)

        assert errors == []
        # ParallelBulkLoader construido con el engine destino y max_workers = nº de rangos
        assert loader_cls.call_args.args[0] is orch._cfg.target_engine
        assert loader_cls.call_args.kwargs["max_workers"] == 3
        # load() recibe la tabla destino y un lector por rango (3 rangos para [1,9] con n=3)
        tabla_arg, readers = loader.load.call_args.args
        assert tabla_arg == "t"
        assert len(readers) == 3

    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
    def test_range_readers_emit_correct_where_sql(self, mock_read_sql):
        orch = self._orch()
        conn = orch._cfg.source_engine.connect.return_value
        conn.execute.return_value.one.return_value = (1, 9)

        captured: list = []

        from util_bbdd.bulk import ParallelLoadResult

        def _capture(tabla, readers, **kwargs):
            captured.extend(readers)
            return ParallelLoadResult()

        with patch("util_bbdd.dump.orchestrator.ParallelBulkLoader") as loader_cls:
            loader_cls.return_value.load.side_effect = _capture
            orch._load_in_pk_ranges("t", ["id", "name"], {"id": "id", "name": "name"}, "id", "t", 3)

        # Invocar cada lector consume _read_chunks con el WHERE de rango parametrizado (args: conn, sql, chunk, params)
        for reader in captured:
            list(reader())
        range_sqls = [str(c.args[1]) for c in mock_read_sql.call_args_list]
        assert len(range_sqls) == 3
        assert all(">= :lo" in s for s in range_sqls)
        assert any("< :hi" in s for s in range_sqls)
        assert any("<= :hi" in s for s in range_sqls)


class TestLoadWholeTable:
    """``_load_whole_table`` delega en ``bulk_insert_from_chunks`` (resolución única)."""

    def _orch(self) -> DumpOrchestrator:
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = DumpConfig(source_engine=_make_engine(), target_engine=_make_engine())
        return orch

    def test_delegates_to_bulk_insert_from_chunks(self):
        import pandas as pd

        orch = self._orch()
        crud = MagicMock()
        crud.bulk_insert_from_chunks.return_value = 4
        chunks = [pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})]

        with patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter(chunks)):
            errors = orch._load_whole_table("t", ["id", "name"], {"id": "id", "name": "name"}, "dbo.t", crud)

        assert errors == []
        # Resolución única por tabla: un solo bulk_insert_from_chunks, sin bucle de bulk_insert_from_df
        crud.bulk_insert_from_chunks.assert_called_once()
        assert crud.bulk_insert_from_chunks.call_args.args[1] == "dbo.t"
        crud.bulk_insert_from_df.assert_not_called()

    def test_renames_columns_lazily_per_chunk(self):
        import pandas as pd

        orch = self._orch()
        crud = MagicMock()
        captured: list[pd.DataFrame] = []
        crud.bulk_insert_from_chunks.side_effect = lambda gen, *a, **k: (captured.extend(list(gen)), 0)[1]
        chunks = [pd.DataFrame({"UserID": [1], "Name": ["a"]})]

        with patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter(chunks)):
            orch._load_whole_table("t", ["UserID", "Name"], {"UserID": "userid", "Name": "name"}, "t", crud)

        assert len(captured) == 1
        assert list(captured[0].columns) == ["userid", "name"]


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
        orch = self._make_orchestrator("oracle")
        orch._cleanup(["customers", "orders"], skip=set())
        sql_stmts = self._executed_sql(orch)
        assert all("TRUNCATE TABLE" in s for s in sql_stmts)
        assert len(sql_stmts) == 2

    def test_postgresql_truncates_all_tables_in_one_statement(self):
        """PD-03: tabla a tabla, PostgreSQL rechaza truncar una tabla referenciada por FK (orders → customers)."""
        orch = self._make_orchestrator("postgresql")
        orch._cleanup(["orders", "customers"], skip=set())
        assert self._executed_sql(orch) == ["TRUNCATE TABLE orders, customers"]

    def test_postgresql_falls_back_to_table_by_table_if_joint_truncate_fails(self):
        """Una FK desde una tabla ajena al volcado hace fallar el TRUNCATE conjunto (sin CASCADE): se limpia como antes."""
        orch = self._make_orchestrator("postgresql")
        conn = orch._cfg.target_engine.connect.return_value.__enter__.return_value  # type: ignore[attr-defined]
        conn.execute.side_effect = [SQLAlchemyError("referenced by external table"), None, None]
        orch._cleanup(["orders", "customers"], skip=set())
        assert self._executed_sql(orch) == [
            "TRUNCATE TABLE orders, customers",
            "TRUNCATE TABLE orders",
            "TRUNCATE TABLE customers",
        ]
        conn.rollback.assert_called_once()

    def test_postgresql_joint_truncate_uses_target_schema(self):
        orch = self._make_orchestrator("postgresql")
        orch._cfg.target_schema = "dst"
        orch._cleanup(["orders", "customers"], skip=set())
        assert self._executed_sql(orch) == ["TRUNCATE TABLE dst.orders, dst.customers"]

    def test_delete_used_for_sqlite(self):
        """SQLite no tiene TRUNCATE TABLE: fallaba con un WARNING y el destino no se limpiaba."""
        orch = self._make_orchestrator("sqlite")
        orch._cleanup(["customers", "orders"], skip=set())
        sql_stmts = self._executed_sql(orch)
        assert len(sql_stmts) == 2
        assert all(s.startswith("DELETE FROM") for s in sql_stmts)

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
            patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([])),
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
# DumpOrchestrator._sync_pk_sequences — nombre lógico con target_schema (PD-02)
# ---------------------------------------------------------------------------


class TestSyncPkSequencesLogicalName:
    def _make_orchestrator(self, target_schema: str | None) -> DumpOrchestrator:
        cfg = DumpConfig(source_engine=_make_engine(), target_engine=_make_engine(), target_schema=target_schema)
        orch = DumpOrchestrator.__new__(DumpOrchestrator)
        orch._cfg = cfg
        return orch

    def _crud(self, cached: list[str]) -> MagicMock:
        crud = MagicMock()
        crud._table_cache = dict.fromkeys(cached, MagicMock())
        crud.sync_pk_sequences.return_value = [MagicMock(status="synced")]
        return crud

    def test_target_schema_syncs_tables_cached_by_logical_name(self):
        """Antes: se filtraba 'customers' contra la clave 'dst.customers' y no se sincronizaba nada (devolvía None)."""
        orch = self._make_orchestrator("dst")
        crud = self._crud(["dst.customers", "dst.orders"])

        results = orch._sync_pk_sequences(crud=crud, effective_dst_order=["customers", "orders"])

        crud.sync_pk_sequences.assert_called_once_with(["dst.customers", "dst.orders"])
        assert results is not None

    def test_without_target_schema_uses_bare_names(self):
        orch = self._make_orchestrator(None)
        crud = self._crud(["customers"])

        orch._sync_pk_sequences(crud=crud, effective_dst_order=["customers", "orders"])

        crud.sync_pk_sequences.assert_called_once_with(["customers"])

    def test_sqlite_dump_with_target_schema_runs_pk_sync(self, tmp_path: Path):
        """E2E: volcado real a un esquema adjunto de SQLite; la Fase 5a recibe la tabla con su nombre lógico.

        SQLite no tiene contadores que sincronizar (el resultado es ``[]``), así que se comprueba la llamada. Antes del
        arreglo, ``BulkCrud.sync_pk_sequences`` no se llamaba.
        """
        from sqlalchemy import create_engine, event, text

        from util_bbdd.bulk import BulkCrud

        src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
        dst = create_engine(f"sqlite:///{tmp_path / 'main.db'}")
        stg_path = (tmp_path / "stg.db").as_posix()

        @event.listens_for(dst, "connect")
        def _attach(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
            dbapi_conn.execute(f"ATTACH DATABASE '{stg_path}' AS stg")

        with src.begin() as conn:
            conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"))
            conn.execute(text("INSERT INTO items VALUES (1, 'a'), (2, 'b')"))
        with dst.begin() as conn:
            conn.execute(text("CREATE TABLE stg.items (id INTEGER PRIMARY KEY, name TEXT)"))

        with patch.object(BulkCrud, "sync_pk_sequences", autospec=True, return_value=[]) as spy:
            result = DumpOrchestrator(
                DumpConfig(source_engine=src, target_engine=dst, target_schema="stg", output_dir=tmp_path)
            ).run()

        assert [r.status for r in result.table_results] == ["success"]
        spy.assert_called_once()
        assert spy.call_args.args[1] == ["stg.items"]
        src.dispose()
        dst.dispose()


# ---------------------------------------------------------------------------
# DumpOrchestrator — propagación de target_schema al INSERT (T4)
# ---------------------------------------------------------------------------


class TestTargetSchemaPropagation:
    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("util_bbdd.dump.orchestrator._read_chunks")
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

        # El volcado delega en bulk_insert_from_chunks(generador, dest_logical)
        call_args = mock_crud.bulk_insert_from_chunks.call_args
        assert call_args is not None
        tabla_arg = call_args[0][1]
        assert tabla_arg == "staging.orders"

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("util_bbdd.dump.orchestrator._read_chunks")
    @patch("util_bbdd.dump.orchestrator.BulkCrud")
    def test_dest_table_uses_logical_name_for_bulk_insert(
        self, mock_bulk_cls, mock_read_sql, mock_report, mock_mgr_cls
    ):
        """TC1: bulk_insert_from_chunks recibe nombre lógico (schema.tabla sin quoting de dialecto).
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

        call_args = mock_crud.bulk_insert_from_chunks.call_args
        assert call_args is not None
        tabla_arg = call_args[0][1]
        # Debe ser el nombre lógico (schema.tabla), NO la forma quoted del dialecto
        assert tabla_arg == "order.user"

    @patch("util_bbdd.dump.orchestrator.ConstraintManager")
    @patch("util_bbdd.dump.reporters.DumpReporter.generate", return_value=Path("r.xlsx"))
    @patch("util_bbdd.dump.orchestrator._read_chunks")
    @patch("util_bbdd.dump.orchestrator.BulkCrud")
    def test_chunk_error_sets_error_status_and_correct_row_count(
        self, mock_bulk_cls, mock_read_sql, mock_report, mock_mgr_cls
    ):
        """TC5: error durante la carga de la tabla → status=error con el mensaje propagado.

        Con la delegación en ``bulk_insert_from_chunks`` (resolución única por tabla),
        un fallo en cualquier chunk aborta la inserción de la tabla con una única
        llamada que propaga el ``SQLAlchemyError``.
        """
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
        mock_crud.bulk_insert_from_chunks.side_effect = SQLAlchemyError("FK violation")
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
        assert mock_crud.bulk_insert_from_chunks.call_count == 1


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
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
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
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
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
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
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
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
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
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
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
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
    @patch("util_bbdd.dump.orchestrator.BulkCrud")
    def test_process_table_delegates_to_bulk_insert_from_chunks(
        self, mock_bulk_cls, mock_read_sql, mock_report, mock_mgr_cls
    ) -> None:
        """El procesado de la tabla delega en bulk_insert_from_chunks (gestiona su propia sesión)."""
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

        mock_crud.bulk_insert_from_chunks.assert_called_once()


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
    @patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([]))
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


class TestBuildAuditSummary:
    """H3 (audit-code 2026-09-25): el CSV guarda segundos y ``dump_inicio`` lleva microsegundos."""

    _HEADER = "timestamp\ttabla\tmotor\toperacion\ttotal_filas\ttiempo_seg\tsql\n"

    def _write_csv(self, path: Path, *timestamps: str) -> Path:
        rows = "".join(f"{ts}\torders\tPOSTGRESQL\tINSERT\t10\t0,500\tNo\n" for ts in timestamps)
        path.write_text(self._HEADER + rows, encoding="utf-8")
        return path

    def test_counts_operation_finished_in_the_same_second_as_the_start(self, tmp_path: Path) -> None:
        csv_path = self._write_csv(tmp_path / "audit.csv", "2026-09-25 10:00:00")

        summary = DumpOrchestrator._build_audit_summary(csv_path, datetime(2026, 9, 25, 10, 0, 0, 700_000))

        assert summary is not None
        assert summary.total_operaciones == 1
        assert summary.total_filas == 10

    def test_failures_without_csv_entries_still_return_a_summary(self, tmp_path: Path) -> None:
        # Si ninguna escritura funcionó no hay filas en el CSV; devolver None ocultaría justo el problema.
        summary = DumpOrchestrator._build_audit_summary(
            tmp_path / "no-existe.csv", datetime(2026, 9, 25, 10, 0, 0), audit_failures=4
        )

        assert summary is not None
        assert summary.audit_failures == 4
        assert summary.total_operaciones == 0

    def test_failures_are_added_to_a_summary_with_entries(self, tmp_path: Path) -> None:
        csv_path = self._write_csv(tmp_path / "audit.csv", "2026-09-25 10:00:01")

        summary = DumpOrchestrator._build_audit_summary(csv_path, datetime(2026, 9, 25, 10, 0, 0), audit_failures=1)

        assert summary is not None
        assert (summary.total_operaciones, summary.audit_failures) == (1, 1)

    @pytest.mark.parametrize(
        "incidencia",
        [{"unaudited_committed_rows": 10}, {"audit_uncommitted_records": 1}],
        ids=["unaudited", "uncommitted"],
    )
    def test_new_anomaly_counters_also_return_a_summary_without_entries(
        self, tmp_path: Path, incidencia: dict[str, int]
    ) -> None:
        summary = DumpOrchestrator._build_audit_summary(
            tmp_path / "no-existe.csv", datetime(2026, 9, 25, 10, 0, 0), **incidencia
        )

        assert summary is not None
        assert summary.total_operaciones == 0
        for campo, valor in incidencia.items():
            assert getattr(summary, campo) == valor

    def test_audited_rows_alone_without_entries_returns_none(self, tmp_path: Path) -> None:
        assert (
            DumpOrchestrator._build_audit_summary(
                tmp_path / "no-existe.csv", datetime(2026, 9, 25, 10, 0, 0), audited_rows=10
            )
            is None
        )

    def test_counters_are_copied_to_a_summary_with_entries(self, tmp_path: Path) -> None:
        csv_path = self._write_csv(tmp_path / "audit.csv", "2026-09-25 10:00:01")

        summary = DumpOrchestrator._build_audit_summary(
            csv_path,
            datetime(2026, 9, 25, 10, 0, 0),
            audited_rows=10,
            unaudited_committed_rows=5,
            audit_uncommitted_records=0,
        )

        assert summary is not None
        assert (summary.total_filas, summary.audited_rows, summary.unaudited_committed_rows) == (10, 10, 5)

    def test_warns_when_the_csv_and_the_counters_disagree(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Otro proceso escribió en el mismo CSV durante el volcado: el CSV suma 20 y el volcado escribió 10.
        csv_path = self._write_csv(tmp_path / "audit.csv", "2026-09-25 10:00:01", "2026-09-25 10:00:02")

        with caplog.at_level("WARNING"):
            summary = DumpOrchestrator._build_audit_summary(csv_path, datetime(2026, 9, 25, 10, 0, 0), audited_rows=10)

        assert summary is not None and (summary.total_filas, summary.audited_rows) == (20, 10)
        assert any("el CSV suma 20 filas" in r.getMessage() for r in caplog.records)

    def test_no_warning_when_they_agree_or_counters_are_unknown(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        csv_path = self._write_csv(tmp_path / "audit.csv", "2026-09-25 10:00:01")

        with caplog.at_level("WARNING"):
            DumpOrchestrator._build_audit_summary(csv_path, datetime(2026, 9, 25, 10, 0, 0), audited_rows=10)
            DumpOrchestrator._build_audit_summary(csv_path, datetime(2026, 9, 25, 10, 0, 0))

        assert not any("el CSV suma" in r.getMessage() for r in caplog.records)

    def test_no_failures_and_no_csv_returns_none(self, tmp_path: Path) -> None:
        assert DumpOrchestrator._build_audit_summary(tmp_path / "no-existe.csv", datetime(2026, 9, 25)) is None

    def test_excludes_operations_from_earlier_seconds(self, tmp_path: Path) -> None:
        csv_path = self._write_csv(tmp_path / "audit.csv", "2026-09-25 09:59:59", "2026-09-25 10:00:01")

        summary = DumpOrchestrator._build_audit_summary(csv_path, datetime(2026, 9, 25, 10, 0, 0, 700_000))

        assert summary is not None
        assert summary.total_operaciones == 1
