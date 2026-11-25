"""Reporter de SchemaDiff en formato Markdown con diagramas Mermaid."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING, ClassVar

from util_bbdd._core.i18n import Translator
from util_bbdd._core.markdown import code_span
from util_bbdd._core.mermaid import mermaid_node_id as _mermaid_node_id  # movida a _core en 5.3.0

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from util_bbdd.comparar.models import RoutineDiff, SchemaDiff, TableDiff, ViewDiff

from ._base import (
    STATUS_EMOJI,
    DdlNormalizer,
    DiffSummary,
    build_diff_summary,
    escape_markdown_table_cell,
    escape_mermaid_label,
    localized_summary,
    status_labels,
)


def _cell(value: object) -> str:
    """Valor del catálogo como código en una celda de tabla: backticks y ``|`` seguros (5.3.0); vacío, celda vacía."""
    text = "" if value is None else str(value)
    return code_span(text, in_table=True) if text else ""


def _code(value: object) -> str:
    """Nombre del catálogo como código fuera de tablas (títulos), con backticks seguros (5.3.0)."""
    return code_span("" if value is None else str(value))


class MarkdownDiffReporter:
    """Genera un reporte Markdown con diagrama Mermaid del SchemaDiff.

    Implementa ``DiffReporterProtocol``.

    El diagrama Mermaid usa ``graph LR`` con subgrafos por estado
    (añadido / eliminado / modificado). Los bloques ``mermaid`` son
    renderizados nativamente por GitHub, GitLab y la mayoría de
    editores Markdown modernos.

    Args:
        translator: Idioma de los textos (títulos, cabeceras, estados); por defecto, español (5.10.0).
    """

    _MERMAID_SUBGRAPH_END: ClassVar[str] = "    end"
    _TABLE_SEPARATOR_4COL: ClassVar[str] = "|---|---|---|---|"
    _TABLE_SEPARATOR_6COL: ClassVar[str] = "|---|---|---|---|---|---|"

    def __init__(self, *, translator: Translator | None = None) -> None:
        """Inicializa MarkdownDiffReporter con logger e idioma de salida."""
        self.logger: logging.Logger = logging.getLogger(__name__)
        self._tr: Translator = translator or Translator()
        self._status: dict[str, str] = status_labels(self._tr)

    def _t(self, key: str, /, **params: object) -> str:
        """Texto ``comparar.<key>`` en el idioma de salida."""
        return self._tr.t(f"comparar.{key}", **params)

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
        lines_str: str = "\n".join(lines)
        content: str = f"{lines_str}\n"
        output.write_text(content, encoding="utf-8")
        self.logger.info("Markdown diff report generado: %s", output)
        return output

    # ------------------------------------------------------------------
    # Secciones del documento
    # ------------------------------------------------------------------

    def _render_header(self, diff: SchemaDiff, summary: DiffSummary) -> list[str]:
        tables_counts: str = self._t(
            "md.counts",
            total=summary.total_tables,
            added=summary.tables_added,
            removed=summary.tables_removed,
            modified=summary.tables_modified,
        )
        views_counts: str = self._t(
            "md.counts",
            total=summary.total_views,
            added=summary.views_added,
            removed=summary.views_removed,
            modified=summary.views_modified,
        )
        routines_counts: str = self._t(
            "md.counts",
            total=summary.total_routines,
            added=summary.routines_added,
            removed=summary.routines_removed,
            modified=summary.routines_modified,
        )
        lines: list[str] = [
            f"# {self._t('title.report')}",
            "",
            "| | |",
            "|---|---|",
            f"| **{self._t('label.source')}** | {_cell(diff.source_label)} |",
            f"| **{self._t('label.target')}** | {_cell(diff.target_label)} |",
            f"| **{self._t('md.tables_with_diffs')}** | {tables_counts} |",
            f"| **{self._t('md.views_with_diffs')}** | {views_counts} |",
            f"| **{self._t('md.routines_with_diffs')}** | {routines_counts} |",
            "",
        ]
        if diff.summary:
            lines += [f"> {localized_summary(diff, self._tr)}", ""]
        if not summary.has_differences:
            lines += [f"> ✅ **{self._t('meta.no_differences')}**", ""]
        return lines

    def _render_mermaid(self, diff: SchemaDiff) -> list[str]:
        """Genera el bloque Mermaid con las tablas agrupadas por estado."""
        added_tables: list[str] = [t.table_name for t in diff.table_diffs if t.status == "added"]
        removed_tables: list[str] = [t.table_name for t in diff.table_diffs if t.status == "removed"]
        modified_tables: list[TableDiff] = [t for t in diff.table_diffs if t.status == "modified"]

        if not diff.table_diffs:
            return []

        lines: list[str] = [f"## {self._t('diagram.title')}", "", "```mermaid", "graph LR"]
        used_ids: set[str] = set()

        if added_tables:
            lines.append(f'    subgraph added["✅ {escape_mermaid_label(self._t("diagram.added"))}"]')
            for name in added_tables:
                safe_id: str = _mermaid_node_id("A", name, used_ids)
                lines.append(f'        {safe_id}["{escape_mermaid_label(name)}"]')
            lines.append(self._MERMAID_SUBGRAPH_END)

        if removed_tables:
            lines.append(f'    subgraph removed["❌ {escape_mermaid_label(self._t("diagram.removed"))}"]')
            for name in removed_tables:
                safe_id = _mermaid_node_id("R", name, used_ids)
                lines.append(f'        {safe_id}["{escape_mermaid_label(name)}"]')
            lines.append(self._MERMAID_SUBGRAPH_END)

        if modified_tables:
            lines.append(f'    subgraph modified["⚠️ {escape_mermaid_label(self._t("diagram.modified"))}"]')
            for td in modified_tables:
                safe_id = _mermaid_node_id("M", td.table_name, used_ids)
                col_count: int = len(td.column_diffs)
                label: str = escape_mermaid_label(td.table_name)
                if col_count:
                    label = f"{label}\\n({col_count} cols)"
                lines.append(f'        {safe_id}["{label}"]')
            lines.append(self._MERMAID_SUBGRAPH_END)

        lines += ["```", ""]
        return lines

    def _render_columns_table(self, column_diffs: Sequence) -> list[str]:
        """Renderiza tabla de diferencias de columnas."""
        lines: list[str] = [
            f"**{self._t('section.columns')}:**",
            "",
            f"| {self._t('col.column')} | {self._t('col.attribute')} | {self._t('label.source')} "
            f"| {self._t('label.target')} |",
            self._TABLE_SEPARATOR_4COL,
        ]
        lines.extend(
            f"| {_cell(cd.column_name)} | {cd.attribute} | {_cell(cd.source_value)} | {_cell(cd.target_value)} |"
            for cd in column_diffs
        )
        lines.append("")
        return lines

    def _render_indexes_table(self, index_diffs: Sequence) -> list[str]:
        """Renderiza tabla de diferencias de índices."""
        lines: list[str] = [
            f"**{self._t('section.indexes')}:**",
            "",
            f"| {self._t('col.index')} | {self._t('col.status')} | {self._t('col.source_cols')} "
            f"| {self._t('col.target_cols')} |",
            self._TABLE_SEPARATOR_4COL,
        ]
        for idx in index_diffs:
            estado_idx: str | None = self._status.get(idx.status, idx.status)
            lines.append(
                f"| {_cell(idx.index_name)} | {estado_idx} | {_cell(idx.source_columns)} | {_cell(idx.target_columns)} |"
            )
        lines.append("")
        return lines

    def _render_fks_table(self, fk_diffs: Sequence) -> list[str]:
        """Renderiza tabla de diferencias de Foreign Keys."""
        lines: list[str] = [
            f"**{self._t('section.foreign_keys')}:**",
            "",
            f"| {self._t('col.fk')} | {self._t('col.status')} | {self._t('col.source_cols')} "
            f"| {self._t('col.source_ref_table_long')} | {self._t('col.target_cols')} "
            f"| {self._t('col.target_ref_table_long')} |",
            self._TABLE_SEPARATOR_6COL,
        ]
        for fk in fk_diffs:
            estado_fk: str | None = self._status.get(fk.status, fk.status)
            lines.append(
                f"| {_cell(fk.fk_name)} | {estado_fk} "
                f"| {_cell(fk.source_columns)} | {_cell(fk.source_referred_table)} "
                f"| {_cell(fk.target_columns)} | {_cell(fk.target_referred_table)} |",
            )
        lines.append("")
        return lines

    def _render_comments_table(self, comment_diffs: Sequence) -> list[str]:
        """Renderiza tabla de diferencias de comentarios."""
        lines: list[str] = [
            f"**{self._t('section.comments')}:**",
            "",
            f"| {self._t('col.object')} | {self._t('col.column')} | {self._t('col.source_comment')} "
            f"| {self._t('col.target_comment')} |",
            "|---|---|---|---|",
        ]
        table_word: str = self._t("label.table_word")
        for cm in comment_diffs:
            col_label: str = f"{_cell(cm.column_name)}" if cm.column_name else f"*({table_word})*"
            source_comment: str = escape_markdown_table_cell(cm.source_comment)
            target_comment: str = escape_markdown_table_cell(cm.target_comment)
            lines.append(f"| {_cell(cm.object_name)} | {col_label} | {source_comment} | {target_comment} |")
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
        lines: list[str] = [f"## {self._t('section.tables')}", ""]
        for td in table_diffs:
            emoji: str = STATUS_EMOJI.get(td.status, "")
            estado: str = self._status.get(td.status, td.status)
            lines.append(f"### {emoji} {_code(td.table_name)} — {estado}")
            lines.append("")
            lines += self._render_table_details(td)
        return lines

    def _render_views_section(self, view_diffs: Sequence[ViewDiff]) -> list[str]:
        if not view_diffs:
            return []
        lines: list[str] = [f"## {self._t('section.views')}", ""]
        for vd in view_diffs:
            emoji: str = STATUS_EMOJI.get(vd.status, "")
            estado: str = self._status.get(vd.status, vd.status)
            lines.append(f"### {emoji} {_code(vd.view_name)} — {estado}")
            lines.append("")
            if vd.status == "modified" and (vd.source_definition or vd.target_definition):
                lines.append(f"<details><summary>{self._t('md.show_definitions')}</summary>")
                lines.append("")
                if vd.source_definition:
                    src_ddl = DdlNormalizer.normalize_view_ddl(vd.source_definition)
                    lines.append(f"**{self._t('label.source')}:**\n```sql\n{src_ddl}\n```")
                if vd.target_definition:
                    tgt_ddl = DdlNormalizer.normalize_view_ddl(vd.target_definition)
                    lines.append(f"**{self._t('label.target')}:**\n```sql\n{tgt_ddl}\n```")
                lines.append("</details>")
                lines.append("")
        return lines

    def _render_routines_section(self, routine_diffs: Sequence[RoutineDiff]) -> list[str]:
        if not routine_diffs:
            return []
        lines: list[str] = [f"## {self._t('section.routines')}", ""]
        for rd in routine_diffs:
            emoji: str = STATUS_EMOJI.get(rd.status, "")
            estado: str = self._status.get(rd.status, rd.status)
            lines.append(f"### {emoji} {_code(rd.routine_name)} ({rd.routine_type}) — {estado}")
            lines.append("")
            if rd.status == "modified" and (rd.source_definition or rd.target_definition):
                lines.append(f"<details><summary>{self._t('md.show_definitions')}</summary>")
                lines.append("")
                if rd.source_definition:
                    src_ddl = DdlNormalizer.normalize_routine_ddl(rd.source_definition)
                    lines.append(f"**{self._t('label.source')}:**\n```sql\n{src_ddl}\n```")
                if rd.target_definition:
                    tgt_ddl = DdlNormalizer.normalize_routine_ddl(rd.target_definition)
                    lines.append(f"**{self._t('label.target')}:**\n```sql\n{tgt_ddl}\n```")
                lines.append("</details>")
                lines.append("")
        return lines
