"""Adaptador de ``dump`` al módulo de auditoría: resultados por tabla, constraint, índice y contador PK.

F5 de la sesión 2026-10-02c. ``util_bbdd.audit`` no conoce los tipos de ``dump`` (Regla #6): la conversión vive aquí.
Los eventos de las operaciones de carga los escriben las ``BulkCrud`` y los ``ParallelBulkLoader`` del volcado; aquí
solo los del final, con el mismo ``run_id``.
"""

from __future__ import annotations

import logging

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, ClassVar

from util_bbdd.audit.events import AuditEvent, AuditStatus

if TYPE_CHECKING:
    from util_bbdd.audit.contracts import AuditSink

    from ._models import ConstraintResult, DumpResult, IndexActionResult, PKSyncResult, TableDumpResult


class DumpAuditEvents:
    """Conversión de los resultados de ``dump`` a :class:`AuditEvent` (sin estado)."""

    TABLE_STATUS: ClassVar[dict[str, AuditStatus]] = {
        "success": "ok",
        "missing_target": "skipped",
        "skipped": "skipped",
        "error": "failed",
    }
    CONSTRAINT_STATUS: ClassVar[dict[str, AuditStatus]] = {"enabled": "ok", "failed": "failed", "unverified": "warning"}
    INDEX_STATUS: ClassVar[dict[str, AuditStatus]] = {
        "rebuilt": "ok",
        "recreated": "ok",
        "failed": "failed",
        "unsupported": "skipped",
        "skipped": "skipped",
    }
    PK_SYNC_STATUS: ClassVar[dict[str, AuditStatus]] = {
        "synced": "ok",
        "no_rows": "ok",
        "skipped": "skipped",
        "unsupported": "skipped",
        "error": "failed",
    }

    @staticmethod
    def table(result: TableDumpResult, *, engine: str, namespace: str | None, run_id: str | None) -> AuditEvent:
        """Evento ``table``: ``rows`` = filas en destino tras la carga (``-1`` sin conteo pasa a ``None``)."""
        return AuditEvent.now(
            source="dump",
            kind="table",
            status=DumpAuditEvents.TABLE_STATUS.get(result.status, "warning"),
            engine=engine,
            namespace=namespace,
            target=result.table_name,
            operation="LOAD",
            rows=result.target_rows_after if result.target_rows_after >= 0 else None,
            message=result.error_msg or None,
            run_id=run_id,
            attributes={
                "dump_status": result.status,
                "source_rows": result.source_rows,
                "target_rows_before": result.target_rows_before,
                "rows_rejected": result.rows_rejected,
                "skipped_columns": len(result.skipped_columns),
                "load_order_position": result.load_order_position,
                "in_cycle": result.in_cycle,
            },
        )

    @staticmethod
    def constraint(result: ConstraintResult, *, namespace: str | None, run_id: str | None) -> AuditEvent:
        """Evento ``constraint`` al rehabilitar una constraint en el destino."""
        return AuditEvent.now(
            source="dump",
            kind="constraint",
            status=DumpAuditEvents.CONSTRAINT_STATUS.get(result.status, "warning"),
            engine=result.dialect,
            namespace=namespace,
            target=f"{result.table_name}.{result.constraint_name}",
            operation="ENABLE",
            message=result.error_msg or None,
            run_id=run_id,
        )

    @staticmethod
    def index(result: IndexActionResult, *, namespace: str | None, run_id: str | None) -> AuditEvent:
        """Evento ``index`` al reconstruir un índice secundario."""
        return AuditEvent.now(
            source="dump",
            kind="index",
            status=DumpAuditEvents.INDEX_STATUS.get(result.action, "warning"),
            engine=result.dialect,
            namespace=namespace,
            target=f"{result.table_name}.{result.index_name}",
            operation=result.action.upper(),
            message=result.error_msg or None,
            run_id=run_id,
        )

    @staticmethod
    def pk_sync(result: PKSyncResult, *, namespace: str | None, run_id: str | None) -> AuditEvent:
        """Evento ``pk_sync`` al resincronizar el contador de una PK."""
        return AuditEvent.now(
            source="dump",
            kind="pk_sync",
            status=DumpAuditEvents.PK_SYNC_STATUS.get(result.status, "warning"),
            engine=result.engine_dialect,
            namespace=namespace,
            target=f"{result.table_name}.{result.column_name}",
            operation="SYNC",
            message=result.error_msg or None,
            run_id=run_id,
            attributes={"pk_status": result.status, "max_value": result.max_value},
        )

    @staticmethod
    def result_events(
        result: DumpResult, *, engine: str, namespace: str | None, run_id: str | None
    ) -> list[AuditEvent]:
        """Eventos de todos los elementos de ``result`` (tablas, constraints, índices, contadores PK)."""
        events = [
            DumpAuditEvents.table(r, engine=engine, namespace=namespace, run_id=run_id) for r in result.table_results
        ]
        events += [DumpAuditEvents.constraint(r, namespace=namespace, run_id=run_id) for r in result.constraint_results]
        events += [DumpAuditEvents.index(r, namespace=namespace, run_id=run_id) for r in result.index_results or []]
        events += [DumpAuditEvents.pk_sync(r, namespace=namespace, run_id=run_id) for r in result.pk_sync_results or []]
        return events

    @staticmethod
    def run(
        *,
        engine: str,
        namespace: str | None,
        run_id: str | None,
        elapsed_s: float,
        result: DumpResult | None,
        error: BaseException | None,
    ) -> AuditEvent:
        """Evento ``run`` de cierre del volcado: ``failed`` si lanzó una excepción, alguna tabla terminó en error o falló la
        reactivación general de constraints (``DumpResult.constraint_reactivation_error``)."""
        failed_tables = 0 if result is None else sum(1 for r in result.table_results if r.status == "error")
        # Hotfix A-01 (audit-code 2026-10-15b): sin esto, un destino con las constraints sin reactivar salía "ok".
        reactivation_failed = result is not None and result.constraint_reactivation_error is not None
        status: AuditStatus = "failed" if error is not None or failed_tables or reactivation_failed else "ok"
        attributes: dict[str, str | int | float | bool | None] = {"failed_tables": failed_tables}
        if result is not None:
            attributes |= {
                "tables": len(result.table_results),
                "rows_rejected": result.rows_rejected,
                "constraints_failed": sum(1 for r in result.constraint_results if r.status == "failed"),
                "constraint_reactivation_failed": reactivation_failed,
                "report": str(result.report),
            }
        return AuditEvent.now(
            source="dump",
            kind="run",
            status=status,
            engine=engine,
            namespace=namespace,
            operation="DUMP",
            rows=None if result is None else sum(max(r.target_rows_after, 0) for r in result.table_results),
            elapsed_s=elapsed_s,
            error_type=None if error is None else type(error).__name__,
            message=None if error is None else str(error),
            run_id=run_id,
            attributes=attributes,
        )


class DumpAuditWriter:
    """Escribe eventos del volcado en el destino sin interrumpirlo nunca (un fallo se registra como ERROR)."""

    def __init__(self, sink: AuditSink) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.sink: AuditSink = sink

    def write(self, build: Callable[[], Sequence[AuditEvent]]) -> None:
        """Construye los eventos con ``build`` y los escribe; si algo falla (construir o escribir), ERROR en el log.

        La construcción va dentro del ``try`` (hipótesis 5 del audit-code 2026-10-02c): un fallo al construir un evento
        no debe hacer que ``run()`` falle tras un volcado correcto ni tapar la excepción original del volcado.
        """
        try:
            events = build()
            self.sink.write(events)
        except Exception as exc:
            self.logger.error(f"❌ No se pudo escribir la auditoría del volcado en audit_sink: {exc}", exc_info=True)


__all__: list[str] = ["DumpAuditEvents", "DumpAuditWriter"]
