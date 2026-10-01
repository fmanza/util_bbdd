"""Auditoría diferida dentro de ``bulk_session`` (M-1, audit-code de AuditManager 2026-09-25).

Antes cada operación se escribía en el CSV al terminar, aunque la transacción de la sesión aún no se hubiera
confirmado: un rollback dejaba filas de auditoría de datos deshechos y los reintentos de ``ParallelBulkLoader`` las
repetían. Ahora la fila se escribe cuando un commit confirma la operación y se descarta si la sesión se deshace.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError

from util_bbdd.bulk import ParallelBulkLoader
from util_bbdd.bulk.audit import AuditManager
from util_bbdd.bulk.crud import BulkCrud

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


def _count_rows(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM items")).scalar_one()


def _audit_rows(audit_path: Path) -> pd.DataFrame:
    if not audit_path.exists():
        return pd.DataFrame(columns=["operacion", "total_filas"])
    return pd.read_csv(audit_path, sep="\t")


class TestAtomicSession:
    def test_rows_are_written_only_after_the_commit(self, engine: Engine, audit_path: Path) -> None:
        crud = BulkCrud(engine, audit_csv_path=audit_path)

        with crud.bulk_session():
            crud.bulk_insert_from_df(_df(range(0, 3)), "items", generar_sql=False)
            crud.bulk_delete_from_df(_df([0]), "items", generar_sql=False)
            assert not audit_path.exists()

        audit = _audit_rows(audit_path)
        assert audit["operacion"].tolist() == ["INSERT", "DELETE"]
        assert audit["total_filas"].tolist() == [3, 1]

    def test_rollback_discards_pending_rows_with_a_warning(
        self, engine: Engine, audit_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        crud = BulkCrud(engine, audit_csv_path=audit_path)

        with caplog.at_level("WARNING"), pytest.raises(IntegrityError):
            with crud.bulk_session():
                crud.bulk_insert_from_df(_df(range(0, 5)), "items", generar_sql=False)
                crud.bulk_insert_from_df(_df([1]), "items", generar_sql=False)  # PK duplicada

        assert _count_rows(engine) == 0
        assert _audit_rows(audit_path).empty
        assert any("se descartan 1 registros (5 filas)" in r.getMessage() for r in caplog.records)

    def test_timestamp_is_the_end_of_each_operation_not_the_commit(self, engine: Engine, audit_path: Path) -> None:
        crud = BulkCrud(engine, audit_csv_path=audit_path)
        with crud.bulk_session():
            crud.bulk_insert_from_df(_df([1]), "items", generar_sql=False)
            pending = crud._persistence._pending
            assert len(pending) == 1
            # El registro guarda el fin de la operación; se fija a una hora conocida para ver que el CSV la respeta.
            pending[0] = replace(pending[0], timestamp=datetime(2026, 1, 1, 10, 0, 0))

        assert _audit_rows(audit_path)["timestamp"].tolist() == ["2026-01-01 10:00:00"]

    def test_generated_sql_is_written_immediately_even_if_the_session_rolls_back(
        self, engine: Engine, audit_path: Path, tmp_path: Path
    ) -> None:
        crud = BulkCrud(engine, audit_csv_path=audit_path)

        with pytest.raises(IntegrityError):
            with crud.bulk_session():
                crud.bulk_insert_from_df(_df([1]), "items", generar_sql=True, path_sql=tmp_path)
                crud.bulk_insert_from_df(_df([1, 1]), "items", generar_sql=False)

        audit = _audit_rows(audit_path)
        assert audit["sql"].tolist() == ["Sí"]

    def test_without_audit_path_nothing_is_buffered(self, engine: Engine) -> None:
        crud = BulkCrud(engine)
        with crud.bulk_session():
            crud.bulk_insert_from_df(_df([1]), "items", generar_sql=False)
        assert crud._persistence._pending == []
        assert _count_rows(engine) == 1


class TestStreamingInsert:
    def test_failed_chunk_leaves_no_audit_rows(self, engine: Engine, audit_path: Path) -> None:
        # R3 de la auditoría: antes el CSV decía "INSERT 100 filas" con la tabla vacía.
        crud = BulkCrud(engine, audit_csv_path=audit_path)

        with pytest.raises(IntegrityError):
            crud.bulk_insert_from_chunks(iter([_df(range(0, 100)), _df([5])]), "items")

        assert _count_rows(engine) == 0
        assert _audit_rows(audit_path).empty

    def test_all_chunks_are_written_with_a_single_csv_write(self, engine: Engine, audit_path: Path) -> None:
        crud = BulkCrud(engine, chunk_size=10, audit_csv_path=audit_path)

        with patch.object(
            AuditManager, "_registrar_lote", autospec=True, side_effect=AuditManager._registrar_lote
        ) as spy:
            crud.bulk_insert_from_chunks((_df(range(i, i + 10)) for i in range(0, 200, 10)), "items")

        assert spy.call_count == 1
        audit = _audit_rows(audit_path)
        assert len(audit) == 20
        assert audit["total_filas"].sum() == 200


class TestCommitEveryNChunks:
    def test_operations_confirmed_by_their_own_commit_survive_a_later_failure(
        self, engine: Engine, audit_path: Path
    ) -> None:
        # Cada operación es un lote y se confirma sola: al registrarla ya no queda nada pendiente.
        crud = BulkCrud(engine, chunk_size=10, commit_every_n_chunks=1, audit_csv_path=audit_path)

        with pytest.raises(IntegrityError):
            with crud.bulk_session():
                crud.bulk_insert_from_df(_df(range(0, 10)), "items", generar_sql=False)
                crud.bulk_insert_from_df(_df(range(10, 20)), "items", generar_sql=False)
                crud.bulk_insert_from_df(_df([0]), "items", generar_sql=False)

        assert _count_rows(engine) == 20
        assert _audit_rows(audit_path)["total_filas"].tolist() == [10, 10]

    def test_periodic_commit_flushes_earlier_operations_and_rollback_discards_the_rest(
        self, engine: Engine, audit_path: Path
    ) -> None:
        crud = BulkCrud(engine, chunk_size=10, commit_every_n_chunks=2, audit_csv_path=audit_path)

        with pytest.raises(IntegrityError):
            with crud.bulk_session():
                crud.bulk_insert_from_df(_df(range(0, 10)), "items", generar_sql=False)  # lote 1: pendiente
                crud.bulk_insert_from_df(_df(range(10, 20)), "items", generar_sql=False)  # lote 2: commit
                crud.bulk_insert_from_df(_df(range(20, 30)), "items", generar_sql=False)  # lote 3: pendiente
                crud.bulk_insert_from_df(_df([0]), "items", generar_sql=False)  # falla: se deshace el lote 3

        assert _count_rows(engine) == 20
        assert _audit_rows(audit_path)["total_filas"].tolist() == [10, 10]

    def test_commit_in_the_middle_of_an_operation_flushes_the_previous_one(
        self, engine: Engine, audit_path: Path
    ) -> None:
        # Sin el gancho de commit periódico la operación 1, ya confirmada, se descartaría con el rollback.
        crud = BulkCrud(engine, chunk_size=10, commit_every_n_chunks=2, audit_csv_path=audit_path)

        with pytest.raises(IntegrityError):
            with crud.bulk_session():
                crud.bulk_insert_from_df(_df(range(0, 10)), "items", generar_sql=False)  # lote 1: pendiente
                crud.bulk_insert_from_df(_df(range(10, 30)), "items", generar_sql=False)  # lote 2: commit; lote 3 no
                crud.bulk_insert_from_df(_df([0]), "items", generar_sql=False)  # falla: se deshace el lote 3

        assert _count_rows(engine) == 20
        # La operación 2 quedó confirmada a medias: no se audita (rows_committed da la cifra real).
        assert _audit_rows(audit_path)["total_filas"].tolist() == [10]
        assert crud.rows_committed == 20

    def test_session_end_commit_flushes_the_tail(self, engine: Engine, audit_path: Path) -> None:
        crud = BulkCrud(engine, chunk_size=10, commit_every_n_chunks=3, audit_csv_path=audit_path)

        with crud.bulk_session():
            crud.bulk_insert_from_df(_df(range(0, 10)), "items", generar_sql=False)
            crud.bulk_delete_from_df(_df([0, 1]), "items", generar_sql=False)

        assert _audit_rows(audit_path)["operacion"].tolist() == ["INSERT", "DELETE"]


class TestParallelLoaderRetries:
    def test_retried_partition_is_audited_once(self, engine: Engine, audit_path: Path) -> None:
        attempts = {"n": 0}

        def reader() -> Iterator[pd.DataFrame]:
            attempts["n"] += 1
            yield _df(range(0, 10))
            if attempts["n"] == 1:
                raise OperationalError("SELECT 1", {}, Exception("conexión perdida"), connection_invalidated=True)
            yield _df(range(10, 20))

        loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=1, max_retries=1, audit_csv_path=audit_path)
        result = loader.load("items", [reader])

        assert result.partition_errors == []
        assert attempts["n"] == 2
        assert _count_rows(engine) == 20
        audit = _audit_rows(audit_path)
        assert len(audit) == 2
        assert audit["total_filas"].sum() == 20
