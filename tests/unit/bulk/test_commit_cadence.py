"""Tests de la cadencia de commit por lotes (commit_every_n_chunks)."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, create_engine, insert

from util_bbdd.bulk._execution.batch import BatchStatementExecutor
from util_bbdd.bulk.crud import BulkCrud

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sqlite_engine() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    return engine


def _table() -> Table:
    return Table(
        "items",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
    )


# ---------------------------------------------------------------------------
# Validación del parámetro
# ---------------------------------------------------------------------------


class TestCommitCadenceValidation:
    def test_zero_raises_value_error(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        with pytest.raises(ValueError, match="commit_every_n_chunks"):
            BulkCrud(engine, commit_every_n_chunks=0)

    def test_negative_raises_value_error(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        with pytest.raises(ValueError, match="commit_every_n_chunks"):
            BulkCrud(engine, commit_every_n_chunks=-3)

    def test_none_is_accepted(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        crud = BulkCrud(engine, commit_every_n_chunks=None)
        assert crud._batch_statement_executor.cadence.every is None


# ---------------------------------------------------------------------------
# Path por defecto (None) — comportamiento inalterado: usa engine.begin()
# ---------------------------------------------------------------------------


class TestDefaultPathUnchanged:
    def test_execute_without_cadence_uses_engine_begin(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        records = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}, {"id": 3, "name": "c"}]
        connection = MagicMock()

        class _BeginCtx:
            def __enter__(self) -> Any:
                return connection

            def __exit__(self, *_: object) -> None:
                return None

        cast(Any, engine).begin = MagicMock(return_value=_BeginCtx())
        cast(Any, engine).connect = MagicMock()

        executor = BatchStatementExecutor(engine=engine, chunk_size=2)
        executor.execute(records=records, stmt=insert(_table()))

        cast(Any, engine).begin.assert_called_once()
        cast(Any, engine).connect.assert_not_called()
        # Sin cadencia no se commitea manualmente sobre la conexión
        connection.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Path con cadencia — usa engine.connect() y commitea cada N lotes + tail
# ---------------------------------------------------------------------------


class TestCadenceCommits:
    def test_execute_with_cadence_uses_connect_and_commits_every_n(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        # 5 lotes de chunk_size=1 → con cadencia=2: commits en lotes 2 y 4, + tail final
        records = [{"id": i, "name": f"n{i}"} for i in range(1, 6)]
        connection = MagicMock()

        class _ConnectCtx:
            def __enter__(self) -> Any:
                return connection

            def __exit__(self, *_: object) -> None:
                return None

        cast(Any, engine).connect = MagicMock(return_value=_ConnectCtx())
        cast(Any, engine).begin = MagicMock()

        executor = BatchStatementExecutor(engine=engine, chunk_size=1, commit_every_n_chunks=2)
        executor.execute(records=records, stmt=insert(_table()))

        cast(Any, engine).connect.assert_called_once()
        cast(Any, engine).begin.assert_not_called()
        # 2 commits periódicos (tras lote 2 y 4) + 1 commit final del tail
        assert connection.commit.call_count == 3

    def test_counter_resets_after_each_commit(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        records = [{"id": i, "name": f"n{i}"} for i in range(1, 5)]  # 4 lotes
        connection = MagicMock()

        class _ConnectCtx:
            def __enter__(self) -> Any:
                return connection

            def __exit__(self, *_: object) -> None:
                return None

        cast(Any, engine).connect = MagicMock(return_value=_ConnectCtx())

        executor = BatchStatementExecutor(engine=engine, chunk_size=1, commit_every_n_chunks=2)
        executor.execute(records=records, stmt=insert(_table()))

        # 4 lotes / cadencia 2 → 2 commits periódicos; tail vacío → +1 commit final no-op
        assert connection.commit.call_count == 3
        assert executor.cadence.batches == 0


# ---------------------------------------------------------------------------
# Persistencia real con SQLite (end-to-end)
# ---------------------------------------------------------------------------


class TestRowsCommittedTracking:
    """BLK-08 (AUDIT_CODE 2026-09-22): rows_committed debe reflejar solo las filas
    que ya sobrevivieron un commit real, no las ejecutadas-pero-pendientes."""

    def test_rows_committed_stays_zero_without_cadence(self) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, chunk_size=2)  # sin commit_every_n_chunks (modo atómico)
        df = pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})

        crud.bulk_insert_from_df(df, "items", generar_sql=False)

        assert crud.rows_committed == 0

    def test_rows_committed_accumulates_periodic_and_tail_commits(self) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, chunk_size=1, commit_every_n_chunks=2)
        df = pd.DataFrame({"id": [1, 2, 3, 4, 5], "name": ["a", "b", "c", "d", "e"]})

        crud.bulk_insert_from_df(df, "items", generar_sql=False)

        assert crud.rows_committed == 5

    def test_rows_committed_reflects_only_durable_rows_on_mid_batch_failure(self) -> None:
        """5 filas, chunk_size=1, cadencia=2: falla la 4ª sub-tanda tras 1 commit
        periódico (filas 1-2). La fila 3 (ejecutada pero sin commitear) se pierde
        al hacer rollback implícito; rows_committed debe reflejar 2, no 0 ni 5."""
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, chunk_size=1, commit_every_n_chunks=2)
        original_execute = crud._batch_statement_executor._insert_strategy.execute
        call_count = {"n": 0}

        def _flaky_execute(*, connection: Any, stmt: Any, records: Any) -> None:
            call_count["n"] += 1
            if call_count["n"] == 4:
                raise RuntimeError("boom on 4th sub-batch")
            original_execute(connection=connection, stmt=stmt, records=records)

        crud._batch_statement_executor._insert_strategy.execute = _flaky_execute  # type: ignore[method-assign]

        df = pd.DataFrame({"id": [1, 2, 3, 4, 5], "name": ["a", "b", "c", "d", "e"]})
        with pytest.raises(RuntimeError, match="boom"):
            crud.bulk_insert_from_df(df, "items", generar_sql=False)

        assert crud.rows_committed == 2
        with engine.connect() as conn:
            total = conn.exec_driver_sql("SELECT COUNT(*) FROM items").scalar()
        assert total == 2

    def test_rows_undone_by_a_failed_session_are_not_counted_by_the_next_one(self) -> None:
        """La fila 3 del caso anterior se deshizo con la sesión fallida; la siguiente carga que termina bien no debe
        contarla. Antes se quedaba como pendiente y rows_committed daba 4 con 3 filas en la BD."""
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, chunk_size=1, commit_every_n_chunks=2)
        original_execute = crud._batch_statement_executor._insert_strategy.execute
        call_count = {"n": 0}

        def _flaky_execute(*, connection: Any, stmt: Any, records: Any) -> None:
            call_count["n"] += 1
            if call_count["n"] == 4:
                raise RuntimeError("boom on 4th sub-batch")
            original_execute(connection=connection, stmt=stmt, records=records)

        crud._batch_statement_executor._insert_strategy.execute = _flaky_execute  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="boom"):
            crud.bulk_insert_from_df(
                pd.DataFrame({"id": [1, 2, 3, 4, 5], "name": ["a", "b", "c", "d", "e"]}), "items", generar_sql=False
            )

        crud.bulk_insert_from_df(pd.DataFrame({"id": [6], "name": ["f"]}), "items", generar_sql=False)

        with engine.connect() as conn:
            total = conn.exec_driver_sql("SELECT COUNT(*) FROM items").scalar()
        assert total == 3
        assert crud.rows_committed == 3

    def test_delete_periodic_commit_also_confirms_pending_insert_rows(self) -> None:
        """El commit periódico del DELETE confirma la transacción entera de la sesión, incluidas las filas de INSERT
        pendientes. Antes solo contaba el ejecutor que hacía el commit: tras un fallo, rows_committed daba 0 con la fila
        insertada ya confirmada en la BD."""
        engine = _make_sqlite_engine()
        with engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO items VALUES (100, 'x'), (101, 'x')")
        crud = BulkCrud(engine, chunk_size=1, commit_every_n_chunks=2, warn_if_audit_disabled=False)

        with pytest.raises(RuntimeError, match="después del DELETE"), crud.bulk_session():
            crud.bulk_insert_from_df(pd.DataFrame({"id": [1], "name": ["a"]}), "items", generar_sql=False)
            crud.bulk_delete_from_df(pd.DataFrame({"id": [100, 101]}), "items", generar_sql=False)  # commit periódico
            raise RuntimeError("fallo después del DELETE")

        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT id FROM items ORDER BY id").scalars().all() == [1]
        assert crud.rows_committed == 1


class TestCadenceEndToEnd:
    def test_all_rows_persist_with_cadence(self) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, chunk_size=2, commit_every_n_chunks=2)
        df = pd.DataFrame({"id": [1, 2, 3, 4, 5], "name": ["a", "b", "c", "d", "e"]})

        crud.bulk_insert_from_df(df, "items", generar_sql=False)

        with engine.connect() as conn:
            total = conn.exec_driver_sql("SELECT COUNT(*) FROM items").scalar()
        assert total == 5

    def test_bulk_session_with_cadence_persists_tail(self) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, chunk_size=2, commit_every_n_chunks=2)

        with crud.bulk_session():
            for start in range(0, 5, 2):
                df = pd.DataFrame(
                    {
                        "id": list(range(start + 1, min(start + 3, 6))),
                        "name": ["x"] * len(range(start + 1, min(start + 3, 6))),
                    }
                )
                crud.bulk_insert_from_df(df, "items", generar_sql=False)

        with engine.connect() as conn:
            total = conn.exec_driver_sql("SELECT COUNT(*) FROM items").scalar()
        assert total == 5
        # El contador queda limpio tras la sesión
        assert crud._batch_statement_executor.cadence.batches == 0
