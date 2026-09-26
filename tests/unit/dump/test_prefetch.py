"""Q3 (performance-audit de dump 2026-09-25): solape de lectura y escritura con un hilo lector y cola acotada."""

from __future__ import annotations

import threading
import time

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from util_bbdd.dump.orchestrator import DumpConfig, DumpOrchestrator, _prefetch

pytestmark = pytest.mark.unit


def _alive_readers() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name == "dump-prefetch"]


def test_yields_all_items_in_order():
    assert list(_prefetch(iter(range(50)))) == list(range(50))
    assert _alive_readers() == []


def test_empty_source():
    assert list(_prefetch(iter([]))) == []


def test_reader_error_is_raised_after_previous_items():
    def source() -> Iterator[int]:
        yield 1
        yield 2
        raise ValueError("fallo leyendo")

    received: list[int] = []
    with pytest.raises(ValueError, match="fallo leyendo"):
        for item in _prefetch(source()):
            received.append(item)
    assert received == [1, 2]
    assert _alive_readers() == []


def test_consumer_stop_ends_reader_and_bounds_reading():
    read: list[int] = []

    def source() -> Iterator[int]:
        for i in range(1000):
            read.append(i)
            yield i

    gen = _prefetch(source(), depth=2)
    assert next(gen) == 0
    time.sleep(0.2)  # el lector llena la cola y queda esperando
    gen.close()  # lo que ocurre cuando falla la escritura

    assert _alive_readers() == []
    # 1 entregado + 2 en cola + 1 esperando a entrar: nunca se lee la tabla entera.
    assert len(read) <= 5


def test_consumer_exception_joins_reader():
    def consume() -> None:
        for item in _prefetch(iter(range(100))):
            if item == 3:
                raise RuntimeError("fallo escribiendo")

    with pytest.raises(RuntimeError, match="fallo escribiendo"):
        consume()
    assert _alive_readers() == []


@pytest.mark.parametrize(("source_dialect", "used"), [("postgresql", True), ("oracle", True), ("sqlite", False)])
def test_load_whole_table_uses_prefetch_by_source_dialect(source_dialect: str, used: bool):
    src = MagicMock()
    src.dialect.name = source_dialect
    src.dialect.identifier_preparer.quote.side_effect = lambda n: n
    orch = DumpOrchestrator.__new__(DumpOrchestrator)
    orch._cfg = DumpConfig(source_engine=src, target_engine=MagicMock())
    crud = MagicMock()

    with (
        patch("util_bbdd.dump.orchestrator._read_chunks", return_value=iter([])),
        patch("util_bbdd.dump.orchestrator._prefetch", side_effect=lambda it: it) as spy,
    ):
        orch._load_whole_table("t", ["id"], {"id": "id"}, "t", crud)

    assert spy.called is used
    crud.bulk_insert_from_chunks.assert_called_once()
