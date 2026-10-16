"""ParallelPlanner (v3.0.0): reglas de seguridad en todos los modos y reglas medidas en ``"auto"``."""

from __future__ import annotations

import pytest

from util_bbdd.bulk import ParallelPlan, ParallelPlanner, PlanInput
from util_bbdd.bulk._execution.parallel_planner import Operation, Workload
from util_bbdd.bulk.options import ParallelOptions

AUTO = ParallelOptions(mode="auto")
MANUAL = ParallelOptions(mode="manual", max_workers=6)


def _plan(
    dialect: str, operation: Operation = "insert", options: ParallelOptions = AUTO, **facts: object
) -> ParallelPlan:
    return ParallelPlanner.plan(PlanInput(dialect=dialect, operation=operation, options=options, **facts))  # type: ignore[arg-type]


class TestSafetyRules:
    def test_off_is_serial(self) -> None:
        assert _plan("mssql", options=ParallelOptions(mode="off"), rows=10**7).workers == 1

    def test_manual_uses_the_requested_workers(self) -> None:
        plan = _plan("postgresql", options=MANUAL, rows=10**7)
        assert plan == ParallelPlan(6, ())

    def test_never_more_workers_than_partitions_or_rows(self) -> None:
        assert _plan("mssql", options=MANUAL, partitions=3).workers == 3
        assert _plan("mssql", options=MANUAL, rows=2).workers == 2

    @pytest.mark.parametrize("options", [MANUAL, AUTO])
    def test_sqlite_has_a_single_writer(self, options: ParallelOptions) -> None:
        plan = _plan("sqlite", options=options, rows=10**7)
        assert plan.workers == 1
        assert "un solo escritor" in plan.reasons[0]

    def test_postgresql_update_without_staging_is_serial(self) -> None:
        plan = _plan("postgresql", "update", MANUAL, rows=10**7, staging_update=False)
        assert plan.workers == 1
        assert "privilegio TEMP" in plan.reasons[0]

    def test_pool_capacity_caps_the_workers(self) -> None:
        plan = _plan("mssql", options=MANUAL, pool_capacity=3)
        assert plan.workers == 3
        assert "capacidad del pool" in plan.reasons[0]


class TestMeasuredRules:
    def test_sql_server_insert_uses_four_workers(self) -> None:
        plan = _plan("mssql", rows=2_000_000)
        assert plan.workers == 4
        assert "2,4-2,8×" in plan.reasons[-1]

    @pytest.mark.parametrize("dialect", ["postgresql", "oracle"])
    def test_inserts_that_do_not_gain_are_serial(self, dialect: str) -> None:
        plan = _plan(dialect, rows=10**7)
        assert plan.workers == 1
        assert "no gana en paralelo" in plan.reasons[-1]

    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_mysql_family_delete_best_with_two_workers(self, dialect: str) -> None:
        plan = _plan(dialect, "delete", rows=1_000_000)
        assert plan.workers == 2
        assert "2 hilos, el mejor tiempo medido" in plan.reasons[-1]

    def test_unmeasured_combination_is_serial(self) -> None:
        plan = _plan("hsqldb", rows=10**7)
        assert plan.workers == 1
        assert "sin medición" in plan.reasons[-1]

    @pytest.mark.parametrize(("rows", "workers"), [(49_999, 1), (50_000, 4)])
    def test_insert_threshold_is_the_smallest_measured_volume(self, rows: int, workers: int) -> None:
        assert _plan("mssql", rows=rows).workers == workers

    def test_below_the_smallest_measured_volume_is_serial(self) -> None:
        plan = _plan("mssql", "update", rows=999_999)
        assert plan.workers == 1
        assert "menor volumen medido" in plan.reasons[-1]

    def test_min_rows_overrides_the_threshold(self) -> None:
        options = ParallelOptions(mode="auto", min_rows=1_000)
        assert _plan("mssql", "update", options, rows=5_000).workers == 4

    def test_unknown_volume_skips_the_threshold(self) -> None:
        plan = _plan("mssql", partitions=8)
        assert plan.workers == 4
        assert "volumen desconocido" in plan.reasons[0]

    def test_max_workers_is_the_ceiling(self) -> None:
        assert _plan("mssql", options=ParallelOptions(mode="auto", max_workers=2), rows=10**7).workers == 2

    @pytest.mark.parametrize("dialect", ["mysql", "mariadb", "postgresql"])
    def test_update_measured_with_staging_is_serial_without_it(self, dialect: str) -> None:
        assert _plan(dialect, "update", rows=10**7, staging_update=False).workers == 1

    def test_staging_flag_is_ignored_where_update_never_uses_it(self) -> None:
        assert _plan("mssql", "update", rows=10**7, staging_update=False).workers == 4

    @pytest.mark.parametrize(("dialect", "workers"), [("mssql", 4), ("postgresql", 1), ("mysql", 1), ("oracle", 1)])
    def test_dump_workload(self, dialect: str, workers: int) -> None:
        assert _plan(dialect, rows=3_500_000, workload="source").workers == workers

    def test_dump_workload_threshold(self) -> None:
        assert _plan("mssql", rows=1_000_000, workload="source").workers == 1


def test_rules_are_consistent() -> None:
    workloads: tuple[Workload, ...] = ("memory", "source")
    for (workload, _dialect, _operation), rule in ParallelPlanner.RULES.items():
        assert workload in workloads
        assert 1 <= rule.workers <= ParallelOptions().max_workers
        assert rule.min_rows >= 1
        assert rule.evidence
