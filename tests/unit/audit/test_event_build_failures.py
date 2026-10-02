"""Hipótesis 5 del audit-code 2026-10-02c: un fallo al *construir* los eventos no rompe la operación auditada.

Hoy ninguna entrada real hace fallar la construcción de un ``AuditEvent``; estos tests lo inyectan con ``monkeypatch`` en
los cuatro sitios que emiten eventos: cierre del volcado, cierre de la carga paralela, ``MigrationPlan.execute`` y la
emisión por operación de ``BulkCrud``.
"""

from __future__ import annotations

import logging

from collections.abc import Iterator
from pathlib import Path
from typing import Any, NoReturn
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd import AuditError
from util_bbdd._core.exceptions import DumpReportError
from util_bbdd.audit import MemoryAuditSink
from util_bbdd.bulk import BulkCrud, ParallelBulkLoader
from util_bbdd.bulk._audit.events import BulkAuditEvents
from util_bbdd.dump import DumpConfig, DumpOrchestrator
from util_bbdd.dump._audit_events import DumpAuditEvents
from util_bbdd.migrate import MigrationPlan
from util_bbdd.migrate._audit_events import MigrationAuditEvents

pytestmark = pytest.mark.unit


def _boom(*_args: Any, **_kwargs: Any) -> NoReturn:
    raise ValueError("construcción del evento rota")


@pytest.fixture
def items(tmp_path: Path) -> Iterator[Engine]:
    eng = create_engine(f"sqlite:///{tmp_path / 'items.db'}")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    yield eng
    eng.dispose()


def _dump_engines(tmp_path: Path) -> tuple[Engine, Engine]:
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    for eng in (src, dst):
        with eng.begin() as conn:
            conn.execute(text("CREATE TABLE a (id INTEGER PRIMARY KEY, v VARCHAR(10))"))
    with src.begin() as conn:
        conn.execute(text("INSERT INTO a VALUES (1, 'x'), (2, 'y')"))
    return src, dst


def _errors(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]


# --- dump -------------------------------------------------------------------------------------------------------------


def test_dump_correcto_devuelve_el_resultado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    src, dst = _dump_engines(tmp_path)
    monkeypatch.setattr(DumpAuditEvents, "result_events", staticmethod(_boom))

    with caplog.at_level(logging.ERROR):
        result = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, audit_sink=MemoryAuditSink())).run()

    assert [r.status for r in result.table_results] == ["success"]
    assert any("construcción del evento rota" in m for m in _errors(caplog))
    src.dispose()
    dst.dispose()


def test_dump_con_fallo_del_informe_conserva_la_excepcion_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src, dst = _dump_engines(tmp_path)
    monkeypatch.setattr(DumpAuditEvents, "result_events", staticmethod(_boom))
    orchestrator = DumpOrchestrator(DumpConfig(src, dst, output_dir=tmp_path, audit_sink=MemoryAuditSink()))

    with (
        patch("util_bbdd.dump.orchestrator.DumpReporter.generate", side_effect=DumpReportError("Excel abierto")),
        pytest.raises(DumpReportError) as excinfo,
    ):
        orchestrator.run()

    assert excinfo.value.result is not None  # quien llama sigue recuperando el DumpResult
    src.dispose()
    dst.dispose()


# --- ParallelBulkLoader -----------------------------------------------------------------------------------------------


def test_carga_paralela_devuelve_el_resultado(
    items: Engine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(BulkAuditEvents, "partition", staticmethod(_boom))
    sink = MemoryAuditSink()

    def reader() -> Iterator[pd.DataFrame]:
        yield pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})

    with caplog.at_level(logging.ERROR):
        result = ParallelBulkLoader(items, chunk_size=10, max_workers=1, audit_sink=sink).load("items", [reader])

    assert result.total_rows == 2 and not result.partition_errors
    assert [e.kind for e in sink.events()] == ["operation"]  # los eventos por operación no dependen del cierre
    assert any("construcción del evento rota" in m for m in _errors(caplog))


# --- migrate ----------------------------------------------------------------------------------------------------------


def _plan(statements: list[str]) -> MigrationPlan:
    emitter = MagicMock()
    emitter.emit_statements.return_value = statements
    return MigrationPlan(
        tables=[], warnings=[], source_schema="S", source_engine="oracle", target_engine="sqlite", emitter=emitter
    )


def test_migracion_aplica_el_ddl_y_registra_el_cierre(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(MigrationAuditEvents, "statement", staticmethod(_boom))
    target = MagicMock(spec=["execute_custom_one"])
    sink = MemoryAuditSink()

    with caplog.at_level(logging.ERROR):
        _plan(["CREATE TABLE a (x INT)", "CREATE TABLE b (y INT)"]).execute(target, audit_sink=sink)

    assert target.execute_custom_one.call_count == 2
    assert [(e.kind, e.status) for e in sink.events()] == [("run", "ok")]
    assert sum("construcción del evento rota" in m for m in _errors(caplog)) == 2


def test_migracion_fallida_conserva_su_excepcion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MigrationAuditEvents, "statement", staticmethod(_boom))
    target = MagicMock(spec=["execute_custom_one"])
    target.execute_custom_one.side_effect = RuntimeError("tabla existe")

    with pytest.raises(RuntimeError, match="tabla existe"):
        _plan(["CREATE TABLE a (x INT)"]).execute(target, audit_sink=MemoryAuditSink())


# --- BulkCrud ---------------------------------------------------------------------------------------------------------


def _df() -> pd.DataFrame:
    return pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})


def _count(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM items")).scalar_one())


def test_bulk_no_estricto_cuenta_el_fallo_y_sigue(items: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BulkAuditEvents, "operation", staticmethod(_boom))
    crud = BulkCrud(items, audit_sink=MemoryAuditSink())

    crud.bulk_insert_from_df(_df(), "items", generar_sql=False)

    assert _count(items) == 3
    assert crud.audit_failures == 1


def test_bulk_estricto_lanza_audit_error_y_deshace(items: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BulkAuditEvents, "operation", staticmethod(_boom))
    crud = BulkCrud(items, audit_sink=MemoryAuditSink(), audit_strict=True)

    with pytest.raises(AuditError, match="construcción del evento rota"), crud.bulk_session():
        crud.bulk_insert_from_df(_df(), "items", generar_sql=False)

    assert _count(items) == 0
