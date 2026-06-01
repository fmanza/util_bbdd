"""Tests de ParallelBulkLoader (carga masiva paralela por particiones)."""

from __future__ import annotations

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
