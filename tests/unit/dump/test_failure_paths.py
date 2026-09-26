"""Caminos de error hallados en el audit-code de 2026-09-26 (A1, A2, A3).

- A1: si la escritura falla, la conexión de lectura no debe devolverse con el hilo de ``_prefetch`` vivo.
- A2: ``ParallelBulkLoader`` cierra el generador del lector aunque falle la escritura.
- A3: ``strip_strings=False`` no recorta subclases de ``str`` (``numpy.str_``).
"""

from __future__ import annotations

import threading
import time

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.bulk._execution.parallel_loader import ParallelBulkLoader, _closing_iterable
from util_bbdd.bulk.normalize import dataframe_to_sql_records
from util_bbdd.dump import DumpConfig, DumpOrchestrator

pytestmark = pytest.mark.unit


def _reader_threads_alive() -> int:
    return sum(1 for t in threading.enumerate() if t.name == "dump-prefetch" and t.is_alive())


class _RecordingConnection:
    """Conexión de origen simulada que anota, al salir del ``with``, si el hilo lector seguía vivo."""

    def __init__(self) -> None:
        self.alive_at_exit: int | None = None

    def __enter__(self) -> _RecordingConnection:
        return self

    def __exit__(self, *exc: object) -> None:
        self.alive_at_exit = _reader_threads_alive()


def test_read_connection_is_released_after_the_reader_thread_ends_when_writing_fails() -> None:
    """A1: antes, el ``with`` devolvía la conexión con el hilo de ``_prefetch`` aún leyendo."""
    source = MagicMock()
    source.dialect.name = "postgresql"
    source.dialect.identifier_preparer.quote.side_effect = lambda n: n
    conn = _RecordingConnection()
    source.connect.return_value = conn
    orch = DumpOrchestrator.__new__(DumpOrchestrator)
    orch._cfg = DumpConfig(source_engine=source, target_engine=MagicMock(), write_batch_size=1)

    def slow_chunks(*_args: Any, **_kwargs: Any) -> Iterator[pd.DataFrame]:
        for i in range(1000):
            time.sleep(0.01)  # el lector sigue produciendo mientras el hilo principal falla al escribir
            yield pd.DataFrame({"id": [i]}, dtype=object)

    def failing_write(chunks: Iterator[pd.DataFrame], _table: str) -> int:
        next(iter(chunks))
        raise SQLAlchemyError("fallo al escribir")

    crud = MagicMock()
    crud.bulk_insert_from_chunks.side_effect = failing_write
    with patch("util_bbdd.dump.orchestrator._read_chunks", side_effect=slow_chunks):
        errors = orch._load_whole_table("t", ["id"], {"id": "id"}, "t", crud)

    assert errors == ["fallo al escribir"]
    assert conn.alive_at_exit == 0
    assert _reader_threads_alive() == 0


class TestClosingIterable:
    def test_closes_the_generator_on_error(self) -> None:
        closed: list[bool] = []

        def gen() -> Iterator[pd.DataFrame]:
            try:
                yield pd.DataFrame({"id": [1]})
                yield pd.DataFrame({"id": [2]})
            finally:
                closed.append(True)

        with pytest.raises(RuntimeError), _closing_iterable(gen()) as chunks:
            next(iter(chunks))
            raise RuntimeError("fallo al escribir")
        assert closed == [True]

    def test_plain_iterables_are_accepted(self) -> None:
        with _closing_iterable([pd.DataFrame({"id": [1]})]) as chunks:
            assert len(list(chunks)) == 1


def test_parallel_loader_closes_the_reader_when_the_write_fails() -> None:
    """A2: el generador del lector (con su conexión de origen) se cierra aunque falle la escritura."""
    closed: list[bool] = []

    def reader() -> Iterator[pd.DataFrame]:
        try:
            yield pd.DataFrame({"id": [1]})
            yield pd.DataFrame({"id": [2]})
        finally:
            closed.append(True)

    def failing_write(chunks: Any, *_args: Any, **_kwargs: Any) -> int:
        next(iter(chunks))
        raise SQLAlchemyError("fallo al escribir")

    loader = ParallelBulkLoader.__new__(ParallelBulkLoader)
    loader._disable_constraints = False
    crud = MagicMock()
    crud.bulk_insert_from_chunks.side_effect = failing_write
    with pytest.raises(SQLAlchemyError):
        loader._run_attempt(crud, "t", reader, False, False, False)
    assert closed == [True]


def test_strip_strings_false_keeps_spaces_of_numpy_strings() -> None:
    """A3: ``numpy.str_`` es subclase de ``str``; antes se recortaba con ``strip_strings=False``."""
    df = pd.DataFrame({"s": pd.Series([np.str_("  a  "), "  b  "], dtype=object)})
    records = dataframe_to_sql_records(df, strip_strings=False)
    assert records == [{"s": "  a  "}, {"s": "  b  "}]
    assert type(records[0]["s"]) is str
