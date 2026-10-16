"""Regla única de capacidad del pool (v0.18.0): ``size + max_overflow`` en ``ParallelBulkLoader`` y ``dump``."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import create_engine, event, text

from util_bbdd.bulk import ParallelBulkLoader
from util_bbdd.bulk._support.pool import pool_capacity
from util_bbdd.bulk.options import ParallelOptions
from util_bbdd.dump import DumpOrchestrator

pytestmark = pytest.mark.unit


def _engine(size: Any, overflow: Any = 0) -> MagicMock:
    engine = MagicMock()
    engine.pool.size = MagicMock(return_value=size)
    engine.pool._max_overflow = overflow
    return engine


@pytest.mark.parametrize(
    ("size", "overflow", "expected"),
    [
        (5, 10, 15),  # create_engine por defecto
        (5, 0, 5),
        (5, -1, None),  # max_overflow ilimitado: sin recorte (D-1)
        (5, MagicMock(), 5),  # overflow no entero (mocks): cuenta como 0
        ("5", 0, None),  # size() no entero: no determinable
        (True, 0, None),
    ],
)
def test_pool_capacity(size: Any, overflow: Any, expected: int | None) -> None:
    assert pool_capacity(_engine(size, overflow)) == expected


def test_pool_capacity_without_size_is_unknown() -> None:
    engine = MagicMock()
    engine.pool.size = "not-callable"
    assert pool_capacity(engine) is None
    assert pool_capacity(object()) is None  # type: ignore[arg-type]


def test_pool_without_max_overflow_attribute_counts_size_only() -> None:
    """``_max_overflow`` es privado de QueuePool: si faltara, la capacidad es ``size`` (no ``None``)."""

    class _Pool:
        def size(self) -> int:
            return 7

    engine = MagicMock()
    engine.pool = _Pool()
    assert pool_capacity(engine) == 7


def test_loader_and_dump_use_the_same_rule(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        loader = ParallelBulkLoader(_engine(5, 10), parallel=ParallelOptions(max_workers=12))
    assert loader._max_workers == 12  # antes: 5 (solo pool_size)
    assert DumpOrchestrator._pool_capacity(_engine(5, 10)) == 15
    assert ParallelBulkLoader(_engine(5, 2), parallel=ParallelOptions(max_workers=12))._max_workers == 7


def test_maintenance_worker_uses_a_single_connection(tmp_path: Path) -> None:
    """Guarda de la regla nueva: con ``disable_constraints=True`` cada worker reflejaba la tabla con la sesión ya abierta
    (dos conexiones a la vez); con ``size + max_overflow`` workers el pool podía agotarse."""
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
    in_use = {"now": 0, "max": 0}

    def _checkout(*_args: Any) -> None:
        in_use["now"] += 1
        in_use["max"] = max(in_use["max"], in_use["now"])

    def _checkin(*_args: Any) -> None:
        in_use["now"] -= 1

    event.listen(engine, "checkout", _checkout)
    event.listen(engine, "checkin", _checkin)
    loader = ParallelBulkLoader(engine, parallel=ParallelOptions(max_workers=1, disable_constraints=True))

    result = loader.load("t", [lambda: iter([pd.DataFrame({"id": [1, 2], "v": ["a", "b"]})])])

    assert result.partition_errors == []
    assert result.total_rows == 2
    assert in_use["max"] == 1
