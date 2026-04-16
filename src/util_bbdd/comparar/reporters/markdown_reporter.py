"""Reporter de SchemaDiff en formato Markdown con diagramas Mermaid."""

from __future__ import annotations

import logging

from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from ..models import (
    RoutineDiff,
    SchemaDiff,
    TableDiff,
    ViewDiff,
)
from ._base import STATUS_EMOJI, STATUS_ES, DdlNormalizer, DiffSummary, build_diff_summary, escape_mermaid_label

logger: logging.Logger = logging.getLogger(__name__)


class MarkdownDiffReporter:
    """Genera un reporte Markdown con diagrama Mermaid del SchemaDiff.

    Implementa ``DiffReporterProtocol``.

    El diagrama Mermaid usa ``graph LR`` con subgrafos por estado
    (añadido / eliminado / modificado). Los bloques ``mermaid`` son
    renderizados nativamente por GitHub, GitLab y la mayoría de
    editores Markdown modernos.
    """

    _MERMAID_SUBGRAPH_END: ClassVar[str] = "    end"
    _TABLE_SEPARATOR_4COL: ClassVar[str] = "|---|---|---|---|"
    _TABLE_SEPARATOR_6COL: ClassVar[str] = "|---|---|---|---|---|---|"

    def render(self, diff: SchemaDiff, output: Path) -> Path:
        """Genera el fichero Markdown en la ruta indicada.

        Args:
            diff: Resultado de la comparación de esquemas.
            output: Ruta completa del fichero ``.md`` a generar.

        Returns:
            La ruta del fichero generado.
        """
        output.parent.mkdir(parents=True, exist_ok=True)
        summary: DiffSummary = build_diff_summary(diff)
        lines: list[str] = []
        lines += self._render_header(diff, summary)
        lines += self._render_mermaid(diff)
        lines += self._render_tables_section(diff.table_diffs)
        lines += self._render_views_section(diff.view_diffs)
        lines += self._render_routines_section(diff.routine_diffs)
        content: str = "\n".join(lines) + "\n"
        output.write_text(content, encoding="utf-8")
        logger.info("Markdown diff report generado: %s", output)
        return output

    # ------------------------------------------------------------------
    # Secciones del documento
    # ------------------------------------------------------------------

    @staticmethod
    def _render_header(diff: SchemaDiff, summary: DiffSummary) -> list[str]:
        lines: list[str] = [
            "# Reporte de diferencias de esquema",
            "",
            "| | |",
            "|---|---|",
            f"| **Origen** | `{diff.source_label}` |",
            f"| **Destino** | `{diff.target_label}` |",
            f"| **Tablas con diferencias** | {summary.total_tables} "
            f"({summary.tables_added} añadidas, "
            f"{summary.tables_removed} eliminadas, "
            f"{summary.tables_modified} modificadas) |",
            f"| **Vistas con diferencias** | {summary.total_views} "
            f"({summary.views_added} añadidas, "
            f"{summary.views_removed} eliminadas, "
            f"{summary.views_modified} modificadas) |",
            f"| **Rutinas con diferencias** | {summary.total_routines} "
            f"({summary.routines_added} añadidas, "
            f"{summary.routines_removed} eliminadas, "
            f"{summary.routines_modified} modificadas) |",
            "",
        ]
        if diff.summary:
            lines += [f"> {diff.summary}", ""]
        if not summary.has_differences:
            lines += ["> ✅ **Sin diferencias detectadas entre los esquemas.**", ""]
        return lines

    def _render_mermaid(self, diff: SchemaDiff) -> list[str]:
        """Genera el bloque Mermaid con las tablas agrupadas por estado."""
        added_tables: list[str] = [t.table_name for t in diff.table_diffs if t.status == "added"]
        removed_tables: list[str] = [t.table_name for t in diff.table_diffs if t.status == "removed"]
        modified_tables: list[str] = [t.table_name for t in diff.table_diffs if t.status == "modified"]

        if not diff.table_diffs:
            return []

        lines: list[str] = ["## Diagrama de diferencias", "", "```mermaid", "graph LR"]

        if added_tables:
            lines.append('    subgraph added["✅ Añadidas"]')
            for name in added_tables:
                safe_id: str = f"A_{escape_mermaid_label(name).replace(' ', '_')}"
                lines.append(f'        {safe_id}["{escape_mermaid_label(name)}"]')
            lines.append(self._MERMAID_SUBGRAPH_END)

        if removed_tables:
            lines.append('    subgraph removed["❌ Eliminadas"]')
            for name in removed_tables:
                safe_id = f"R_{escape_mermaid_label(name).replace(' ', '_')}"
                lines.append(f'        {safe_id}["{escape_mermaid_label(name)}"]')
            lines.append(self._MERMAID_SUBGRAPH_END)

        if modified_tables:
            lines.append('    subgraph modified["⚠️ Modificadas"]')
            for name in modified_tables:
                safe_id = f"M_{escape_mermaid_label(name).replace(' ', '_')}"
                col_count: int = len([t for t in diff.table_diffs if t.table_name == name and t.column_diffs])
                label: str = escape_mermaid_label(name)
                if col_count:
                    label = f"{label}\\n({col_count} cols)"
                lines.append(f'        {safe_id}["{label}"]')
            lines.append(self._MERMAID_SUBGRAPH_END)

        lines += ["```", ""]
        return lines

    def _render_columns_table(self, column_diffs: Sequence) -> list[str]:
        """Renderiza tabla de diferencias de columnas."""
        lines: list[str] = [
            "**Columnas:**",
            "",
            "| Columna | Atributo | Origen | Destino |",
            self._TABLE_SEPARATOR_4COL,
        ]
        for cd in column_diffs:
            lines.append(f"| `{cd.column_name}` | {cd.attribute} | `{cd.source_value}` | `{cd.target_value}` |")
        lines.append("")
        return lines

    def _render_indexes_table(self, index_diffs: Sequence) -> list[str]:
        """Renderiza tabla de diferencias de índices."""
        lines: list[str] = [
            "**Índices:**",
            "",
            "| Índice | Estado | Cols origen | Cols destino |",
            self._TABLE_SEPARATOR_4COL,
        ]
        for idx in index_diffs:
            estado_idx: str | None = STATUS_ES.get(idx.status, idx.status)
            lines.append(f"| `{idx.index_name}` | {estado_idx} | `{idx.source_columns}` | `{idx.target_columns}` |")
        lines.append("")
        return lines

    def _render_fks_table(self, fk_diffs: Sequence) -> list[str]:
        """Renderiza tabla de diferencias de Foreign Keys."""
        lines: list[str] = [
            "**Foreign Keys:**",
            "",
            "| FK | Estado | Cols origen | Tabla referenciada origen | Cols destino | Tabla referenciada destino |",
            self._TABLE_SEPARATOR_6COL,
        ]
        for fk in fk_diffs:
            estado_fk: str | None = STATUS_ES.get(fk.status, fk.status)
            lines.append(
                f"| `{fk.fk_name}` | {estado_fk} "
                f"| `{fk.source_columns}` | `{fk.source_referred_table}` "
                f"| `{fk.target_columns}` | `{fk.target_referred_table}` |"
            )
        lines.append("")
        return lines

    @staticmethod
    def _render_comments_table(comment_diffs: Sequence) -> list[str]:
        """Renderiza tabla de diferencias de comentarios."""
        lines: list[str] = [
            "**Comentarios:**",
            "",
            "| Objeto | Columna | Comentario origen | Comentario destino |",
            "|---|---|---|---|",
        ]
        for cm in comment_diffs:
            col_label: str = f"`{cm.column_name}`" if cm.column_name else "*(tabla)*"
            lines.append(f"| `{cm.object_name}` | {col_label} | {cm.source_comment} | {cm.target_comment} |")
        lines.append("")
        return lines

    def _render_table_details(self, table_diff: TableDiff) -> list[str]:
        """Renderiza los detalles de una tabla (columnas, índices, FKs, comentarios)."""
        lines: list[str] = []
        if table_diff.column_diffs:
            lines += self._render_columns_table(table_diff.column_diffs)
        if table_diff.index_diffs:
            lines += self._render_indexes_table(table_diff.index_diffs)
        if table_diff.fk_diffs:
            lines += self._render_fks_table(table_diff.fk_diffs)
        if table_diff.comment_diffs:
            lines += self._render_comments_table(table_diff.comment_diffs)
        return lines

    def _render_tables_section(self, table_diffs: Sequence[TableDiff]) -> list[str]:
        if not table_diffs:
            return []
        lines: list[str] = ["## Tablas", ""]
        for td in table_diffs:
            emoji: str = STATUS_EMOJI.get(td.status, "")
            estado: str = STATUS_ES.get(td.status, td.status)
            lines.append(f"### {emoji} `{td.table_name}` — {estado}")
            lines.append("")
            lines += self._render_table_details(td)
        return lines

    def _render_views_section(self, view_diffs: Sequence[ViewDiff]) -> list[str]:
        if not view_diffs:
            return []
        lines: list[str] = ["## Vistas", ""]
        for vd in view_diffs:
            emoji: str = STATUS_EMOJI.get(vd.status, "")
            estado: str = STATUS_ES.get(vd.status, vd.status)
            lines.append(f"### {emoji} `{vd.view_name}` — {estado}")
            lines.append("")
            if vd.status == "modified" and (vd.source_definition or vd.target_definition):
                lines.append("<details><summary>Ver definiciones</summary>")
                lines.append("")
                if vd.source_definition:
                    src_ddl = DdlNormalizer.normalize_view_ddl(vd.source_definition)
                    lines.append(f"**Origen:**\n```sql\n{src_ddl}\n```")
                if vd.target_definition:
                    tgt_ddl = DdlNormalizer.normalize_view_ddl(vd.target_definition)
                    lines.append(f"**Destino:**\n```sql\n{tgt_ddl}\n```")
                lines.append("</details>")
                lines.append("")
        return lines

    def _render_routines_section(self, routine_diffs: Sequence[RoutineDiff]) -> list[str]:
        if not routine_diffs:
            return []
        lines: list[str] = ["## Rutinas", ""]
        for rd in routine_diffs:
            emoji: str = STATUS_EMOJI.get(rd.status, "")
            estado: str = STATUS_ES.get(rd.status, rd.status)
            lines.append(f"### {emoji} `{rd.routine_name}` ({rd.routine_type}) — {estado}")
            lines.append("")
            if rd.status == "modified" and (rd.source_definition or rd.target_definition):
                lines.append("<details><summary>Ver definiciones</summary>")
                lines.append("")
                if rd.source_definition:
                    src_ddl = DdlNormalizer.normalize_routine_ddl(rd.source_definition)
                    lines.append(f"**Origen:**\n```sql\n{src_ddl}\n```")
                if rd.target_definition:
                    tgt_ddl = DdlNormalizer.normalize_routine_ddl(rd.target_definition)
                    lines.append(f"**Destino:**\n```sql\n{tgt_ddl}\n```")
                lines.append("</details>")
                lines.append("")
        return lines
