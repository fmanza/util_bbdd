"""Utilidades base compartidas entre los reporters de SchemaDiff."""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import ClassVar, Literal

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


class DdlNormalizer:
    """Normaliza DDL de vistas y rutinas eliminando artefactos dialect-específicos.

    Los motores como MariaDB/MySQL incluyen metadatos en el DDL almacenado
    (``DEFINER``, ``ALGORITHM``, ``SQL SECURITY``) que no forman parte de la
    definición semántica del objeto y deben eliminarse antes de mostrar o
    exportar el DDL para aplicar en el motor destino.

    Uso::

        from util_bbdd.comparar.reporters._base import DdlNormalizer

        clean = DdlNormalizer.normalize_view_ddl(raw_ddl)
        body  = DdlNormalizer.extract_view_body(raw_ddl)

    Todos los métodos son ``@staticmethod`` puro (sin estado de instancia).
    Los patrones son ``ClassVar`` para permitir extensión sin modificar la lógica.
    """

    #: Patrones de artefactos a eliminar de DDL de vistas (MariaDB/MySQL/Oracle).
    #: Orden significativo: ALGORITHM antes de DEFINER; SQL SECURITY al final.
    _VIEW_STRIP_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (r"ALGORITHM\s*=\s*\w+", ""),                   # MariaDB/MySQL ALGORITHM=UNDEFINED etc.
        (r"DEFINER\s*=\s*`[^`]+`@`[^`]+`", ""),        # DEFINER con backticks
        (r"DEFINER\s*=\s*'[^']*'@'[^']*'", ""),        # DEFINER con comillas simples
        (r"DEFINER\s*=\s*\S+@\S+", ""),                # DEFINER sin comillas
        (r"SQL\s+SECURITY\s+(?:DEFINER|INVOKER)", ""), # SQL SECURITY
        (r"\bFORCE\s+(?=VIEW\b)", ""),                 # Oracle FORCE VIEW
    ]

    #: Patrones a eliminar de DDL de rutinas.
    #: No se elimina LANGUAGE ya que es parte semántica de la rutina PostgreSQL.
    _ROUTINE_STRIP_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (r"DEFINER\s*=\s*`[^`]+`@`[^`]+`", ""),
        (r"DEFINER\s*=\s*'[^']*'@'[^']*'", ""),
        (r"DEFINER\s*=\s*\S+@\S+", ""),
    ]

    @staticmethod
    def normalize_view_ddl(raw_ddl: str) -> str:
        """Elimina artefactos dialect-específicos de un DDL de vista.

        Strips: ``ALGORITHM=…``, ``DEFINER=…``, ``SQL SECURITY …``, Oracle ``FORCE``.
        Preserva: header ``CREATE [OR REPLACE] VIEW``, cuerpo SELECT, cualquier
        cláusula semántica propia de la vista.

        Args:
            raw_ddl: DDL crudo tal como lo devuelve el Inspector o el comparador.

        Returns:
            DDL limpio sin metadatos de motor; puede seguir incluyendo el header
            ``CREATE VIEW …``.
        """
        result = raw_ddl
        for pattern, replacement in DdlNormalizer._VIEW_STRIP_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        result = re.sub(r"[ \t]{2,}", " ", result)
        return result.strip()

    @staticmethod
    def normalize_routine_ddl(raw_ddl: str) -> str:
        """Elimina ``DEFINER=…`` de un DDL de rutina (procedure/function).

        Preserva ``LANGUAGE``, ``SECURITY DEFINER/INVOKER`` y cualquier otra
        cláusula semántica del cuerpo de la rutina.

        Args:
            raw_ddl: DDL crudo de la rutina.

        Returns:
            DDL limpio sin el bloque ``DEFINER=…``.
        """
        result = raw_ddl
        for pattern, replacement in DdlNormalizer._ROUTINE_STRIP_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        result = re.sub(r"[ \t]{2,}", " ", result)
        return result.strip()

    @staticmethod
    def extract_view_body(raw_ddl: str) -> str:
        """Extrae el cuerpo SELECT de un DDL de vista, eliminando el header CREATE VIEW.

        Reconoce nombres de vista con backticks, comillas dobles o sin comillas::

            CREATE [OR REPLACE] [...] VIEW `my_view` AS SELECT ...
            CREATE VIEW "my_view" AS SELECT ...
            CREATE VIEW my_view AS SELECT ...

        Args:
            raw_ddl: DDL completo (posiblemente con artefactos) o solo el cuerpo SELECT.

        Returns:
            El cuerpo SELECT/WITH de la vista, sin el header.
            Si no se detecta un header ``VIEW … AS``, devuelve el input sin cambios
            (asume que ya es solo el cuerpo).
        """
        match = re.search(
            r"(?i)\bVIEW\b\s+(?:`[^`]+`|\"[^\"]+\"|[^\s(]+)\s+AS\b",
            raw_ddl,
        )
        if match:
            return raw_ddl[match.end():].strip()
        return raw_ddl.strip()
