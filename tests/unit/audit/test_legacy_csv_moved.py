"""F1 (sesión 2026-10-02c): la auditoría CSV de ``bulk`` vive en ``util_bbdd.audit`` y ``bulk`` solo la re-exporta.

Riesgo principal del traslado: que existan dos registros de locks por ruta (uno en ``bulk`` y otro en ``audit``). Dos
hilos escribirían entonces el mismo CSV con locks distintos e intercalarían filas.
"""

from __future__ import annotations

import threading

from pathlib import Path

import pandas as pd

from util_bbdd.audit import legacy_csv, locks
from util_bbdd.audit.analytics import AuditAnalyticsService
from util_bbdd.audit.counters import AuditCounters
from util_bbdd.audit.exporters import AuditExporters
from util_bbdd.bulk._audit import (
    counters as bulk_counters,
    exporters as bulk_exporters,
    record as bulk_record,
    repository as bulk_repository,
    service as bulk_service,
)
from util_bbdd.bulk.audit import AuditManager


def test_un_solo_registro_de_locks() -> None:
    assert bulk_repository._get_file_lock is locks.path_lock


def test_bulk_re_exporta_las_mismas_clases() -> None:
    assert bulk_repository.AuditCsvRepository is legacy_csv.AuditCsvRepository
    assert bulk_record.AuditRecord is legacy_csv.AuditRecord
    assert bulk_record.AUDIT_OPERATIONS is legacy_csv.AUDIT_OPERATIONS
    assert bulk_service.AuditAnalyticsService is AuditAnalyticsService
    assert bulk_exporters.AuditExporters is AuditExporters
    assert bulk_counters.AuditCounters is AuditCounters


def test_bulk_y_audit_escriben_el_mismo_csv_sin_intercalar(tmp_path: Path) -> None:
    """Una ``AuditManager`` (bulk) y un ``AuditCsvRepository`` directo (audit) en hilos sobre la misma ruta."""
    path = tmp_path / "auditoria.csv"
    n = 200

    def via_bulk() -> None:
        manager = AuditManager(path, cache_enabled=False)
        for i in range(n):
            manager.registrar_operacion("desde_bulk", "sqlite", "INSERT", i, 0.001)

    def via_audit() -> None:
        repo = legacy_csv.AuditCsvRepository(
            audit_csv_path=path,
            columnas_auditoria=list(legacy_csv.AUDIT_COLUMNS),
            logger=AuditManager(None).logger,
            cache_enabled=False,
        )
        for i in range(n):
            repo.registrar_operacion(tabla="desde_audit", motor="sqlite", operacion="DELETE", rowcount=i, elapsed=0.001)

    threads = [threading.Thread(target=fn) for fn in (via_bulk, via_audit, via_bulk, via_audit)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    frame = pd.read_csv(path, delimiter="\t")
    assert list(frame.columns) == list(legacy_csv.AUDIT_COLUMNS)  # una sola cabecera
    assert len(frame) == 4 * n
    assert frame["tabla"].value_counts().to_dict() == {"desde_bulk": 2 * n, "desde_audit": 2 * n}


def test_read_since_lee_solo_lo_anadido(tmp_path: Path) -> None:
    path = tmp_path / "auditoria.csv"
    manager = AuditManager(path, cache_enabled=False)
    manager.registrar_operacion("antes", "sqlite", "INSERT", 1, 0.1)
    offset = path.stat().st_size
    manager.registrar_operacion("despues", "sqlite", "INSERT", 2, 0.25)

    frame = legacy_csv.AuditCsvRepository.read_since(path, offset)

    assert frame["tabla"].tolist() == ["despues"]
    assert frame["tiempo_seg"].tolist() == [0.25]
    assert legacy_csv.AuditCsvRepository.read_since(path, None)["tabla"].tolist() == ["antes", "despues"]
