"""F5 (sesión 2026-10-02c): ``BulkCrud(audit_sink=...)`` y ``ParallelBulkLoader(audit_sink=...)``.

Los eventos ``operation`` salen de los mismos registros que el CSV y en el mismo momento: con ``bulk_session`` al
confirmarse la transacción; si la sesión acaba en rollback no hay evento. Un fallo del destino sigue ``audit_strict``.
"""

from __future__ import annotations

import logging

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.audit import AuditEvent, MemoryAuditSink
from util_bbdd.bulk import BulkCrud, ParallelBulkLoader
from util_bbdd.bulk.audit import AuditManager

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    yield eng
    eng.dispose()


def _df(start: int, n: int) -> pd.DataFrame:
    return pd.DataFrame({"id": range(start, start + n), "name": [f"n{i}" for i in range(start, start + n)]})


def _count(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM items")).scalar_one())


class _BrokenSink:
    def write(self, events: Sequence[AuditEvent], /) -> None:
        raise OSError("disco lleno")

    def close(self) -> None:
        pass


def test_operacion_fuera_de_sesion_emite_un_evento(engine: Engine) -> None:
    sink = MemoryAuditSink()
    crud = BulkCrud(engine, audit_sink=sink)

    crud.bulk_insert_from_df(_df(1, 5), "items", generar_sql=False)

    (event,) = sink.events()
    assert (event.source, event.kind, event.status) == ("bulk", "operation", "ok")
    assert (event.engine, event.target, event.operation, event.rows) == ("sqlite", "items", "INSERT", 5)
    assert event.run_id == crud.audit_run_id is not None
    assert event.attribute("generated_sql") is False
    assert event.timestamp.tzinfo is not None


def test_csv_y_destino_registran_lo_mismo(engine: Engine, tmp_path: Path) -> None:
    sink = MemoryAuditSink()
    crud = BulkCrud(engine, audit_csv_path=tmp_path / "a.csv", audit_sink=sink, audit_run_id="r-1")

    crud.bulk_insert_from_df(_df(1, 5), "items", generar_sql=False)
    crud.bulk_delete_from_df(_df(1, 2)[["id"]], "items", generar_sql=False)

    csv_rows = AuditManager(tmp_path / "a.csv").leer_auditoria()
    assert csv_rows["total_filas"].tolist() == [e.rows for e in sink.events()] == [5, 2]
    assert csv_rows["operacion"].tolist() == [e.operation for e in sink.events()]
    assert {e.run_id for e in sink.events()} == {"r-1"}


def test_sesion_confirmada_emite_al_commit_y_rollback_no_emite(engine: Engine) -> None:
    sink = MemoryAuditSink()
    crud = BulkCrud(engine, audit_sink=sink)

    with crud.bulk_session():
        crud.bulk_insert_from_df(_df(1, 3), "items", generar_sql=False)
        assert sink.events() == ()  # aún sin confirmar
    assert [e.rows for e in sink.events()] == [3]

    with pytest.raises(RuntimeError), crud.bulk_session():
        crud.bulk_insert_from_df(_df(10, 4), "items", generar_sql=False)
        raise RuntimeError("fallo después de insertar")
    assert [e.rows for e in sink.events()] == [3]  # lo deshecho no se audita
    assert _count(engine) == 3


def test_destino_sin_csv_no_avisa_de_auditoria_deshabilitada(engine: Engine, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="util_bbdd.bulk.audit"):
        BulkCrud(engine, audit_sink=MemoryAuditSink()).bulk_insert_from_df(_df(1, 2), "items", generar_sql=False)
    assert not [r for r in caplog.records if "Auditoría deshabilitada" in r.getMessage()]


def test_fallo_del_destino_sin_strict_cuenta_y_sigue(engine: Engine) -> None:
    crud = BulkCrud(engine, audit_sink=_BrokenSink())

    crud.bulk_insert_from_df(_df(1, 4), "items", generar_sql=False)

    assert _count(engine) == 4
    assert crud.audit_failures == 1


def test_fallo_del_destino_con_strict_deshace_la_sesion(engine: Engine) -> None:
    crud = BulkCrud(engine, audit_sink=_BrokenSink(), audit_strict=True)

    with pytest.raises(OSError, match="disco lleno"), crud.bulk_session():
        crud.bulk_insert_from_df(_df(1, 4), "items", generar_sql=False)

    assert _count(engine) == 0


def test_sin_destino_no_hay_run_id(engine: Engine) -> None:
    assert BulkCrud(engine).audit_run_id is None


def _reader(start: int) -> Callable[[], Iterator[pd.DataFrame]]:
    def read() -> Iterator[pd.DataFrame]:
        yield _df(start, 10)
        yield _df(start + 10, 10)

    return read


def test_carga_paralela_eventos_y_conciliacion(engine: Engine) -> None:
    sink = MemoryAuditSink()
    loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=2, audit_sink=sink)

    result = loader.load("items", [_reader(0), _reader(100), _reader(200)])

    events = sink.events()
    operations = [e for e in events if e.kind == "operation"]
    partitions = [e for e in events if e.kind == "partition"]
    (run,) = [e for e in events if e.kind == "run"]
    # Invariante de conciliación de ParallelLoadResult, comprobada contra los eventos.
    assert sum(e.rows or 0 for e in operations) + result.rows_rejected == result.total_rows == 60
    assert [e.attribute("partition") for e in partitions] == [0, 1, 2]
    assert (run.status, run.rows, run.attribute("partitions")) == ("ok", 60, 3)
    assert {e.run_id for e in events} == {result.audit_run_id}
    assert result.audit_run_id is not None


def test_carga_paralela_con_run_id_recibido(engine: Engine) -> None:
    sink = MemoryAuditSink()
    loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=1, audit_sink=sink, audit_run_id="dump-1")

    assert loader.load("items", [_reader(0)]).audit_run_id == "dump-1"
    assert {e.run_id for e in sink.events()} == {"dump-1"}


def test_carga_paralela_fallo_del_destino_final_no_cambia_el_resultado(
    engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=1, audit_sink=_BrokenSink())

    with caplog.at_level(logging.ERROR):
        result = loader.load("items", [_reader(0)])

    assert result.total_rows == 20 and not result.partition_errors
    assert any("audit_sink" in r.getMessage() for r in caplog.records)


def test_strict_csv_escrito_y_destino_fallido_cuenta_lo_escrito_sin_commit(engine: Engine, tmp_path: Path) -> None:
    """AUDIT_CODE de F5: el CSV se escribe antes del commit, falla el destino y la sesión se deshace."""
    crud = BulkCrud(engine, audit_csv_path=tmp_path / "a.csv", audit_sink=_BrokenSink(), audit_strict=True)

    with pytest.raises(OSError, match="disco lleno"), crud.bulk_session():
        crud.bulk_insert_from_df(_df(1, 4), "items", generar_sql=False)

    assert _count(engine) == 0
    assert AuditManager(tmp_path / "a.csv").leer_auditoria()["total_filas"].tolist() == [4]
    assert crud.audit_uncommitted_records == 1


def test_run_id_sin_destino_es_none(engine: Engine) -> None:
    """Hallazgo 3 del audit-code 2026-10-02c: como ParallelBulkLoader."""
    assert BulkCrud(engine, audit_run_id="x").audit_run_id is None
    assert BulkCrud(engine, audit_sink=MemoryAuditSink(), audit_run_id="x").audit_run_id == "x"


class _RuntimeErrorSink:
    def write(self, events: Sequence[AuditEvent], /) -> None:
        raise RuntimeError("cola externa caída")

    def close(self) -> None:
        pass


def test_strict_destino_propio_que_falla_lanza_audit_error(engine: Engine) -> None:
    """Hallazgo 1: audit_strict promete AuditError/OSError; la causa original queda en __cause__."""
    from util_bbdd.exceptions import AuditError

    crud = BulkCrud(engine, audit_sink=_RuntimeErrorSink(), audit_strict=True)

    with pytest.raises(AuditError, match="cola externa caída") as excinfo, crud.bulk_session():
        crud.bulk_insert_from_df(_df(1, 2), "items", generar_sql=False)

    assert isinstance(excinfo.value.__cause__, RuntimeError)
    assert _count(engine) == 0


def test_log_sin_csv_no_menciona_el_csv(engine: Engine, caplog: pytest.LogCaptureFixture) -> None:
    """Hallazgo 4: solo destino, strict, falla el commit tras escribir los eventos."""
    crud = BulkCrud(engine, audit_sink=MemoryAuditSink(), audit_strict=True)
    persistence = crud._persistence
    persistence.start_session_audit(MagicMock(in_transaction=MagicMock(return_value=True)))
    persistence.register_operation(table_name="items", operation="INSERT", rowcount=3, elapsed=0.1, generated_sql=False)
    persistence.flush_audit_before_commit()

    with caplog.at_level(logging.ERROR):
        persistence.end_session_audit()  # el commit no llegó a hacerse

    assert crud.audit_uncommitted_records == 1
    (message,) = [r.getMessage() for r in caplog.records if "antes de un commit" in r.getMessage()]
    assert "audit_sink" in message and "CSV" not in message


# ---------------------------------------------------------------------------------------------------------------------
# Eventos de ParallelBulkLoader.update() y .delete() (pendiente del audit-code 2026-10-02c)
# ---------------------------------------------------------------------------------------------------------------------


def _chunked(start: int, value: str) -> Callable[[], Iterator[pd.DataFrame]]:
    """Partición de 10 filas (ids ``start``..``start+9``) en 2 chunks de 5."""

    def read() -> Iterator[pd.DataFrame]:
        for offset in (0, 5):
            ids = list(range(start + offset, start + offset + 5))
            yield pd.DataFrame({"id": ids, "name": [value] * 5})

    return read


def _seed(engine: Engine, n: int = 40) -> None:
    BulkCrud(engine).bulk_insert_from_df(_df(1, n), "items", generar_sql=False)


@pytest.mark.parametrize(("method", "operation"), [("update", "UPDATE"), ("delete", "DELETE")])
def test_update_y_delete_paralelos_emiten_sus_eventos(engine: Engine, method: str, operation: str) -> None:
    _seed(engine)
    sink = MemoryAuditSink()
    loader = ParallelBulkLoader(engine, chunk_size=5, max_workers=1, audit_sink=sink)

    result = getattr(loader, method)("items", [_chunked(1, "u"), _chunked(11, "u")])

    events = sink.events()
    operations = [e for e in events if e.kind == "operation"]
    partitions = [e for e in events if e.kind == "partition"]
    (run,) = [e for e in events if e.kind == "run"]
    assert [e.operation for e in operations] == [operation] * 4  # un registro por chunk, al confirmar la sesión
    assert sum(e.rows or 0 for e in operations) == result.total_rows == 20
    assert [(e.operation, e.attribute("partition"), e.status) for e in partitions] == [
        (operation, 0, "ok"),
        (operation, 1, "ok"),
    ]
    assert (run.operation, run.status, run.rows) == (operation, "ok", 20)
    assert {e.run_id for e in events} == {result.audit_run_id}
    expected = 40 if method == "update" else 20
    assert _count(engine) == expected


def test_reintento_de_update_no_duplica_eventos(engine: Engine) -> None:
    """El intento que falla se deshace entero: sus registros no llegan al destino; solo los del intento confirmado."""
    _seed(engine)
    sink = MemoryAuditSink()
    calls: list[int] = []

    def flaky() -> Iterator[pd.DataFrame]:
        calls.append(1)
        yield pd.DataFrame({"id": [1, 2, 3, 4, 5], "name": ["r"] * 5})
        if len(calls) == 1:
            raise RuntimeError("corte transitorio")
        yield pd.DataFrame({"id": [6, 7, 8, 9, 10], "name": ["r"] * 5})

    loader = ParallelBulkLoader(
        engine,
        chunk_size=5,
        max_workers=1,
        audit_sink=sink,
        retry_backoff=(0, 0),
        retry_on=lambda exc: isinstance(exc, RuntimeError),
    )

    result = loader.update("items", [flaky])

    operations = [e for e in sink.events() if e.kind == "operation"]
    (partition,) = [e for e in sink.events() if e.kind == "partition"]
    assert len(calls) == 2
    assert [e.rows for e in operations] == [5, 5]  # sin los 5 del intento deshecho
    assert (partition.status, partition.attribute("retries"), partition.rows) == ("ok", 1, 10)
    assert result.total_rows == 10
