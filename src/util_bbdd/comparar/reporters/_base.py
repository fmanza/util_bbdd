"""Utilidades base compartidas entre los reporters de SchemaDiff."""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Literal

from ..models import SchemaDiff

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
    """Genera el nombre base (sin extensión) para el fichero de reporte."""
    src = sanitize_filename(diff.source_label)
    tgt = sanitize_filename(diff.target_label)
    return f"{src}_vs_{tgt}_diff"


def escape_mermaid_label(name: str) -> str:
    """Escapa un nombre para usarlo como label en un diagrama Mermaid."""
    return name.replace('"', "'").replace("[", "(").replace("]", ")")
