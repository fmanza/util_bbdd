"""U-B2 (G36 de util_bbdd_web): ``ParallelPlan.atomic`` y ``ParallelOptions(require_atomic=True)``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk import BulkCrud, ParallelBulkLoader, ParallelPlan, ParallelPlanner, PlanInput
from util_bbdd.bulk._execution import parallel_planner
from util_bbdd.bulk.options import AuditOptions, BatchOptions, BulkOptions, ParallelOptions

pytestmark = pytest.mark.unit

MANUAL = ParallelOptions(mode="manual", max_workers=4)


def _plan(options: ParallelOptions = MANUAL, **facts: object) -> ParallelPlan:
    return ParallelPlanner.plan(PlanInput(dialect="mssql", operation="insert", options=options, **facts))  # type: ignore[arg-type]


class TestPlanner:
    def test_several_workers_are_not_atomic(self) -> None:
        plan = _plan(rows=10**6)
        assert (plan.workers, plan.parallel, plan.atomic) == (4, True, False)

    @pytest.mark.parametrize("options", [ParallelOptions(mode="off"), ParallelOptions(max_workers=1)])
    def test_one_worker_is_atomic(self, options: ParallelOptions) -> None:
        assert _plan(options, rows=10**6).atomic is True

    def test_safety_rules_keep_it_atomic(self) -> None:
        plan = ParallelPlanner.plan(PlanInput(dialect="sqlite", operation="insert", options=MANUAL, rows=10**6))
        assert (plan.workers, plan.atomic) == (1, True)

    def test_periodic_commits_are_never_atomic(self) -> None:
        assert _plan(ParallelOptions(mode="off"), periodic_commits=True).atomic is False

    def test_several_partitions_in_one_worker_are_not_atomic(self) -> None:
        """``ParallelBulkLoader``: con un hilo, las particiones se cargan una tras otra, cada una en su transacción."""
        plan = _plan(ParallelOptions(max_workers=1), partitions=3)
        assert (plan.workers, plan.atomic) == (1, False)
        assert _plan(ParallelOptions(max_workers=1), partitions=1).atomic is True

    def test_require_atomic_forces_one_worker(self) -> None:
        plan = _plan(ParallelOptions(mode="auto", require_atomic=True), rows=10**7)
        assert (plan.workers, plan.atomic) == (1, True)
        assert plan.reasons == ("require_atomic=True: en serie, en una transacción",)

    def test_hand_made_plan_is_not_atomic_unless_said(self) -> None:
        assert ParallelPlan(1).atomic is False
        assert ParallelPlan(1, (), atomic=True).atomic is True


class TestOptions:
    def test_require_atomic_must_be_bool(self) -> None:
        with pytest.raises(ValueError, match="require_atomic"):
            ParallelOptions(require_atomic="si")  # type: ignore[arg-type]

    def test_require_atomic_rejects_periodic_commits(self) -> None:
        with pytest.raises(ValueError, match="commit_every_n_chunks"):
            BulkOptions(batch=BatchOptions(commit_every_n_chunks=2), parallel=ParallelOptions(require_atomic=True))

    def test_loader_rejects_require_atomic(self) -> None:
        with pytest.raises(ValueError, match="solo aplica a BulkCrud"):
            ParallelBulkLoader(create_engine("sqlite://"), parallel=ParallelOptions(require_atomic=True))


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}", connect_args={"timeout": 30})
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, v TEXT)"))
    yield engine
    engine.dispose()


def _crud(engine: Engine, parallel: ParallelOptions | None, **batch: int) -> BulkCrud:
    return BulkCrud(engine, batch=BatchOptions(**batch), audit=AuditOptions(warn_if_disabled=False), parallel=parallel)


class TestBulkCrud:
    def test_serial_plans(self, engine: Engine) -> None:
        assert _crud(engine, None).parallel_plan("insert", 10).atomic is True
        assert _crud(engine, None, commit_every_n_chunks=2).parallel_plan("insert", 10).atomic is False
        assert _crud(engine, MANUAL).parallel_plan("update", 10).atomic is True  # SQLite: en serie

    @pytest.mark.usefixtures("several_writers")
    def test_parallel_plan_and_require_atomic(self, engine: Engine) -> None:
        df = pd.DataFrame({"id": range(1, 21), "v": "x"})
        parallel = _crud(engine, MANUAL)
        assert parallel.parallel_plan("insert", len(df)).atomic is False

        atomic = _crud(engine, ParallelOptions(max_workers=4, require_atomic=True))
        assert atomic.parallel_plan("insert", len(df)).atomic is True
        atomic.bulk_insert_from_df(df, "items", generar_sql=False)
        assert atomic.last_parallel_result is None  # en serie, una transacción


@pytest.fixture
def several_writers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deja que el planificador use varios hilos con SQLite (como ``test_crud_parallel``)."""
    monkeypatch.setattr(parallel_planner, "SINGLE_WRITER_DIALECTS", frozenset())
