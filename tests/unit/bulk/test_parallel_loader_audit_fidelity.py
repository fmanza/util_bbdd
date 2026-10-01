"""Fidelidad y coste de la auditoría en ``ParallelBulkLoader`` (audit-code de ParallelBulkLoader 2026-09-25).

Cada clase cubre un hallazgo del informe ``.ai/sessions/2026-09-25-audit-code-parallel-loader-audit/``:

- PL-2 / M-1: con ``audit_strict``, un COMMIT fallido después de escribir la auditoría no se reintenta.
- PL-1 / M-2: filas confirmadas por commits periódicos que no constan en el CSV.
- PL-6 / M-3: ``audited_rows`` para conciliar sin leer el CSV.
- PL-9 / M-5: con ``commit_every_n_chunks`` lo confirmado se escribe por tandas.
- PL-5 / M-4: un solo aviso de auditoría deshabilitada por carga.
- PL-3 / QW-1, PL-4 / QW-2, PL-7 y PL-8 / QW-3.
"""

from __future__ import annotations

import logging

from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, Table, create_engine, event, text
from sqlalchemy.exc import IntegrityError, OperationalError

from util_bbdd.bulk import BulkCrud, ParallelBulkLoader
from util_bbdd.bulk._audit.errors import AuditFileError
from util_bbdd.bulk._execution import parallel_loader as pl_mod
from util_bbdd.bulk._support import persistence as persistence_mod
from util_bbdd.bulk.audit import AuditConfigError, AuditManager

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    yield eng
    eng.dispose()


@pytest.fixture
def audit_path(tmp_path: Path) -> Path:
    return tmp_path / "audit.csv"


def _df(ids: range | list[int]) -> pd.DataFrame:
    return pd.DataFrame({"id": list(ids), "name": [f"n{i}" for i in ids]})


def _reader(*chunks: range | list[int]) -> Callable[[], Iterator[pd.DataFrame]]:
    def read() -> Iterator[pd.DataFrame]:
        for ids in chunks:
            yield _df(ids)

    return read


def _count(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM items")).scalar_one()


def _audit_rows(audit_path: Path) -> list[int]:
    if not audit_path.exists():
        return []
    return pd.read_csv(audit_path, sep="\t")["total_filas"].tolist()


def _fail_first_commit(engine: Engine) -> None:
    """El primer COMMIT del engine falla con ``OperationalError`` (conexión perdida al confirmar)."""
    state = {"fail": True}

    @event.listens_for(engine, "commit")
    def _commit(_conn: object) -> None:
        if state["fail"]:
            state["fail"] = False
            raise OperationalError(
                "COMMIT", {}, Exception("conexión perdida en el commit"), connection_invalidated=True
            )


class TestStrictCommitFailure:
    """PL-2 / M-1: antes el reintento volvía a escribir la auditoría (CSV 80 filas, BD 40)."""

    def test_strict_partition_is_not_retried_after_a_failed_commit(
        self, engine: Engine, audit_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        _fail_first_commit(engine)
        calls: list[int] = []

        def reader() -> Iterator[pd.DataFrame]:
            calls.append(1)
            yield _df(range(0, 20))
            yield _df(range(20, 40))

        loader = ParallelBulkLoader(
            engine, chunk_size=10, max_workers=1, max_retries=1, audit_csv_path=audit_path, audit_strict=True
        )
        with caplog.at_level(logging.ERROR):
            result = loader.load("items", [reader])

        pr = result.partition_results[0]
        assert calls == [1]  # sin reintento
        assert pr.retries == 0
        assert pr.audit_uncommitted_records == 2
        assert result.audit_uncommitted_records == 2
        assert pr.error is not None and "2 registros de este intento" in pr.error
        assert _count(engine) == 0
        assert _audit_rows(audit_path) == [20, 20]  # lo escrito antes del COMMIT, una sola vez
        assert any("antes de un commit que falló" in r.getMessage() for r in caplog.records)

    def test_fail_open_is_still_retried_and_audited_once(self, engine: Engine, audit_path: Path) -> None:
        _fail_first_commit(engine)
        loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=1, max_retries=1, audit_csv_path=audit_path)

        result = loader.load("items", [_reader(range(0, 20), range(20, 40))])

        pr = result.partition_results[0]
        assert pr.error is None
        assert pr.retries == 1
        assert pr.audit_uncommitted_records == 0
        assert _count(engine) == 40
        assert _audit_rows(audit_path) == [20, 20]

    def test_bulk_session_counts_records_written_before_the_failed_commit(
        self, engine: Engine, audit_path: Path
    ) -> None:
        _fail_first_commit(engine)
        crud = BulkCrud(engine, chunk_size=10, audit_csv_path=audit_path, audit_strict=True)

        with pytest.raises(OperationalError):
            with crud.bulk_session():
                crud.bulk_insert_from_df(_df(range(0, 5)), "items", generar_sql=False)

        assert crud.audit_uncommitted_records == 1
        assert crud.audited_rows == 5  # están en el CSV, aunque no en la BD
        assert _count(engine) == 0


class TestUnauditedCommittedRows:
    """PL-1 / M-2: operación confirmada a medias por un commit periódico antes de un fallo."""

    def _load(self, engine: Engine, audit_path: Path) -> pl_mod.ParallelLoadResult:
        loader = ParallelBulkLoader(
            engine, chunk_size=10, max_workers=1, commit_every_n_chunks=3, audit_csv_path=audit_path
        )
        # Lotes 1-2 (op. 1), 3-4 (op. 2; el 3 se confirma con el commit periódico) y 5 (op. 3, PK duplicada).
        return loader.load("items", [_reader(range(0, 20), range(20, 40), range(0, 10))])

    def test_gap_is_reported_in_the_result(self, engine: Engine, audit_path: Path) -> None:
        result = self._load(engine, audit_path)

        pr = result.partition_results[0]
        assert _count(engine) == 30
        assert pr.rows == 30
        assert _audit_rows(audit_path) == [20]
        assert pr.audited_rows == 20
        assert pr.unaudited_committed_rows == 10
        assert result.audited_rows + result.unaudited_committed_rows == result.total_rows

    def test_warnings_do_not_claim_the_committed_rows_were_unconfirmed(
        self, engine: Engine, audit_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            self._load(engine, audit_path)

        messages = [r.getMessage() for r in caplog.records]
        assert any("sin confirmarlos enteros (rollback)" in m for m in messages)
        assert any("10 filas confirmadas por commits periódicos no constan en el CSV" in m for m in messages)

    def test_plain_rollback_keeps_the_previous_message_and_no_gap(
        self, engine: Engine, audit_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        crud = BulkCrud(engine, chunk_size=10, commit_every_n_chunks=2, audit_csv_path=audit_path)

        with caplog.at_level(logging.WARNING), pytest.raises(IntegrityError):
            with crud.bulk_session():
                crud.bulk_insert_from_df(_df(range(0, 20)), "items", generar_sql=False)  # lotes 1-2: commit
                crud.bulk_insert_from_df(_df(range(20, 30)), "items", generar_sql=False)  # lote 3: pendiente
                crud.bulk_insert_from_df(_df([0]), "items", generar_sql=False)  # falla

        assert crud.unaudited_committed_rows == 0
        assert any("sin confirmarlos (rollback)" in r.getMessage() for r in caplog.records)
        assert not any("no constan en el CSV" in r.getMessage() for r in caplog.records)


class TestAuditedRows:
    """PL-6 / M-3: conciliación sin leer el CSV."""

    def test_successful_load_audits_every_row(self, engine: Engine, audit_path: Path) -> None:
        loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=2, audit_csv_path=audit_path)

        result = loader.load("items", [_reader(range(0, 20)), _reader(range(100, 130))])

        assert result.audited_rows == result.total_rows == 50
        assert sorted(pr.audited_rows for pr in result.partition_results) == [20, 30]
        assert sum(_audit_rows(audit_path)) == 50

    def test_lost_records_are_not_counted_as_audited(self, engine: Engine, audit_path: Path) -> None:
        loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=1, audit_csv_path=audit_path)

        with patch.object(AuditManager, "_registrar_lote", side_effect=OSError("CSV bloqueado")):
            result = loader.load("items", [_reader(range(0, 10), range(10, 20))])

        assert result.total_rows == 20
        assert result.audited_rows == 0
        assert result.audit_failures == 2

    def test_without_audit_nothing_is_counted(self, engine: Engine) -> None:
        result = ParallelBulkLoader(engine, chunk_size=10, max_workers=1).load("items", [_reader(range(0, 10))])

        assert result.audited_rows == 0

    def test_operations_outside_a_session_are_counted(self, engine: Engine, audit_path: Path) -> None:
        crud = BulkCrud(engine, audit_csv_path=audit_path)

        crud.bulk_insert_from_df(_df(range(0, 7)), "items", generar_sql=False)

        assert crud.audited_rows == 7


class TestConfirmedBatching:
    """PL-9 / M-5: con operaciones de un lote y N=2 salían 2 aperturas del CSV por commit (una por operación)."""

    def _spy(self) -> object:
        return patch.object(AuditManager, "_registrar_lote", autospec=True, side_effect=AuditManager._registrar_lote)

    def test_confirmed_operations_are_written_in_batches(
        self, engine: Engine, audit_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(persistence_mod, "_CONFIRMED_FLUSH_SECONDS", 3600.0)
        crud = BulkCrud(engine, chunk_size=10, commit_every_n_chunks=2, audit_csv_path=audit_path)

        with self._spy() as spy:
            crud.bulk_insert_from_chunks((_df(range(i, i + 10)) for i in range(0, 400, 10)), "items")

        assert spy.call_count == 1  # 40 operaciones < 64: una sola escritura al cerrar la sesión
        assert _audit_rows(audit_path) == [10] * 40
        assert crud.audited_rows == 400

    def test_record_threshold_bounds_what_is_kept_in_memory(
        self, engine: Engine, audit_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(persistence_mod, "_CONFIRMED_FLUSH_SECONDS", 3600.0)
        crud = BulkCrud(engine, chunk_size=10, commit_every_n_chunks=1, audit_csv_path=audit_path)

        with self._spy() as spy:
            crud.bulk_insert_from_chunks((_df(range(i, i + 10)) for i in range(0, 1500, 10)), "items")

        assert [len(call.args[1]) for call in spy.call_args_list] == [64, 64, 22]
        assert len(_audit_rows(audit_path)) == 150

    def test_time_threshold_writes_without_waiting_for_the_record_threshold(
        self, engine: Engine, audit_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(persistence_mod, "_CONFIRMED_FLUSH_SECONDS", 0.0)
        crud = BulkCrud(engine, chunk_size=10, commit_every_n_chunks=1, audit_csv_path=audit_path)

        with self._spy() as spy:
            crud.bulk_insert_from_chunks((_df(range(i, i + 10)) for i in range(0, 50, 10)), "items")

        assert spy.call_count == 5

    def test_confirmed_operations_are_written_when_the_session_fails(
        self, engine: Engine, audit_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(persistence_mod, "_CONFIRMED_FLUSH_SECONDS", 3600.0)
        crud = BulkCrud(engine, chunk_size=10, commit_every_n_chunks=1, audit_csv_path=audit_path)
        chunks = [_df(range(i, i + 10)) for i in range(0, 50, 10)] + [_df([0])]

        with pytest.raises(IntegrityError):
            crud.bulk_insert_from_chunks(iter(chunks), "items")

        assert _count(engine) == 50
        assert _audit_rows(audit_path) == [10] * 5

    def test_strict_still_writes_before_each_commit(self, engine: Engine, audit_path: Path) -> None:
        crud = BulkCrud(engine, chunk_size=10, commit_every_n_chunks=2, audit_csv_path=audit_path, audit_strict=True)

        with self._spy() as spy:
            crud.bulk_insert_from_chunks((_df(range(i, i + 10)) for i in range(0, 40, 10)), "items")

        assert spy.call_count == 4  # una por operación, como antes: strict no agrupa
        assert _audit_rows(audit_path) == [10] * 4


class TestDisabledAuditWarning:
    """PL-5 / M-4: antes, un WARNING por partición en cada carga."""

    def test_loader_warns_once_per_load_at_info(self, engine: Engine, caplog: pytest.LogCaptureFixture) -> None:
        loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=2)
        readers = [_reader(range(i * 10, i * 10 + 10)) for i in range(8)]

        with caplog.at_level(logging.INFO):
            loader.load("items", readers)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "deshabilitada" in r.getMessage()]
        infos = [r for r in caplog.records if r.levelno == logging.INFO and "deshabilitada" in r.getMessage()]
        assert warnings == []
        assert len(infos) == 1

    def test_bulk_crud_can_skip_the_warning(self, engine: Engine, caplog: pytest.LogCaptureFixture) -> None:
        crud = BulkCrud(engine, warn_if_audit_disabled=False)

        with caplog.at_level(logging.WARNING):
            crud.bulk_insert_from_df(_df([1]), "items", generar_sql=False)

        assert not any("deshabilitada" in r.getMessage() for r in caplog.records)

    def test_bulk_crud_warns_by_default(self, engine: Engine, caplog: pytest.LogCaptureFixture) -> None:
        crud = BulkCrud(engine)

        with caplog.at_level(logging.WARNING):
            crud.bulk_insert_from_df(_df([1]), "items", generar_sql=False)

        assert any("deshabilitada" in r.getMessage() for r in caplog.records)


class TestLoaderQuickWins:
    def test_resolve_table_keeps_fast_executemany_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PL-3 / QW-1: el hoist activaba fast_executemany en el engine compartido aunque se pidiera False."""
        pytest.importorskip("pyodbc")
        engine = create_engine("mssql+pyodbc://u:p@dsn_inexistente")  # no conecta: reflect_table se sustituye
        fake = Table("t", MetaData(), Column("id", Integer, primary_key=True))
        monkeypatch.setattr(BulkCrud, "reflect_table", lambda _self, _name: fake)
        loader = ParallelBulkLoader(engine, max_workers=1, enable_fast_executemany=False, disable_constraints=True)

        loader._resolve_table("t")

        assert engine.dialect.fast_executemany is False

    def test_invalid_audit_path_fails_in_the_constructor(self, engine: Engine, tmp_path: Path) -> None:
        """PL-4 / QW-2: antes fallaba cada partición por separado, ya dentro del pool."""
        blocker = tmp_path / "no_soy_directorio"
        blocker.write_text("x")

        with pytest.raises(AuditConfigError) as excinfo:
            ParallelBulkLoader(engine, audit_csv_path=blocker / "audit.csv")

        assert isinstance(excinfo.value, ValueError)  # el Raises del constructor sigue siendo ValueError

    def test_strict_audit_error_is_logged_without_traceback(
        self, engine: Engine, audit_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """PL-7 / QW-3: BulkCrud ya registró el ERROR; el loader no repite la traza."""
        loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=1, audit_csv_path=audit_path, audit_strict=True)
        with (
            patch.object(AuditManager, "_registrar_lote", side_effect=AuditFileError("CSV bloqueado")),
            caplog.at_level(logging.WARNING),
        ):
            result = loader.load("items", [_reader(range(0, 10))])

        assert result.partition_errors == ["partición 0: CSV bloqueado"]
        permanent = [r for r in caplog.records if "Error permanente" in r.getMessage()]
        assert len(permanent) == 1 and not permanent[0].exc_info

    def test_exhausted_retries_use_the_common_error_format(self) -> None:
        """PL-8 / QW-3: la rama de reintentos agotados construía el texto a mano."""
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.side_effect = TimeoutError("timeout")
            crud_cls.return_value.rows_committed = 0
            crud_cls.return_value.audit_uncommitted_records = 0
            crud_cls.return_value.rows_rejected = 0  # sin on_error="isolate"
            result = ParallelBulkLoader(create_engine("sqlite://"), max_workers=1, max_retries=1).load(
                "t", [lambda: iter([])]
            )

        assert result.partition_errors == ["partición 0: TimeoutError: timeout"]
