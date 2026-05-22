"""Reporter de plan de migración en formato Markdown."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ir.models import CanonicalColumn, CanonicalRoutine, CanonicalTable, MigrationPlan, MigrationWarning


def format_plan_markdown(plan: MigrationPlan) -> str:
    """Genera un reporte Markdown del plan de migración.

    Args:
        plan: Plan de migración con tablas, rutinas y warnings.

    Returns:
        Documento Markdown con resumen, tabla de avisos, listado de tablas
        y sección de rutinas (PROCEDURE/FUNCTION) con su código fuente.
    """
    lines: list[str] = [
        f"# Plan de migración: {plan.source_engine.upper()} → {plan.target_engine.upper()}",
        "",
        f"**Schema origen**: `{plan.source_schema}`  ",
        f"**Tablas**: {len(plan.tables)}  ",
        f"**Rutinas**: {len(plan.routines)}  ",
        f"**Avisos**: {plan.error_count} error / {plan.warning_count} warning / {plan.info_count} info",
        "",
    ]

    if plan.warnings:
        lines.extend(_warnings_section(plan.warnings))
    if plan.tables:
        lines.extend(_tables_section(plan.tables, plan.target_engine.upper()))
    if plan.routines:
        lines.extend(_routines_section(plan.routines, plan.source_engine))

    return "\n".join(lines)


def _warnings_section(warnings: list[MigrationWarning]) -> list[str]:
    lines: list[str] = [
        "## Avisos de migración",
        "",
        "| Severidad | Tabla | Columna | Mensaje |",
        "|---|---|---|---|",
    ]
    for w in warnings:
        col = w.column or "—"
        msg = w.message.replace("|", "\\|")
        lines.append(f"| **{w.severity}** | `{w.table}` | `{col}` | {msg} |")
    lines.append("")
    return lines


def _tables_section(tables: list[CanonicalTable], target_engine: str) -> list[str]:
    lines: list[str] = ["## Tablas migradas", ""]
    for table in tables:
        lines.extend(_table_block(table, target_engine))
    return lines


def _table_block(table: CanonicalTable, target_engine: str) -> list[str]:
    lines: list[str] = [f"### `{table.name}`"]
    if table.original_name != table.name:
        lines.append(f"> Nombre original: `{table.original_name}`")
    lines += [
        "",
        f"| Columna | Tipo Oracle | Tipo {target_engine} | Nullable | AI |",
        "|---|---|---|---|---|",
        *(_column_row(col) for col in table.columns),
        "",
    ]
    return lines


def _column_row(column: CanonicalColumn) -> str:
    if column.omit:
        return f"| ~~`{column.name}`~~ | `{column.oracle_type}` | *(omitida)* | — | — |"
    ai = "✓" if column.auto_increment else ""
    null = "YES" if column.nullable else "NO"
    return f"| `{column.name}` | `{column.oracle_type}` | `{column.target_type}` | {null} | {ai} |"


def _routines_section(routines: list[CanonicalRoutine], source_engine: str) -> list[str]:
    lines: list[str] = [
        "## Rutinas (PROCEDURE/FUNCTION)",
        "",
        "> ⚠️ Las rutinas requieren revisión manual. El código se muestra tal como existe "
        "en el motor origen; adaptar la sintaxis al motor destino antes de ejecutar.",
        "",
    ]
    for routine in routines:
        lines.extend(_routine_block(routine, source_engine))
    return lines


def _routine_block(routine: CanonicalRoutine, source_engine: str) -> list[str]:
    lines: list[str] = [f"### `{routine.name}` ({routine.routine_type})"]
    if routine.original_name != routine.name:
        lines.append(f"> Nombre original: `{routine.original_name}`")
    if routine.comment:
        lines.append(f"> {routine.comment}")
    lines.append("")

    src_type = ("PACKAGE BODY" if routine.body else "PACKAGE") if routine.is_package_member else routine.routine_type
    lines.append(f"> **Fuente**: `{source_engine.upper()}` · schema `{routine.schema}` · tipo `{src_type}`")
    lines.append("")

    if routine.is_package_member:
        pkg = routine.package_name or routine.name
        lines += [
            f"> **Miembro de PACKAGE**: `{pkg}` — requiere descomposición manual en rutinas individuales.",
            "",
        ]
    elif routine.warnings:
        lines.append("> **⚠️ Requiere revisión manual** (ver avisos de migración).")
        lines.append("")

    if not routine.body:
        lines += [
            "> **Código no disponible** — implementación manual requerida.",
            "",
        ]
        return lines

    lines += [
        "```sql",
        routine.body,
        "```",
        "",
    ]
    return lines


__all__: list[str] = ["format_plan_markdown"]
