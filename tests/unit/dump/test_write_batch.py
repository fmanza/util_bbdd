"""Q5 (roadmap de dump, paso 2.1): lote de escritura separado del de lectura (``DumpConfig.write_batch_size``)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import create_engine, text

from util_bbdd.dump import DumpConfig, DumpOrchestrator
from util_bbdd.dump.orchestrator import _rebatch

pytestmark = pytest.mark.unit


def _engine(dialect: str) -> MagicMock:
    engine = MagicMock()
    engine.dialect.name = dialect
    return engine


def _orch(dialect: str, **kwargs: object) -> DumpOrchestrator:
    orch = DumpOrchestrator.__new__(DumpOrchestrator)
    orch._cfg = DumpConfig(source_engine=_engine("postgresql"), target_engine=_engine(dialect), **kwargs)  # type: ignore[arg-type]
    return orch


class TestDumpConfigValidation:
    @pytest.mark.parametrize("value", [0, -5])
    def test_rejects_non_positive(self, value: int) -> None:
        with pytest.raises(ValueError, match="write_batch_size"):
            DumpConfig(source_engine=_engine("postgresql"), target_engine=_engine("postgresql"), write_batch_size=value)

    def test_default_is_none(self) -> None:
        assert DumpConfig(source_engine=_engine("x"), target_engine=_engine("y")).write_batch_size is None


class TestResolveWriteBatchSize:
    def test_postgresql_default_is_20000(self) -> None:
        assert _orch("postgresql")._resolve_write_batch_size() == 20_000

    def test_postgresql_keeps_a_larger_chunk_size(self) -> None:
        assert _orch("postgresql", chunk_size=50_000)._resolve_write_batch_size() == 50_000

    def test_postgresql_with_periodic_commits_keeps_chunk_size(self) -> None:
        """commit_every_n_chunks cuenta lotes de escritura: no se cambia cada cuántas filas se confirma."""
        assert _orch("postgresql", commit_every_n_chunks=10)._resolve_write_batch_size() == 5000

    @pytest.mark.parametrize("dialect", ["mssql", "oracle", "mysql", "mariadb", "sqlite"])
    def test_other_targets_use_chunk_size(self, dialect: str) -> None:
        assert _orch(dialect, chunk_size=3000)._resolve_write_batch_size() == 3000

    @pytest.mark.parametrize("dialect", ["postgresql", "mssql"])
    def test_explicit_value_wins(self, dialect: str) -> None:
        assert _orch(dialect, write_batch_size=1234)._resolve_write_batch_size() == 1234


class TestRebatch:
    @staticmethod
    def _chunks(sizes: list[int]) -> list[pd.DataFrame]:
        start, out = 0, []
        for n in sizes:
            out.append(pd.DataFrame({"id": range(start, start + n)}, dtype=object))
            start += n
        return out

    def test_groups_until_size_and_keeps_order(self) -> None:
        batches = list(_rebatch(iter(self._chunks([5, 5, 5, 5, 3])), 10))
        assert [len(b) for b in batches] == [10, 10, 3]
        assert pd.concat(batches)["id"].tolist() == list(range(23))
        assert all(list(b.index) == list(range(len(b))) for b in batches)

    def test_single_large_chunk_is_passed_through(self) -> None:
        chunk = self._chunks([25])[0]
        assert next(_rebatch(iter([chunk]), 10)) is chunk

    def test_empty(self) -> None:
        assert list(_rebatch(iter([]), 10)) == []


def test_dump_with_explicit_write_batch_size_loads_every_row(tmp_path: Path) -> None:
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    for eng in (src, dst):
        with eng.begin() as conn:
            conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
    with src.begin() as conn:
        conn.execute(text("INSERT INTO t (id, v) VALUES (:i, 'x')"), [{"i": i} for i in range(1, 1001)])

    result = DumpOrchestrator(
        DumpConfig(source_engine=src, target_engine=dst, output_dir=tmp_path, chunk_size=100, write_batch_size=350)
    ).run()

    assert [r.status for r in result.table_results] == ["success"]
    with dst.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*), SUM(id) FROM t")).one() == (1000, 500500)
    src.dispose()
    dst.dispose()
