"""``JsonLinesAuditSink`` (H-04): una línea JSON por evento, ISO 8601 con zona, lock por ruta compartido."""

from __future__ import annotations

import json
import logging
import threading

from pathlib import Path

import pytest

from util_bbdd.audit import AuditEvent, JsonLinesAuditSink
from util_bbdd.audit.locks import path_lock


def _event(n: int) -> AuditEvent:
    return AuditEvent.now(
        source="bulk", kind="operation", status="ok", target=f"t{n}", rows=n, elapsed_s=0.5, attributes={"n": n}
    )


def _lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_una_linea_por_evento_con_todos_los_campos(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    sink = JsonLinesAuditSink(path)

    sink.write([_event(1), _event(2)])
    sink.write([_event(3)])

    data = _lines(path)
    assert [d["rows"] for d in data] == [1, 2, 3]
    assert data[0]["elapsed_s"] == 0.5  # punto decimal, número
    assert str(data[0]["timestamp"]).endswith("+00:00")  # con zona
    assert data[0]["attributes"] == {"n": 1}
    assert set(data[0]) == set(_event(0).as_dict())


def test_dos_instancias_misma_ruta_comparten_lock_y_no_intercalan(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    sinks = [JsonLinesAuditSink(path), JsonLinesAuditSink(path)]
    assert sinks[0]._file_lock is sinks[1]._file_lock is path_lock(path)

    def worker(sink: JsonLinesAuditSink, base: int) -> None:
        for n in range(100):
            sink.write([_event(base + n), _event(base + n)])

    threads = [threading.Thread(target=worker, args=(sinks[i % 2], i * 1000)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    rows = [d["rows"] for d in _lines(path)]
    assert len(rows) == 6 * 100 * 2
    assert all(rows[i] == rows[i + 1] for i in range(0, len(rows), 2))  # cada write queda junto


def test_aparta_un_fichero_que_no_es_de_eventos(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = tmp_path / "a.jsonl"
    path.write_text("timestamp,tabla\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="util_bbdd.audit.sinks"):
        JsonLinesAuditSink(path).write([_event(1)])

    assert len(list(tmp_path.glob("a.invalid-*.jsonl"))) == 1
    assert [d["rows"] for d in _lines(path)] == [1]
    assert any("se ha apartado" in r.getMessage() for r in caplog.records)


def test_conserva_un_fichero_de_eventos_existente(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    JsonLinesAuditSink(path).write([_event(1)])

    JsonLinesAuditSink(path).write([_event(2)])

    assert [d["rows"] for d in _lines(path)] == [1, 2]
    assert not list(tmp_path.glob("a.invalid-*"))


def test_message_con_saltos_de_linea_no_rompe_el_formato(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    event = AuditEvent.now(source="dump", kind="table", status="failed", message="línea 1\nlínea 2")

    JsonLinesAuditSink(path).write([event])

    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
