"""Adaptador de ``migrate`` al módulo de auditoría: avisos del plan, sentencias ejecutadas y validación de vistas.

F4 de la sesión 2026-10-02c (resuelve H-03: ``MigrationPlan.execute`` no dejaba rastro de qué sentencias aplicó).
``util_bbdd.audit`` no conoce los tipos de ``migrate`` (Regla #6): la conversión a :class:`AuditEvent` vive aquí.

Qué se registra y qué no:

- Avisos del plan: categoría, código, severidad, tabla/columna y mensaje.
- Sentencias: posición, primera palabra (``CREATE``, ``ALTER``…), primera línea útil truncada a 120 caracteres (como
  el mensaje de error de ``execute``), duración y, si falla, la clase del error. **No** se guarda el DDL completo.
- Un fallo del destino de auditoría no interrumpe la migración: se registra como ERROR (el DDL ya aplicado no se puede
  deshacer y relanzar invitaría a repetirlo).
"""

from __future__ import annotations

import logging
import time
import uuid

from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING, ClassVar

from ..audit.events import AuditEvent, AuditStatus

if TYPE_CHECKING:
    from ..audit.contracts import AuditSink
    from .ir.models import MigrationPlan, MigrationWarning
    from .views.validation import ViewValidationResult


class MigrationAuditEvents:
    """Conversión de los tipos de ``migrate`` a :class:`AuditEvent` (sin estado)."""

    #: Severidad de :class:`MigrationWarning` → :data:`AuditStatus`.
    SEVERITY_STATUS: ClassVar[dict[str, AuditStatus]] = {"INFO": "info", "WARNING": "warning", "ERROR": "error"}
    #: Longitud de la primera línea de una sentencia que se registra.
    STATEMENT_PREVIEW: ClassVar[int] = 120

    @staticmethod
    def plan_warnings(
        plan: MigrationPlan, warnings: Iterable[MigrationWarning] | None = None, *, run_id: str | None = None
    ) -> list[AuditEvent]:
        """Un evento ``plan_warning`` por aviso de ``plan`` (o de ``warnings``)."""
        return [
            AuditEvent.now(
                source="migrate",
                kind="plan_warning",
                status=MigrationAuditEvents.SEVERITY_STATUS.get(warning.severity, "warning"),
                engine=plan.target_engine,
                target=warning.table if warning.column is None else f"{warning.table}.{warning.column}",
                operation=warning.category,
                message=warning.message,
                run_id=run_id,
                attributes={
                    "code": warning.code,
                    "severity": warning.severity,
                    "source_type": warning.source_type,
                    "target_type": warning.target_type,
                    "source_engine": plan.source_engine,
                    "source_schema": plan.source_schema,
                },
            )
            for warning in (plan.warnings if warnings is None else warnings)
        ]

    @staticmethod
    def first_sql_line(statement: str) -> str:
        """Primera línea que no es comentario ni está vacía, truncada a :attr:`STATEMENT_PREVIEW`."""
        line = next((ln.strip() for ln in statement.splitlines() if ln.strip() and not ln.strip().startswith("--")), "")
        return line[: MigrationAuditEvents.STATEMENT_PREVIEW]

    @staticmethod
    def statement(
        *,
        engine: str,
        position: int,
        total: int,
        statement: str,
        elapsed_s: float,
        error: BaseException | None,
        run_id: str | None,
    ) -> AuditEvent:
        """Evento ``statement`` de una sentencia ejecutada por ``MigrationPlan.execute``."""
        preview = MigrationAuditEvents.first_sql_line(statement)
        return AuditEvent.now(
            source="migrate",
            kind="statement",
            status="ok" if error is None else "failed",
            engine=engine,
            operation=preview.split(maxsplit=1)[0].upper() if preview else None,
            elapsed_s=elapsed_s,
            error_type=None if error is None else type(error).__name__,
            message=preview,
            run_id=run_id,
            attributes={"position": position, "total": total},
        )

    @staticmethod
    def view_validation(
        results: Sequence[ViewValidationResult], *, engine: str, run_id: str | None = None
    ) -> list[AuditEvent]:
        """Un evento ``view_validation`` por vista: ``ok``, ``failed`` o ``skipped`` (no se pudo validar)."""
        events: list[AuditEvent] = []
        for result in results:
            status: AuditStatus = "skipped" if result.valid is None else ("ok" if result.valid else "failed")
            events.append(
                AuditEvent.now(
                    source="migrate",
                    kind="view_validation",
                    status=status,
                    engine=engine,
                    target=result.view,
                    operation="VALIDATE",
                    message=result.error,
                    run_id=run_id,
                    attributes={"method": result.method},
                )
            )
        return events


class MigrationAuditRecorder:
    """Escribe en un :class:`AuditSink` el rastro de una ejecución de ``MigrationPlan`` (un ``run_id`` por ejecución).

    Args:
        sink: Destino de los eventos.
        plan: Plan que se ejecuta.
    """

    def __init__(self, sink: AuditSink, plan: MigrationPlan) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.sink: AuditSink = sink
        self.plan: MigrationPlan = plan
        self.run_id: str = uuid.uuid4().hex
        #: Escrituras en el destino (llamadas a :meth:`write`) que fallaron; cada una se registró como ERROR.
        self.failures: int = 0
        self._ok: int = 0
        self._started: float = time.perf_counter()

    def warnings(self) -> None:
        """Avisos del plan en el momento de ejecutar."""
        self.write(lambda: MigrationAuditEvents.plan_warnings(self.plan, run_id=self.run_id))

    def statement(
        self, position: int, total: int, statement: str, elapsed_s: float, error: BaseException | None
    ) -> None:
        """Una sentencia aplicada (``error=None``) o fallida."""
        if error is None:
            self._ok += 1
        self.write(
            lambda: [
                MigrationAuditEvents.statement(
                    engine=self.plan.target_engine,
                    position=position,
                    total=total,
                    statement=statement,
                    elapsed_s=elapsed_s,
                    error=error,
                    run_id=self.run_id,
                )
            ]
        )

    def finish(self, *, total: int, error: BaseException | None) -> None:
        """Evento ``run`` de cierre: ``ok`` si se aplicaron todas las sentencias, ``failed`` si no."""
        elapsed_s = time.perf_counter() - self._started
        self.write(
            lambda: [
                AuditEvent.now(
                    source="migrate",
                    kind="run",
                    status="ok" if error is None else "failed",
                    engine=self.plan.target_engine,
                    operation="EXECUTE",
                    elapsed_s=elapsed_s,
                    error_type=None if error is None else type(error).__name__,
                    message=None if error is None else str(error),
                    run_id=self.run_id,
                    attributes={
                        "source_engine": self.plan.source_engine,
                        "source_schema": self.plan.source_schema,
                        "statements_total": total,
                        "statements_ok": self._ok,
                        "errors": self.plan.error_count,
                        "warnings": self.plan.warning_count,
                    },
                )
            ]
        )

    def write(self, build: Callable[[], Sequence[AuditEvent]]) -> None:
        """Construye los eventos con ``build`` y los escribe; si algo falla, ERROR y +1 en :attr:`failures`.

        No relanza nunca. La construcción va dentro del ``try`` (hipótesis 5 del audit-code 2026-10-02c): un fallo al
        construir un evento no debe hacer fallar ``execute`` tras aplicar el DDL ni tapar su ``DatabaseOperationError``.
        """
        try:
            self.sink.write(build())
        except Exception as exc:
            self.failures += 1
            self.logger.error(
                f"❌ No se pudo escribir la auditoría de la migración (run_id={self.run_id}): {exc}", exc_info=True
            )


__all__: list[str] = ["MigrationAuditEvents", "MigrationAuditRecorder"]
