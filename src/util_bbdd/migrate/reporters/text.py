"""Reporter de plan de migración en formato texto plano."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ir.models import MigrationPlan, MigrationWarning

_SEP = "=" * 70
_SEP_THIN = "-" * 70


def format_plan_text(plan: MigrationPlan) -> str:
    """Genera un reporte texto plano del plan de migración.

    Args:
        plan: Plan de migración con tablas y warnings.

    Returns:
        Reporte legible con resumen y warnings por severidad.
    """
    lines: list[str] = [
        _SEP,
        f"PLAN DE MIGRACIÓN: {plan.source_engine.upper()} → {plan.target_engine.upper()}",
        f"Schema origen: {plan.source_schema}",
        f"Tablas: {len(plan.tables)}",
        f"Avisos: {plan.error_count} ERROR / {plan.warning_count} WARNING / {plan.info_count} INFO",
        _SEP,
    ]

    if plan.warnings:
        lines.extend(_warnings_section(plan.warnings))

    lines.append("")
    return "\n".join(lines)


def _warnings_section(warnings: list[MigrationWarning]) -> list[str]:
    lines: list[str] = ["", "AVISOS:", _SEP_THIN]
    for sev in ("ERROR", "WARNING", "INFO"):
        ws = [w for w in warnings if w.severity == sev]
        if ws:
            lines.extend(_severity_block(sev, ws))
    return lines


def _severity_block(severity: str, warnings: list[MigrationWarning]) -> list[str]:
    lines: list[str] = [f"\n[{severity}]"]
    for w in warnings:
        lines.extend(_warning_lines(w))
    return lines


def _warning_lines(w: MigrationWarning) -> list[str]:
    loc = f"{w.table}.{w.column}" if w.column else w.table
    lines = [f"  {loc}: {w.message}"]
    lines.extend(f"    → {p}" for p in w.proposals)
    return lines


__all__: list[str] = ["format_plan_text"]
