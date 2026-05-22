"""Reporter de plan de migración en formato texto plano."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ir.models import CanonicalRoutine, MigrationPlan, MigrationWarning

_SEP = "=" * 70
_SEP_THIN = "-" * 70


def format_plan_text(plan: MigrationPlan) -> str:
    """Genera un reporte texto plano del plan de migración.

    Args:
        plan: Plan de migración con tablas, rutinas y warnings.

    Returns:
        Reporte legible con resumen, warnings por severidad y listado de
        rutinas (PROCEDURE/FUNCTION) con su código fuente para revisión manual.
    """
    lines: list[str] = [
        _SEP,
        f"PLAN DE MIGRACIÓN: {plan.source_engine.upper()} → {plan.target_engine.upper()}",
        f"Schema origen: {plan.source_schema}",
        f"Tablas: {len(plan.tables)}",
        f"Rutinas: {len(plan.routines)}",
        f"Avisos: {plan.error_count} ERROR / {plan.warning_count} WARNING / {plan.info_count} INFO",
        _SEP,
    ]

    if plan.warnings:
        lines.extend(_warnings_section(plan.warnings))
    if plan.routines:
        lines.extend(_routines_section(plan.routines, plan.source_engine))

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


def _routines_section(routines: list[CanonicalRoutine], source_engine: str) -> list[str]:
    lines: list[str] = [
        "",
        "RUTINAS (PROCEDURE/FUNCTION):",
        _SEP_THIN,
        "AVISO: requieren revisión manual — adaptar sintaxis al motor destino.",
        _SEP_THIN,
    ]
    for routine in routines:
        lines.extend(_routine_block(routine, source_engine))
    return lines


def _routine_block(routine: CanonicalRoutine, source_engine: str) -> list[str]:
    header = f"{routine.routine_type}: {routine.name}"
    if routine.original_name != routine.name:
        header += f" (original: {routine.original_name})"
    lines: list[str] = ["", header, "-" * len(header)]

    src_type = ("PACKAGE BODY" if routine.body else "PACKAGE") if routine.is_package_member else routine.routine_type
    lines.append(f"  Fuente: {source_engine.upper()} · schema {routine.schema} · tipo {src_type}")

    if routine.is_package_member:
        pkg = routine.package_name or routine.name
        lines.append(f"  [PACKAGE MEMBER] {pkg} — requiere descomposición manual en rutinas individuales.")
    elif routine.warnings:
        lines.append("  [REQUIERE REVISIÓN MANUAL] (ver avisos de migración)")

    if routine.comment:
        lines.append(f"  Comentario: {routine.comment}")

    if not routine.body:
        lines.append("  [CÓDIGO NO DISPONIBLE] — implementación manual requerida.")
        return lines

    lines.append("")
    lines.extend(f"  {ln}" for ln in routine.body.splitlines())
    return lines


__all__: list[str] = ["format_plan_text"]
