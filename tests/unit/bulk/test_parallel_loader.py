"""Tests de ParallelBulkLoader (carga masiva paralela por particiones)."""

from __future__ import annotations

import contextlib
import logging

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError

import util_bbdd.bulk._execution.parallel_loader as pl_mod

from util_bbdd.bulk import ParallelBulkLoader, ParallelLoadResult


class TestParallelBulkLoaderValidation:
    def test_max_workers_below_1_raises(self) -> None:
        with pytest.raises(ValueError, match="max_workers"):
            ParallelBulkLoader(MagicMock(), max_workers=0)

    def test_no_readers_returns_empty_result(self) -> None:
        loader = ParallelBulkLoader(MagicMock(), max_workers=4)
        result = loader.load("t", [])
        assert result == ParallelLoadResult(total_rows=0, partition_errors=[])


class TestParallelBulkLoaderOrchestration:
    def test_one_crud_per_partition_and_aggregates_rows(self) -> None:
        readers = [lambda: iter([]) for _ in range(3)]

        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.return_value = 10
            loader = ParallelBulkLoader(MagicMock(), chunk_size=5, max_workers=3)
            result = loader.load("dbo.t", readers)

        assert crud_cls.call_count == 3
        assert result.total_rows == 30
        assert result.partition_errors == []

    def test_partition_error_is_captured_others_continue(self) -> None:
        readers = [lambda: iter([]) for _ in range(3)]

        calls = {"n": 0}

        def _make(*_args: object, **_kwargs: object) -> MagicMock:
            crud = MagicMock()
            calls["n"] += 1
            if calls["n"] == 2:  # la 2ª partición falla
                crud.bulk_insert_from_chunks.side_effect = SQLAlchemyError("boom")
            else:
                crud.bulk_insert_from_chunks.return_value = 7
            return crud

        with patch.object(pl_mod, "BulkCrud", side_effect=_make):
            loader = ParallelBulkLoader(MagicMock(), max_workers=3)
            result = loader.load("t", readers)

        assert result.total_rows == 14  # 2 particiones OK × 7
        assert len(result.partition_errors) == 1
        assert "boom" in result.partition_errors[0]

    def test_workers_capped_to_number_of_partitions(self) -> None:
        import concurrent.futures as cf

        real_tpe = cf.ThreadPoolExecutor
        captured: dict[str, int | None] = {}

        def _spy(max_workers: int | None = None, **kwargs: object) -> cf.ThreadPoolExecutor:
            captured["mw"] = max_workers
            return real_tpe(max_workers=max_workers)

        readers = [lambda: iter([])]
        with patch.object(pl_mod, "ThreadPoolExecutor", side_effect=_spy), patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.return_value = 0
            ParallelBulkLoader(MagicMock(), max_workers=8).load("t", readers)

        # max_workers se acota al nº de particiones (1), no 8
        assert captured["mw"] == 1


class TestParallelLoadResultMetrics:
    def test_rows_per_second_returns_correct_ratio(self) -> None:
        result = ParallelLoadResult(total_rows=1000, elapsed_seconds=2.0)
        assert result.rows_per_second == pytest.approx(500.0)

    def test_rows_per_second_zero_when_elapsed_zero(self) -> None:
        result = ParallelLoadResult(total_rows=100, elapsed_seconds=0.0)
        assert result.rows_per_second == pytest.approx(0.0, abs=1e-9)

    def test_rows_per_second_zero_when_elapsed_negative(self) -> None:
        result = ParallelLoadResult(total_rows=100, elapsed_seconds=-1.0)
        assert result.rows_per_second == pytest.approx(0.0, abs=1e-9)

    def test_partition_results_populated_on_load(self) -> None:
        readers = [lambda: iter([]) for _ in range(2)]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.return_value = 5
            loader = ParallelBulkLoader(MagicMock(), max_workers=2)
            result = loader.load("t", readers)

        assert len(result.partition_results) == 2
        assert all(isinstance(pr, pl_mod.PartitionResult) for pr in result.partition_results)
        assert sum(pr.rows for pr in result.partition_results) == result.total_rows

    def test_elapsed_seconds_populated_after_load(self) -> None:
        readers = [lambda: iter([])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.return_value = 0
            loader = ParallelBulkLoader(MagicMock(), max_workers=1)
            result = loader.load("t", readers)

        assert result.elapsed_seconds >= 0.0

    def test_empty_readers_has_zero_elapsed(self) -> None:
        result = ParallelBulkLoader(MagicMock(), max_workers=1).load("t", [])
        assert result.elapsed_seconds == pytest.approx(0.0, abs=1e-9)
        assert result.partition_results == []


class TestParallelBulkLoaderNewParameters:
    def test_max_retries_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            ParallelBulkLoader(MagicMock(), max_retries=-1)

    def test_max_retries_zero_is_valid(self) -> None:
        loader = ParallelBulkLoader(MagicMock(), max_retries=0)
        assert loader._max_retries == 0

    def test_disable_constraints_default_false(self) -> None:
        loader = ParallelBulkLoader(MagicMock())
        assert loader._disable_constraints is False

    def test_disable_constraints_true_stored(self) -> None:
        loader = ParallelBulkLoader(MagicMock(), disable_constraints=True)
        assert loader._disable_constraints is True

    def test_pool_size_warning_emitted(self, caplog: pytest.LogCaptureFixture) -> None:
        engine = MagicMock()
        engine.pool.size.return_value = 2
        with caplog.at_level(logging.WARNING, logger="util_bbdd.bulk._execution.parallel_loader"):
            ParallelBulkLoader(engine, max_workers=4)
        assert any("pool size" in m for m in caplog.messages)

    def test_pool_size_no_warning_when_sufficient(self, caplog: pytest.LogCaptureFixture) -> None:
        engine = MagicMock()
        engine.pool.size.return_value = 4
        with caplog.at_level(logging.WARNING, logger="util_bbdd.bulk._execution.parallel_loader"):
            ParallelBulkLoader(engine, max_workers=4)
        assert not any("pool size" in m for m in caplog.messages)


class TestParallelBulkLoaderRetry:
    def test_retries_on_timeout_error_then_succeeds(self) -> None:
        call_count: dict[str, int] = {"n": 0}

        def _side_effect(*_args: object, **_kwargs: object) -> int:
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise TimeoutError("connection timed out")
            return 10

        readers = [lambda: iter([])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.side_effect = _side_effect
            loader = ParallelBulkLoader(MagicMock(), max_workers=1, max_retries=2)
            result = loader.load("t", readers)

        assert result.total_rows == 10
        assert result.partition_errors == []
        assert call_count["n"] == 3

    def test_retries_exhausted_captures_error(self) -> None:
        readers = [lambda: iter([])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.side_effect = TimeoutError("timeout")
            loader = ParallelBulkLoader(MagicMock(), max_workers=1, max_retries=2)
            result = loader.load("t", readers)

        assert len(result.partition_errors) == 1
        assert result.partition_results[0].retries == 2
        assert result.partition_results[0].rows == 0

    def test_permanent_error_not_retried(self) -> None:
        call_count: dict[str, int] = {"n": 0}

        def _permanent(*_args: object, **_kwargs: object) -> int:
            call_count["n"] += 1
            raise SQLAlchemyError("integrity violation")

        readers = [lambda: iter([])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.side_effect = _permanent
            loader = ParallelBulkLoader(MagicMock(), max_workers=1, max_retries=3)
            result = loader.load("t", readers)

        assert call_count["n"] == 1  # no retry for permanent errors
        assert len(result.partition_errors) == 1

    def test_partition_result_retries_zero_on_success(self) -> None:
        readers = [lambda: iter([])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.return_value = 5
            loader = ParallelBulkLoader(MagicMock(), max_workers=1, max_retries=3)
            result = loader.load("t", readers)

        assert result.partition_results[0].retries == 0


class TestParallelBulkLoaderDisableConstraints:
    def test_disable_constraints_calls_maintenance_scope_not_chunks(self) -> None:
        df = pd.DataFrame({"id": [1, 2], "v": ["a", "b"]})
        readers = [lambda: iter([df])]

        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_mock = MagicMock()
            crud_cls.return_value = crud_mock
            loader = ParallelBulkLoader(MagicMock(), max_workers=1, disable_constraints=True)
            result = loader.load("orders", readers)

        crud_mock.bulk_session.assert_called_once()
        crud_mock.maintenance_scope.assert_called_once_with("orders", disable_constraints=True, disable_indexes=False)
        crud_mock.bulk_insert_from_df.assert_called_once()
        crud_mock.bulk_insert_from_chunks.assert_not_called()
        assert result.total_rows == 2

    def test_disable_constraints_false_uses_bulk_insert_from_chunks(self) -> None:
        readers = [lambda: iter([])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.return_value = 7
            loader = ParallelBulkLoader(MagicMock(), max_workers=1, disable_constraints=False)
            result = loader.load("t", readers)

        crud_cls.return_value.bulk_session.assert_not_called()
        crud_cls.return_value.maintenance_scope.assert_not_called()
        assert result.total_rows == 7

    def test_disable_constraints_skips_empty_chunks(self) -> None:
        readers = [lambda: iter([pd.DataFrame(), pd.DataFrame({"id": [1]})])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_mock = MagicMock()
            crud_cls.return_value = crud_mock
            loader = ParallelBulkLoader(MagicMock(), max_workers=1, disable_constraints=True)
            result = loader.load("t", readers)

        # Solo el chunk no vacío llama a bulk_insert_from_df
        assert crud_mock.bulk_insert_from_df.call_count == 1
        assert result.total_rows == 1


class TestParallelBulkLoaderPoolSizeCap:
    """F-03: max_workers se acota a pool_size para evitar deadlock."""

    def test_max_workers_capped_to_pool_size(self) -> None:
        engine = MagicMock()
        engine.pool.size.return_value = 2
        loader = ParallelBulkLoader(engine, max_workers=4)
        assert loader._max_workers == 2

    def test_max_workers_not_capped_when_pool_sufficient(self) -> None:
        engine = MagicMock()
        engine.pool.size.return_value = 4
        loader = ParallelBulkLoader(engine, max_workers=4)
        assert loader._max_workers == 4

    def test_cap_emits_warning_with_pool_size_text(self, caplog: pytest.LogCaptureFixture) -> None:
        engine = MagicMock()
        engine.pool.size.return_value = 2
        with caplog.at_level(logging.WARNING, logger="util_bbdd.bulk._execution.parallel_loader"):
            ParallelBulkLoader(engine, max_workers=4)
        assert any("pool size" in m for m in caplog.messages)

    def test_no_cap_when_pool_size_equals_max_workers(self) -> None:
        engine = MagicMock()
        engine.pool.size.return_value = 3
        loader = ParallelBulkLoader(engine, max_workers=3)
        assert loader._max_workers == 3

    def test_no_cap_for_null_pool(self) -> None:
        engine = MagicMock()
        engine.pool = None
        loader = ParallelBulkLoader(engine, max_workers=8)
        assert loader._max_workers == 8


class TestParallelBulkLoaderCommitRetryGuard:
    """F-04+F-07: commit_every_n_chunks y max_retries > 0 son incompatibles."""

    def test_commit_cadence_with_retries_raises(self) -> None:
        with pytest.raises(ValueError, match="incompatibles"):
            ParallelBulkLoader(MagicMock(), commit_every_n_chunks=10, max_retries=1)

    def test_commit_cadence_with_retries_zero_is_valid(self) -> None:
        loader = ParallelBulkLoader(MagicMock(), commit_every_n_chunks=10, max_retries=0)
        assert loader._commit_every_n_chunks == 10

    def test_no_commit_cadence_with_retries_is_valid(self) -> None:
        loader = ParallelBulkLoader(MagicMock(), commit_every_n_chunks=None, max_retries=3)
        assert loader._max_retries == 3


class TestParallelBulkLoaderConstraintHoist:
    """F-05: constraints se deshabilitan una sola vez antes del pool (MSSQL y PostgreSQL)."""

    def test_mssql_hoist_executes_nocheck_sql(self) -> None:
        engine = MagicMock()
        engine.dialect.name = "mssql"
        executed_sqls: list[str] = []
        conn_mock = engine.begin.return_value.__enter__.return_value
        conn_mock.execute.side_effect = lambda stmt: executed_sqls.append(str(stmt))

        readers = [lambda: iter([])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.return_value = 0
            loader = ParallelBulkLoader(engine, max_workers=1, disable_constraints=True)
            loader.load("dbo.orders", readers)

        assert any("NOCHECK" in sql.upper() for sql in executed_sqls)
        assert any("WITH CHECK" in sql.upper() for sql in executed_sqls)

    def test_mssql_hoist_workers_skip_maintenance_scope(self) -> None:
        engine = MagicMock()
        engine.dialect.name = "mssql"
        df = pd.DataFrame({"id": [1], "v": ["a"]})
        readers = [lambda: iter([df])]

        with patch.object(pl_mod, "BulkCrud") as crud_cls, patch.object(
            pl_mod.ParallelBulkLoader,
            "_hoist_constraints_for_workers",
            return_value=contextlib.nullcontext(True),
        ):
            crud_mock = MagicMock()
            crud_cls.return_value = crud_mock
            loader = ParallelBulkLoader(engine, max_workers=1, disable_constraints=True)
            loader.load("dbo.orders", readers)

        crud_mock.bulk_insert_from_chunks.assert_called_once()
        crud_mock.maintenance_scope.assert_not_called()

    def test_postgresql_hoist_executes_disable_trigger_sql(self) -> None:
        engine = MagicMock()
        engine.dialect.name = "postgresql"
        executed_sqls: list[str] = []
        conn_mock = engine.begin.return_value.__enter__.return_value
        # El check de privilegios devuelve True
        conn_mock.execute.return_value.scalar.return_value = True
        conn_mock.execute.side_effect = lambda stmt, *a, **kw: (
            executed_sqls.append(str(stmt)) or conn_mock.execute.return_value
        )

        readers = [lambda: iter([])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.return_value = 0
            loader = ParallelBulkLoader(engine, max_workers=1, disable_constraints=True)
            loader.load("public.orders", readers)

        assert any("DISABLE TRIGGER" in sql.upper() for sql in executed_sqls)
        assert any("ENABLE TRIGGER" in sql.upper() for sql in executed_sqls)

    def test_postgresql_hoist_workers_skip_maintenance_scope(self) -> None:
        engine = MagicMock()
        engine.dialect.name = "postgresql"
        df = pd.DataFrame({"id": [1], "v": ["a"]})
        readers = [lambda: iter([df])]

        with patch.object(pl_mod, "BulkCrud") as crud_cls, patch.object(
            pl_mod.ParallelBulkLoader,
            "_hoist_constraints_for_workers",
            return_value=contextlib.nullcontext(True),
        ):
            crud_mock = MagicMock()
            crud_cls.return_value = crud_mock
            loader = ParallelBulkLoader(engine, max_workers=1, disable_constraints=True)
            loader.load("public.orders", readers)

        crud_mock.bulk_insert_from_chunks.assert_called_once()
        crud_mock.maintenance_scope.assert_not_called()

    def test_postgresql_no_privileges_falls_back_to_per_worker(self) -> None:
        engine = MagicMock()
        engine.dialect.name = "postgresql"
        df = pd.DataFrame({"id": [1], "v": ["a"]})
        readers = [lambda: iter([df])]

        with patch.object(pl_mod, "BulkCrud") as crud_cls, patch.object(
            pl_mod.ParallelBulkLoader,
            "_hoist_constraints_for_workers",
            return_value=contextlib.nullcontext(False),
        ):
            crud_mock = MagicMock()
            crud_cls.return_value = crud_mock
            loader = ParallelBulkLoader(engine, max_workers=1, disable_constraints=True)
            loader.load("public.orders", readers)

        # Sin hoist (skip_maintenance=False): workers usan _load_with_maintenance
        crud_mock.bulk_session.assert_called_once()
        crud_mock.maintenance_scope.assert_called_once()
        crud_mock.bulk_insert_from_chunks.assert_not_called()

    def test_mysql_disable_constraints_uses_per_worker_no_hoist(self) -> None:
        """MySQL/MariaDB usa SET SESSION — sin lock DDL, no necesita hoist."""
        engine = MagicMock()
        engine.dialect.name = "mysql"
        df = pd.DataFrame({"id": [1], "v": ["a"]})
        readers = [lambda: iter([df])]

        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_mock = MagicMock()
            crud_cls.return_value = crud_mock
            loader = ParallelBulkLoader(engine, max_workers=1, disable_constraints=True)
            loader.load("orders", readers)

        # MySQL dialect → _hoist_constraints_for_workers yield False → per-worker
        crud_mock.bulk_session.assert_called_once()
        crud_mock.maintenance_scope.assert_called_once()


class TestParallelBulkLoaderPartitionRanges:
    """F-08: Validación de rangos de partición no solapados."""

    def test_overlapping_ranges_raise_value_error(self) -> None:
        readers = [lambda: iter([]), lambda: iter([])]
        loader = ParallelBulkLoader(MagicMock(), max_workers=2)
        with pytest.raises(ValueError, match="solapados"):
            loader.load("t", readers, partition_ranges=[(1, 5), (5, 10)])

    def test_mismatched_ranges_count_raises_value_error(self) -> None:
        readers = [lambda: iter([]), lambda: iter([])]
        loader = ParallelBulkLoader(MagicMock(), max_workers=2)
        with pytest.raises(ValueError, match="longitud"):
            loader.load("t", readers, partition_ranges=[(1, 5)])

    def test_valid_disjoint_ranges_accepted(self) -> None:
        readers = [lambda: iter([]), lambda: iter([])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.return_value = 0
            loader = ParallelBulkLoader(MagicMock(), max_workers=2)
            result = loader.load("t", readers, partition_ranges=[(1, 5), (6, 10)])
        assert result.partition_errors == []

    def test_none_ranges_skips_validation(self) -> None:
        readers = [lambda: iter([])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.return_value = 0
            result = ParallelBulkLoader(MagicMock(), max_workers=1).load(
                "t", readers, partition_ranges=None
            )
        assert result.partition_errors == []

    def test_adjacent_ranges_not_considered_overlapping(self) -> None:
        readers = [lambda: iter([]), lambda: iter([])]
        with patch.object(pl_mod, "BulkCrud") as crud_cls:
            crud_cls.return_value.bulk_insert_from_chunks.return_value = 0
            loader = ParallelBulkLoader(MagicMock(), max_workers=2)
            result = loader.load("t", readers, partition_ranges=[(1, 4), (5, 8)])
        assert result.partition_errors == []


class TestParallelBulkLoaderEndToEnd:
    def _make_file_engine(self, tmp_path: Path) -> Engine:
        db = tmp_path / "parallel.db"
        engine = create_engine(f"sqlite:///{db}", connect_args={"timeout": 30})
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        return engine

    def test_disjoint_partitions_all_persist(self, tmp_path: Path) -> None:
        engine = self._make_file_engine(tmp_path)

        def reader_lo():
            return iter([pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})])

        def reader_hi():
            return iter([pd.DataFrame({"id": [4, 5], "name": ["d", "e"]})])

        loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=2)
        result = loader.load("items", [reader_lo, reader_hi])

        assert result.partition_errors == []
        assert result.total_rows == 5
        with engine.connect() as conn:
            assert int(conn.exec_driver_sql("SELECT COUNT(*) FROM items").scalar() or 0) == 5
