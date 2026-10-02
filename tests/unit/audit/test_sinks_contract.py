"""Contrato de ``AuditSink``: toda implementación es sustituible por otra (LSP).

Cada implementación nueva se añade a ``SINK_FACTORIES``; los tests de contrato se ejecutan con todas.
"""

from __future__ import annotations

import threading

from collections.abc import Callable
from pathlib import Path

import pytest

from util_bbdd.audit import (
    AuditEvent,
    AuditEventSource,
    AuditSink,
    JsonLinesAuditSink,
    MemoryAuditSink,
    NullAuditSink,
)

SinkFactory = Callable[[Path], AuditSink]

SINK_FACTORIES: dict[str, SinkFactory] = {
    "null": lambda _tmp: NullAuditSink(),
    "memory": lambda _tmp: MemoryAuditSink(),
    "jsonl": lambda tmp: JsonLinesAuditSink(tmp / "auditoria.jsonl"),
}


@pytest.fixture(params=sorted(SINK_FACTORIES))
def sink(request: pytest.FixtureRequest, tmp_path: Path) -> AuditSink:
    return SINK_FACTORIES[request.param](tmp_path)


def _event(n: int) -> AuditEvent:
    return AuditEvent.now(source="bulk", kind="operation", status="ok", target=f"t{n}", rows=n)


def test_cumple_el_protocol(sink: AuditSink) -> None:
    assert isinstance(sink, AuditSink)


def test_write_vacio_no_falla(sink: AuditSink) -> None:
    sink.write([])


def test_close_es_idempotente_y_write_tras_close_falla(sink: AuditSink) -> None:
    sink.write([_event(1)])
    sink.close()
    sink.close()

    with pytest.raises(ValueError, match="cerrado"):
        sink.write([_event(2)])


def test_write_desde_varios_hilos(sink: AuditSink) -> None:
    def worker(base: int) -> None:
        for n in range(50):
            sink.write([_event(base + n), _event(base + n)])

    threads = [threading.Thread(target=worker, args=(i * 1000,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if isinstance(sink, AuditEventSource):
        events = sink.events()
        assert len(events) == 8 * 50 * 2
        # Atómico por llamada: los dos eventos de cada write quedan juntos.
        assert all(events[i].rows == events[i + 1].rows for i in range(0, len(events), 2))


def test_memory_es_event_source_y_devuelve_copia() -> None:
    sink = MemoryAuditSink()
    sink.write([_event(1)])

    events = sink.events()
    sink.write([_event(2)])

    assert isinstance(sink, AuditEventSource)
    assert [e.rows for e in events] == [1]
    assert [e.rows for e in sink.events()] == [1, 2]
