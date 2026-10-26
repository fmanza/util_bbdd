"""U-V2 (G6 de util_bbdd_web): el ``audit_sink`` del volcado recibe el evento de cada tabla al terminarla."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.audit import AuditEvent, MemoryAuditSink
from util_bbdd.dump import DumpConfig, DumpOrchestrator

pytestmark = pytest.mark.unit


def _engines(tmp_path: Path) -> tuple[Engine, Engine]:
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    for engine, rows in ((src, True), (dst, False)):
        with engine.begin() as conn:
            for table in ("a", "b", "c"):
                conn.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
                if rows:
                    conn.execute(text(f"INSERT INTO {table} VALUES (1), (2)"))
    with src.begin() as conn:
        conn.execute(text("CREATE TABLE solo_origen (id INTEGER PRIMARY KEY)"))
    return src, dst


def _tables(events: Sequence[AuditEvent]) -> list[str]:
    return [e.target or "" for e in events if e.kind == "table"]


class _SnapshotSink(MemoryAuditSink):
    """Guarda, al empezar cada tabla, qué eventos ``table`` había ya en el destino."""

    def __init__(self) -> None:
        super().__init__()
        self.seen_at_start: dict[str, list[str]] = {}


@pytest.mark.parametrize("parallel", [1, 2], ids=["secuencial", "paralelo"])
def test_table_events_arrive_while_dumping(tmp_path: Path, parallel: int) -> None:
    src, dst = _engines(tmp_path)
    sink = _SnapshotSink()
    orchestrator = DumpOrchestrator(
        DumpConfig(src, dst, output_dir=tmp_path, audit_sink=sink, truncate_target=True, max_parallel_tables=parallel)
    )
    original = orchestrator._process_table_with_columns

    def spy(src_table: str, *args: Any, **kwargs: Any) -> Any:
        sink.seen_at_start[src_table] = _tables(sink.events())
        return original(src_table, *args, **kwargs)

    orchestrator._process_table_with_columns = spy  # type: ignore[method-assign]
    result = orchestrator.run()

    # Sin FK, las tres tablas son del mismo nivel: en secuencial, cada una empieza con las anteriores ya registradas.
    if parallel == 1:
        assert sink.seen_at_start == {"a": [], "b": ["a"], "c": ["a", "b"]}
    events = sink.events()
    # Una vez cada tabla, también la que no existe en el destino (al final, con el resto de elementos).
    assert sorted(_tables(events)) == ["a", "b", "c", "solo_origen"]
    assert _tables(events)[-1] == "solo_origen"
    assert len(_tables(events)) == len(result.table_results)
    assert events[-1].kind == "run"
    src.dispose()
    dst.dispose()


def test_a_table_event_that_fails_to_write_is_retried_at_the_end(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)

    class _FlakySink(MemoryAuditSink):
        def __init__(self) -> None:
            super().__init__()
            self.failed = False

        def write(self, events: Sequence[AuditEvent], /) -> None:
            if not self.failed and any(e.kind == "table" for e in events):
                self.failed = True
                raise OSError("disco lleno un momento")
            super().write(events)

    sink = _FlakySink()
    DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, audit_sink=sink, truncate_target=True)).run()

    assert sorted(_tables(sink.events())) == ["a", "b", "c", "solo_origen"]
    src.dispose()
    dst.dispose()


def test_failed_dump_keeps_the_events_of_finished_tables(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    sink = MemoryAuditSink()
    orchestrator = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, audit_sink=sink, truncate_target=True))
    original = orchestrator._process_table_with_columns

    def boom(src_table: str, *args: Any, **kwargs: Any) -> Any:
        if src_table == "c":
            raise RuntimeError("caída a mitad")
        return original(src_table, *args, **kwargs)

    orchestrator._process_table_with_columns = boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        orchestrator.run()

    assert _tables(sink.events()) == ["a", "b"]
    (run,) = [e for e in sink.events() if e.kind == "run"]
    assert (run.status, run.error_type) == ("failed", "RuntimeError")
    src.dispose()
    dst.dispose()
