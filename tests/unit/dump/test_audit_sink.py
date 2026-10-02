"""F5 (sesión 2026-10-02c): ``DumpConfig(audit_sink=...)``: un ``run_id`` para todo el volcado."""

from __future__ import annotations

import logging

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd._core.exceptions import DumpReportError
from util_bbdd.audit import AuditEvent, MemoryAuditSink
from util_bbdd.dump import DumpConfig, DumpOrchestrator

pytestmark = pytest.mark.unit


def _engines(tmp_path: Path) -> tuple[Engine, Engine]:
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    with src.begin() as conn:
        conn.execute(text("CREATE TABLE a (id INTEGER PRIMARY KEY, v VARCHAR(10))"))
        conn.execute(text("CREATE TABLE b (id INTEGER PRIMARY KEY, v VARCHAR(10))"))
        conn.execute(text("INSERT INTO a VALUES (1, 'x'), (2, 'y'), (3, 'z')"))
        conn.execute(text("INSERT INTO b VALUES (1, 'p')"))
    with dst.begin() as conn:
        conn.execute(text("CREATE TABLE a (id INTEGER PRIMARY KEY, v VARCHAR(10))"))
        conn.execute(text("CREATE TABLE b (id INTEGER PRIMARY KEY, v VARCHAR(10))"))
    return src, dst


def _by_kind(events: Sequence[AuditEvent], kind: str) -> list[AuditEvent]:
    return [e for e in events if e.kind == kind]


def test_volcado_con_destino_un_run_id_para_todo(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    sink = MemoryAuditSink()

    result = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, audit_sink=sink)).run()

    events = sink.events()
    assert result.audit_run_id is not None
    assert {e.run_id for e in events} == {result.audit_run_id}
    # Las BulkCrud del volcado emiten sus operaciones con el run_id del volcado.
    assert sorted((e.target, e.rows) for e in _by_kind(events, "operation")) == [("a", 3), ("b", 1)]
    assert sorted((e.target, e.status, e.rows) for e in _by_kind(events, "table")) == [
        ("a", "ok", 3),
        ("b", "ok", 1),
    ]
    (run,) = _by_kind(events, "run")
    assert (run.source, run.status, run.rows, run.attribute("tables")) == ("dump", "ok", 4, 2)
    assert events[-1] is run  # el cierre es el último
    src.dispose()
    dst.dispose()


def test_volcado_sin_destino_no_cambia(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)

    result = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path)).run()

    assert result.audit_run_id is None
    src.dispose()
    dst.dispose()


def test_fallo_del_informe_emite_los_eventos_y_un_run_fallido(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    sink = MemoryAuditSink()
    orchestrator = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, audit_sink=sink))

    with (
        patch("util_bbdd.dump.orchestrator.DumpReporter.generate", side_effect=DumpReportError("Excel abierto")),
        pytest.raises(DumpReportError),
    ):
        orchestrator.run()

    assert len(_by_kind(sink.events(), "table")) == 2  # la carga terminó: sus resultados se registran
    (run,) = _by_kind(sink.events(), "run")
    assert (run.status, run.error_type) == ("failed", "DumpReportError")
    src.dispose()
    dst.dispose()


class _BrokenSink:
    def write(self, events: Sequence[AuditEvent], /) -> None:
        raise OSError("disco lleno")

    def close(self) -> None:
        pass


def test_fallo_del_destino_no_interrumpe_el_volcado(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    src, dst = _engines(tmp_path)

    with caplog.at_level(logging.ERROR):
        result = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, audit_sink=_BrokenSink())).run()

    assert [r.status for r in result.table_results] == ["success", "success"]
    assert result.audit_summary is None  # sin CSV no hay resumen; los fallos del destino van al log
    assert any("audit_sink" in r.getMessage() for r in caplog.records)
    src.dispose()
    dst.dispose()


# ---------------------------------------------------------------------------------------------------------------------
# audit-code 2026-10-02c
# ---------------------------------------------------------------------------------------------------------------------


class _RuntimeErrorSink:
    """Destino propio que falla con una excepción que no es AuditError ni OSError."""

    def write(self, events: Sequence[AuditEvent], /) -> None:
        if any(e.kind == "operation" for e in events):
            raise RuntimeError("cola externa caída")

    def close(self) -> None:
        pass


def test_strict_destino_propio_que_falla_deja_la_tabla_en_error_y_el_volcado_sigue(tmp_path: Path) -> None:
    """Hallazgo 1: antes el RuntimeError escapaba de la tabla y abortaba run()."""
    src, dst = _engines(tmp_path)

    result = DumpOrchestrator(
        DumpConfig(src, dst, output_dir=tmp_path, audit_sink=_RuntimeErrorSink(), bulk_audit_strict=True)
    ).run()

    assert {r.table_name: r.status for r in result.table_results} == {"a": "error", "b": "error"}
    assert all("cola externa caída" in r.error_msg for r in result.table_results)
    src.dispose()
    dst.dispose()


def _mock_engine() -> MagicMock:
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    engine.dialect.identifier_preparer.quote.side_effect = lambda n: n
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.execute.return_value.one.return_value = (1, 9)
    engine.connect.return_value = conn
    return engine


def test_carga_por_rangos_recibe_el_destino_y_el_run_id_del_volcado() -> None:
    """Test 1 del audit-code: _bulk_options → ParallelBulkLoader (SQLite fuerza 1 rango: se usa un engine simulado)."""
    sink = MemoryAuditSink()
    orch = DumpOrchestrator.__new__(DumpOrchestrator)
    orch._cfg = DumpConfig(source_engine=_mock_engine(), target_engine=_mock_engine(), audit_sink=sink)
    orch._reset_audit_tracking()
    orch._audit_run_id = "dump-1"

    from util_bbdd.bulk import ParallelLoadResult

    with patch("util_bbdd.dump.orchestrator.ParallelBulkLoader") as loader_cls:
        loader_cls.return_value.load.return_value = ParallelLoadResult()
        orch._load_in_pk_ranges("t", ["id"], {"id": "id"}, "id", "t", 2)

    assert loader_cls.call_args.kwargs["audit_sink"] is sink
    assert loader_cls.call_args.kwargs["audit_run_id"] == "dump-1"


def test_tablas_en_paralelo_comparten_el_run_id(tmp_path: Path) -> None:
    """Test 1 del audit-code: max_parallel_tables > 1 (una BulkCrud por hilo)."""
    src, dst = _engines(tmp_path)
    sink = MemoryAuditSink()

    result = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, audit_sink=sink, max_parallel_tables=2)).run()

    assert sorted(e.target for e in _by_kind(sink.events(), "operation")) == ["a", "b"]
    assert {e.run_id for e in sink.events()} == {result.audit_run_id}
    src.dispose()
    dst.dispose()
