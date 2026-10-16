"""BulkCrud verifica las condiciones del motor una sola vez por engine (EngineReadinessAdvisor.report_once)."""

from __future__ import annotations

import logging
import threading

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from sqlalchemy import create_engine

from util_bbdd.bulk.crud import BulkCrud
from util_bbdd.bulk.options import AuditOptions

_LOGGER = "util_bbdd.connection.performance_advisor"
_HEADER = "ENGINE READINESS REPORT"


def _reports(caplog: pytest.LogCaptureFixture) -> int:
    return sum(1 for r in caplog.records if _HEADER in r.getMessage())


def test_many_bulkcrud_same_engine_single_report(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'bulk.sqlite'}")
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        for _ in range(5):
            BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))
    assert _reports(caplog) == 1
    engine.dispose()


def test_bulkcrud_in_parallel_threads_single_report(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    # Escenario de ParallelBulkLoader / dump: una BulkCrud por hilo sobre el mismo engine
    engine = create_engine(f"sqlite:///{tmp_path / 'bulk.sqlite'}")
    n_threads = 8
    barrier = threading.Barrier(n_threads)

    def _worker(_: int) -> BulkCrud:
        barrier.wait()
        return BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            list(pool.map(_worker, range(n_threads)))

    assert _reports(caplog) == 1
    engine.dispose()
