"""Resumen del CSV de auditoría de ``bulk`` al terminar un volcado (hoja «Auditoría Bulk» y ``DumpResult``).

Separado de ``orchestrator`` (R10a del refactor de reutilización 2026-09-26) sin cambios de comportamiento;
``DumpOrchestrator`` conserva los métodos estáticos (``_build_audit_summary``…) como delegados.
"""

from __future__ import annotations

import logging

from datetime import datetime
from pathlib import Path

import pandas as pd

from util_bbdd.audit.files import AuditFiles
from util_bbdd.audit.legacy_csv import AuditCsvRepository

from ._models import DumpAuditSummary

# Mismo logger que antes de separar este código de ``orchestrator`` (R10a): los registros no cambian de nombre.
_log = logging.getLogger("util_bbdd.dump.orchestrator")

# Columnas del CSV que usa el resumen.
_AUDIT_COLUMNS = frozenset({"timestamp", "tabla", "total_filas", "tiempo_seg"})


# F3 (sesión 2026-10-02c): la lectura del CSV y las utilidades de fichero viven en ``util_bbdd.audit``; ``dump`` ya no
# importa partes privadas de ``bulk``. Estos nombres se conservan como delegados (los usa ``DumpOrchestrator``).


def file_size(path: Path | None) -> int | None:
    """Tamaño de ``path`` en bytes, o ``None`` si no hay ruta o el fichero no existe (:meth:`AuditFiles.file_size`)."""
    return AuditFiles.file_size(path)


def file_identity(path: Path | None) -> tuple[int, int] | None:
    """``(st_dev, st_ino)`` de ``path``, o ``None`` si no hay ruta o el fichero no existe.

    Distingue el CSV del inicio del volcado de uno nuevo con la misma ruta: ``AuditCsvRepository`` aparta el fichero si
    su cabecera no es válida, y el desplazamiento de inicio (``file_size``) ya no corresponde al fichero nuevo.
    """
    return AuditFiles.file_identity(path)


def read_audit_csv(audit_path: Path, start_offset: int | None) -> pd.DataFrame:
    """CSV de auditoría con los registros añadidos desde ``start_offset`` (:meth:`AuditCsvRepository.read_since`)."""
    return AuditCsvRepository.read_since(audit_path, start_offset)


def build_audit_summary(
    audit_path: Path | None,
    desde: datetime,
    audit_failures: int = 0,
    *,
    audited_rows: int | None = None,
    unaudited_committed_rows: int = 0,
    audit_uncommitted_records: int = 0,
    start_offset: int | None = None,
) -> DumpAuditSummary | None:
    """Lee el CSV de auditoría y extrae métricas del volcado actual.

    Filtra por ``timestamp >= desde`` para aislar las entradas de este volcado
    frente a operaciones previas que pudieran existir en el mismo CSV.
    Devuelve ``None`` si la ruta no está configurada, o si el fichero no existe o no
    hay entradas en el rango temporal y no hubo incidencias. Si ``audit_failures``,
    ``unaudited_committed_rows`` o ``audit_uncommitted_records`` es mayor que 0 devuelve
    siempre un resumen (con métricas del CSV a 0 si no hay entradas), para que el
    problema no quede oculto.

    ``audited_rows`` son las filas que el volcado escribió según sus contadores; ``None`` si
    no se conocen (entonces vale 0 en el resumen y no se compara con el CSV). Si difiere de
    ``total_filas`` se registra un WARNING.
    """
    if audit_path is None:
        return None

    counters: dict[str, int] = {
        "audit_failures": audit_failures,
        "audited_rows": audited_rows or 0,
        "unaudited_committed_rows": unaudited_committed_rows,
        "audit_uncommitted_records": audit_uncommitted_records,
    }
    incidencias = audit_failures > 0 or unaudited_committed_rows > 0 or audit_uncommitted_records > 0

    def _sin_entradas() -> DumpAuditSummary | None:
        if not incidencias:
            return None
        return DumpAuditSummary(
            total_operaciones=0,
            total_filas=0,
            tiempo_total_seg=0.0,
            tiempo_promedio_seg=0.0,
            tablas_auditadas=0,
            tabla_mas_activa=None,
            audit_path=audit_path,
            **counters,
        )

    if not audit_path.is_file():
        return _sin_entradas()
    try:
        df = read_audit_csv(audit_path, start_offset)
    except Exception as exc:
        _log.warning("No se pudo leer el CSV de auditoría '%s': %s", audit_path, exc)
        return _sin_entradas()
    # Una cabecera mal formada (p.ej. la línea entera entrecomillada al re-guardar el CSV) deja una sola columna: el
    # KeyError al usarlas abortaba run() antes de generar el informe Excel.
    faltan = _AUDIT_COLUMNS.difference(df.columns)
    if faltan:
        _log.warning(
            "El CSV de auditoría '%s' no tiene las columnas %s (¿cabecera mal formada?); se omite su resumen.",
            audit_path,
            sorted(faltan),
        )
        return _sin_entradas()
    if df.empty:
        return _sin_entradas()
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    # H3 (audit-code 2026-09-25): el CSV guarda el timestamp truncado al segundo; comparar con ``desde`` y sus
    # microsegundos descartaba las operaciones terminadas en el mismo segundo en que empezó el volcado.
    df = df[df["timestamp"] >= pd.Timestamp(desde.replace(microsecond=0))]
    if df.empty:
        return _sin_entradas()
    tabla_mas_activa: str | None = str(df["tabla"].value_counts().index[0]) if len(df) > 0 else None
    total_filas = int(df["total_filas"].sum())
    if audited_rows is not None and audited_rows != total_filas:
        _log.warning(
            "Auditoría del volcado: el CSV suma %d filas desde el inicio y el volcado escribió %d. Causas "
            "probables: otros procesos escriben en el mismo CSV, o registros escritos antes de un commit que "
            "falló (audit_uncommitted_records=%d).",
            total_filas,
            audited_rows,
            audit_uncommitted_records,
        )
    return DumpAuditSummary(
        total_operaciones=int(len(df)),
        total_filas=total_filas,
        tiempo_total_seg=round(float(df["tiempo_seg"].sum()), 3),
        tiempo_promedio_seg=round(float(df["tiempo_seg"].mean()), 3),
        tablas_auditadas=int(df["tabla"].nunique()),
        tabla_mas_activa=tabla_mas_activa,
        audit_path=audit_path,
        **counters,
    )
