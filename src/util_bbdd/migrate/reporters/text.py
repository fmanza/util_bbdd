"""Reporter de plan de migración en formato texto plano."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ir.models import MigrationPlan


def format_plan_text(plan: MigrationPlan) -> str:
    """Genera un reporte texto plano del plan de migración.

    Args:
        plan: Plan de migración con tablas y warnings.

    Returns:
        Reporte legible con resumen y warnings por severidad.
    """
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"PLAN DE MIGRACIÓN: {plan.source_engine.upper()} → {plan.target_engine.upper()}")
    lines.append(f"Schema origen: {plan.source_schema}")
    lines.append(f"Tablas: {len(plan.tables)}")
    lines.append(f"Avisos: {plan.error_count} ERROR / {plan.warning_count} WARNING / {plan.info_count} INFO")
    lines.append("=" * 70)

    if plan.warnings:
        lines.append("")
        lines.append("AVISOS:")
        lines.append("-" * 70)

        for sev in ("ERROR", "WARNING", "INFO"):
            ws = [w for w in plan.warnings if w.severity == sev]
            if not ws:
                continue
            lines.append(f"\n[{sev}]")
            for w in ws:
                loc = f"{w.table}.{w.column}" if w.column else w.table
                lines.append(f"  {loc}: {w.message}")
                if w.proposals:
                    for p in w.proposals:
                        lines.append(f"    → {p}")

    lines.append("")
    return "\n".join(lines)


__all__: list[str] = ["format_plan_text"]
