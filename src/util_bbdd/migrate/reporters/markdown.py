"""Reporter de plan de migración en formato Markdown."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ir.models import MigrationPlan


def format_plan_markdown(plan: MigrationPlan) -> str:
    """Genera un reporte Markdown del plan de migración.

    Args:
        plan: Plan de migración con tablas y warnings.

    Returns:
        Documento Markdown con resumen, tabla de avisos y listado de tablas.
    """
    lines: list[str] = []
    lines.append(f"# Plan de migración: {plan.source_engine.upper()} → {plan.target_engine.upper()}")
    lines.append("")
    lines.append(f"**Schema origen**: `{plan.source_schema}`  ")
    lines.append(f"**Tablas**: {len(plan.tables)}  ")
    lines.append(f"**Avisos**: {plan.error_count} error / {plan.warning_count} warning / {plan.info_count} info")
    lines.append("")

    if plan.warnings:
        lines.append("## Avisos de migración")
        lines.append("")
        lines.append("| Severidad | Tabla | Columna | Mensaje |")
        lines.append("|---|---|---|---|")
        for w in plan.warnings:
            col = w.column or "—"
            msg = w.message.replace("|", "\\|")
            lines.append(f"| **{w.severity}** | `{w.table}` | `{col}` | {msg} |")
        lines.append("")

    if plan.tables:
        lines.append("## Tablas migradas")
        lines.append("")
        for table in plan.tables:
            lines.append(f"### `{table.name}`")
            if table.original_name != table.name:
                lines.append(f"> Nombre original: `{table.original_name}`")
            lines.append("")
            lines.append("| Columna | Tipo Oracle | Tipo MariaDB | Nullable | AI |")
            lines.append("|---|---|---|---|---|")
            for column in table.columns:
                if column.omit:
                    lines.append(f"| ~~`{column.name}`~~ | `{column.oracle_type}` | *(omitida)* | — | — |")
                    continue
                ai = "✓" if column.auto_increment else ""
                null = "YES" if column.nullable else "NO"
                lines.append(f"| `{column.name}` | `{column.oracle_type}` | `{column.target_type}` | {null} | {ai} |")
            lines.append("")

    return "\n".join(lines)


__all__: list[str] = ["format_plan_markdown"]
