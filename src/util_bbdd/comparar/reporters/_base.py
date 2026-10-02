"""Utilidades base compartidas entre los reporters de SchemaDiff."""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from util_bbdd.comparar._ddl import DdlNormalizer

if TYPE_CHECKING:
    from util_bbdd.comparar.models import SchemaDiff

StatusLabel = Literal["added", "removed", "modified"]

STATUS_ES: dict[str, str] = {
    "added": "Añadido",
    "removed": "Eliminado",
    "modified": "Modificado",
}

STATUS_EMOJI: dict[str, str] = {
    "added": "✅",
    "removed": "❌",
    "modified": "⚠️",
}


@dataclass(frozen=True)
class DiffSummary:
    """Resumen de diferencias derivado de SchemaDiff para facilitar el rendering."""

    source_label: str
    target_label: str
    total_tables: int
    tables_added: int
    tables_removed: int
    tables_modified: int
    total_views: int
    views_added: int
    views_removed: int
    views_modified: int
    total_routines: int
    routines_added: int
    routines_removed: int
    routines_modified: int
    has_differences: bool


def build_diff_summary(diff: SchemaDiff) -> DiffSummary:
    """Construye un DiffSummary a partir de un SchemaDiff."""
    tables_added = sum(1 for t in diff.table_diffs if t.status == "added")
    tables_removed = sum(1 for t in diff.table_diffs if t.status == "removed")
    tables_modified = sum(1 for t in diff.table_diffs if t.status == "modified")
    views_added = sum(1 for v in diff.view_diffs if v.status == "added")
    views_removed = sum(1 for v in diff.view_diffs if v.status == "removed")
    views_modified = sum(1 for v in diff.view_diffs if v.status == "modified")
    routines_added = sum(1 for r in diff.routine_diffs if r.status == "added")
    routines_removed = sum(1 for r in diff.routine_diffs if r.status == "removed")
    routines_modified = sum(1 for r in diff.routine_diffs if r.status == "modified")
    return DiffSummary(
        source_label=diff.source_label,
        target_label=diff.target_label,
        total_tables=len(diff.table_diffs),
        tables_added=tables_added,
        tables_removed=tables_removed,
        tables_modified=tables_modified,
        total_views=len(diff.view_diffs),
        views_added=views_added,
        views_removed=views_removed,
        views_modified=views_modified,
        total_routines=len(diff.routine_diffs),
        routines_added=routines_added,
        routines_removed=routines_removed,
        routines_modified=routines_modified,
        has_differences=diff.has_differences,
    )


def sanitize_filename(label: str) -> str:
    """Convierte un label de schema en un nombre de fichero válido."""
    sanitized = re.sub(r"[^\w\-]", "_", label)
    return sanitized[:64]


def build_output_stem(diff: SchemaDiff) -> str:
    """Genera el nombre base (sin extensión) para el fichero de reporte.

    Usa ``source_short_label`` / ``target_short_label`` cuando están disponibles
    (producen nombres compactos con usuario/schema/database según motor).
    Recae en ``source_label`` / ``target_label`` para retrocompatibilidad.
    """
    src_short = diff.source_short_label
    tgt_short = diff.target_short_label
    if src_short and tgt_short:
        src = sanitize_filename(src_short)
        tgt = sanitize_filename(tgt_short)
    else:
        src = sanitize_filename(diff.source_label)
        tgt = sanitize_filename(diff.target_label)
    return f"{src}_vs_{tgt}_diff"


def escape_mermaid_label(name: str) -> str:
    """Escapa un nombre para usarlo como label en un diagrama Mermaid."""
    return name.replace('"', "'").replace("[", "(").replace("]", ")")


def escape_markdown_table_cell(value: str) -> str:
    """Escapa texto libre (p.ej. comentarios de BD) para una celda de tabla Markdown.

    BLK-07 (AUDIT_CODE 2026-09-22): un comentario de BD es texto libre sin
    restricciones — puede contener "|" (rompe la estructura de columnas de la
    tabla), backticks (abren un code span sin cerrar) o saltos de línea
    (terminan la fila antes de tiempo). Se escapan con backslash por ser
    caracteres de puntuación ASCII válidos para backslash-escape en CommonMark.
    """
    if not value:
        return value
    escaped = value.replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`")
    return escaped.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


__all__: list[str] = [
    "STATUS_EMOJI",
    "STATUS_ES",
    "DdlNormalizer",  # reexportado desde comparar/_ddl.py
    "DiffSummary",
    "StatusLabel",
    "build_diff_summary",
    "build_output_stem",
    "escape_markdown_table_cell",
    "escape_mermaid_label",
    "sanitize_filename",
]
