"""Adaptador de ``bulk`` al módulo de auditoría: operaciones, particiones y cargas paralelas como ``AuditEvent``.

F5 de la sesión 2026-10-02c. ``util_bbdd.audit`` no conoce los tipos de ``bulk`` (Regla #6): la conversión vive aquí.
Los eventos de operación salen de los mismos :class:`AuditRecord` que el CSV, en el mismo momento (al confirmarse la
transacción; con ``audit_strict``, antes del commit), así que siguen las mismas reglas que el CSV.
"""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING, ClassVar

from ...audit.events import AuditEvent, AuditStatus
from ...audit.legacy_csv import AuditRecord

if TYPE_CHECKING:
    from .._execution.parallel_loader import ParallelLoadResult, PartitionResult
    from .._models import IndexActionResult


class BulkAuditEvents:
    """Conversión de los tipos de ``bulk`` a :class:`AuditEvent` (sin estado)."""

    @staticmethod
    def operation(record: AuditRecord, *, engine: str, run_id: str | None) -> AuditEvent:
        """Evento ``operation`` de un registro de auditoría (``rows`` = filas enviadas, como en el CSV)."""
        return AuditEvent(
            source="bulk",
            kind="operation",
            status="ok",
            timestamp=record.timestamp.astimezone(UTC),  # el registro guarda la hora local sin zona
            engine=engine,
            target=record.tabla,
            operation=record.operacion,
            rows=record.rowcount,
            elapsed_s=record.elapsed,
            run_id=run_id,
            attributes=(("driver", record.motor), ("generated_sql", record.genero_sql)),
        )

    @staticmethod
    def partition(
        result: PartitionResult, *, table: str, operation: str, engine: str, run_id: str | None
    ) -> AuditEvent:
        """Evento ``partition`` de una partición de ``ParallelBulkLoader``."""
        status: AuditStatus = "ok" if result.error is None else "failed"
        return AuditEvent.now(
            source="bulk",
            kind="partition",
            status=status,
            engine=engine,
            target=table,
            operation=operation.upper(),
            rows=result.rows,
            elapsed_s=result.elapsed_seconds,
            message=result.error,
            run_id=run_id,
            attributes={
                "partition": result.index,
                "retries": result.retries,
                "rows_rejected": result.rows_rejected,
                "audit_failures": result.audit_failures,
                "unaudited_committed_rows": result.unaudited_committed_rows,
            },
        )

    @staticmethod
    def load(result: ParallelLoadResult, *, table: str, operation: str, engine: str, run_id: str | None) -> AuditEvent:
        """Evento ``run`` de cierre de una carga paralela: ``failed`` si alguna partición falló."""
        status: AuditStatus = "ok" if not result.partition_errors else "failed"
        return AuditEvent.now(
            source="bulk",
            kind="run",
            status=status,
            engine=engine,
            target=table,
            operation=operation.upper(),
            rows=result.total_rows,
            elapsed_s=result.elapsed_seconds,
            message=None if not result.partition_errors else f"{len(result.partition_errors)} particiones fallidas",
            run_id=run_id,
            attributes={
                "partitions": len(result.partition_results),
                "rows_rejected": result.rows_rejected,
                "audited_rows": result.audited_rows,
                "audit_failures": result.audit_failures,
            },
        )

    #: Estado del evento ``index`` según ``IndexActionResult.action`` (el mismo que en ``dump``).
    INDEX_STATUS: ClassVar[dict[str, AuditStatus]] = {
        "rebuilt": "ok",
        "recreated": "ok",
        "failed": "failed",
        "unsupported": "skipped",
        "skipped": "skipped",
    }

    @staticmethod
    def index(result: IndexActionResult, *, engine: str, run_id: str | None) -> AuditEvent:
        """Evento ``index`` al reconstruir un índice desactivado con ``ParallelOptions.disable_indexes`` (v3.3.0)."""
        return AuditEvent.now(
            source="bulk",
            kind="index",
            status=BulkAuditEvents.INDEX_STATUS.get(result.action, "warning"),
            engine=engine,
            target=f"{result.table_name}.{result.index_name}",
            operation=result.action.upper(),
            message=result.error_msg or None,
            run_id=run_id,
        )


__all__: list[str] = ["BulkAuditEvents"]
