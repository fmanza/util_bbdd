"""Política de auditoría en ``ParallelBulkLoader`` y ``dump`` (audit-code de AuditManager 2026-09-25).

El loader crea una ``BulkCrud`` por partición: ahora le pasa ``audit_strict`` y recoge su ``audit_failures`` en
``PartitionResult`` / ``ParallelLoadResult``. ``dump`` lo propaga con ``DumpConfig.bulk_audit_strict`` y lo resume en
``DumpAuditSummary.audit_failures``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk import ParallelBulkLoader
from util_bbdd.bulk.audit import AuditManager
from util_bbdd.dump import DumpConfig, DumpOrchestrator

pytestmark = pytest.mark.unit

_DDL = "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"


def _engine(path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as conn:
        conn.exec_driver_sql(_DDL)
    return eng


def _count(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM items")).scalar_one()


def _reader(start: int, calls: list[int]) -> Callable[[], Iterator[pd.DataFrame]]:
    """Partición de 20 filas en 2 chunks de 10; anota cada invocación."""

    def read() -> Iterator[pd.DataFrame]:
        calls.append(start)
        for offset in (0, 10):
            ids = range(start + offset, start + offset + 10)
            yield pd.DataFrame({"id": list(ids), "name": [f"n{i}" for i in ids]})

    return read


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = _engine(tmp_path / "db.sqlite")
    yield eng
    eng.dispose()


class TestParallelBulkLoaderAudit:
    def test_without_failures_counters_are_zero(self, engine: Engine, tmp_path: Path) -> None:
        calls: list[int] = []
        loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=1, audit_csv_path=tmp_path / "audit.csv")

        result = loader.load("items", [_reader(0, calls), _reader(100, calls)])

        assert result.partition_errors == []
        assert result.audit_failures == 0
        assert all(pr.audit_failures == 0 for pr in result.partition_results)

    def test_fail_open_counts_lost_records_per_partition_and_in_total(self, engine: Engine, tmp_path: Path) -> None:
        calls: list[int] = []
        loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=1, audit_csv_path=tmp_path / "audit.csv")

        with patch.object(AuditManager, "_registrar_lote", side_effect=OSError("CSV bloqueado")):
            result = loader.load("items", [_reader(0, calls), _reader(100, calls)])

        assert result.partition_errors == []
        assert _count(engine) == 40
        assert sorted(pr.audit_failures for pr in result.partition_results) == [2, 2]
        assert result.audit_failures == 4

    def test_strict_rolls_back_the_partition_without_retrying(self, engine: Engine, tmp_path: Path) -> None:
        calls: list[int] = []
        loader = ParallelBulkLoader(
            engine,
            chunk_size=10,
            max_workers=1,
            max_retries=2,
            audit_csv_path=tmp_path / "audit.csv",
            audit_strict=True,
        )

        with patch.object(AuditManager, "_registrar_lote", side_effect=OSError("CSV bloqueado")):
            result = loader.load("items", [_reader(0, calls)])

        assert len(result.partition_errors) == 1
        assert "CSV bloqueado" in result.partition_errors[0]
        assert _count(engine) == 0
        assert calls == [0]  # sin reintentos: el fallo de auditoría es permanente
        assert result.partition_results[0].retries == 0
        assert result.audit_failures == 0


class TestDumpAudit:
    def _config(self, tmp_path: Path, **kwargs: object) -> tuple[DumpConfig, Engine]:
        src = _engine(tmp_path / "src.sqlite")
        with src.begin() as conn:
            conn.exec_driver_sql("INSERT INTO items (id, name) VALUES (1, 'a'), (2, 'b'), (3, 'c')")
        dst = _engine(tmp_path / "dst.sqlite")
        audit_path = tmp_path / "audit.csv"
        audit_path.mkdir()  # el CSV no se puede escribir
        cfg = DumpConfig(
            source_engine=src,
            target_engine=dst,
            output_dir=tmp_path / "out",
            bulk_audit_path=audit_path,
            sync_pk_sequences=False,
            **kwargs,  # type: ignore[arg-type]
        )
        return cfg, dst

    def test_fail_open_loads_the_data_and_reports_audit_failures(self, tmp_path: Path) -> None:
        cfg, dst = self._config(tmp_path)

        result = DumpOrchestrator(cfg).run()

        assert _count(dst) == 3
        assert [r.status for r in result.table_results] == ["success"]
        assert result.audit_summary is not None
        assert result.audit_summary.audit_failures == 1
        assert result.audit_summary.total_operaciones == 0

    def test_strict_fails_the_table_and_loads_nothing(self, tmp_path: Path) -> None:
        cfg, dst = self._config(tmp_path, bulk_audit_strict=True)

        result = DumpOrchestrator(cfg).run()

        assert _count(dst) == 0
        assert [r.status for r in result.table_results] == ["error"]
        assert result.audit_summary is None
