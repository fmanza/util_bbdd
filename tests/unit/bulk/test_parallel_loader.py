"""Tests de ParallelBulkLoader (carga masiva paralela por particiones)."""

from __future__ import annotations

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
