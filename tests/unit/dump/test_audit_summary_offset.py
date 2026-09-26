"""3.4 / PF-08: el resumen de auditoría del volcado lee solo lo añadido al CSV desde el inicio del volcado."""

from __future__ import annotations

import csv

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from util_bbdd.dump.orchestrator import DumpOrchestrator

pytestmark = pytest.mark.unit

HEADER = ["timestamp", "tabla", "motor", "operacion", "total_filas", "tiempo_seg", "sql"]


def _append(path: Path, rows: list[list[object]], *, header: bool = False) -> None:
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        if header:
            writer.writerow(HEADER)
        writer.writerows(rows)


def _row(ts: str, tabla: str, filas: int) -> list[object]:
    return [ts, tabla, "POSTGRESQL", "INSERT", filas, "0,125", "No"]


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    path = tmp_path / "audit.csv"
    _append(path, [_row("2025-01-01 00:00:00", "viejo", 5000) for _ in range(50)], header=True)
    return path


def test_tail_read_gives_the_same_summary_as_full_read(csv_path: Path) -> None:
    offset = csv_path.stat().st_size
    _append(csv_path, [_row("2026-09-26 10:00:01", "a", 100), _row("2026-09-26 10:00:02", "b", 200)])
    desde = datetime(2026, 9, 26, 10, 0, 0)

    full = DumpOrchestrator._build_audit_summary(csv_path, desde, audited_rows=300)
    tail = DumpOrchestrator._build_audit_summary(csv_path, desde, audited_rows=300, start_offset=offset)

    assert tail == full
    assert tail is not None and (tail.total_operaciones, tail.total_filas) == (2, 300)


def test_tail_read_only_parses_new_rows(csv_path: Path) -> None:
    offset = csv_path.stat().st_size
    _append(csv_path, [_row("2026-09-26 10:00:01", "a", 100)])
    df = DumpOrchestrator._read_audit_csv(csv_path, offset)
    assert df["tabla"].tolist() == ["a"]
    assert df["tiempo_seg"].tolist() == [0.125]
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])


def test_offset_in_the_middle_of_a_row_skips_the_partial_row(csv_path: Path) -> None:
    offset = csv_path.stat().st_size - 5  # a mitad de la última fila vieja (escrita por otro proceso)
    _append(csv_path, [_row("2026-09-26 10:00:01", "a", 100)])
    assert DumpOrchestrator._read_audit_csv(csv_path, offset)["tabla"].tolist() == ["a"]


def test_shrunk_file_falls_back_to_full_read(csv_path: Path) -> None:
    offset = csv_path.stat().st_size + 10_000  # el fichero es ahora más pequeño: se truncó o rotó
    assert len(DumpOrchestrator._read_audit_csv(csv_path, offset)) == 50


@pytest.mark.parametrize("offset", [None, 0])
def test_without_offset_reads_everything(csv_path: Path, offset: int | None) -> None:
    assert len(DumpOrchestrator._read_audit_csv(csv_path, offset)) == 50


def test_file_created_during_the_dump(tmp_path: Path) -> None:
    path = tmp_path / "nuevo.csv"
    assert DumpOrchestrator._file_size(path) is None  # no existía al empezar
    _append(path, [_row("2026-09-26 10:00:01", "a", 100)], header=True)
    assert DumpOrchestrator._read_audit_csv(path, None)["tabla"].tolist() == ["a"]
