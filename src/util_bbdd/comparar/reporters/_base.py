"""Utilidades base compartidas entre los reporters de SchemaDiff."""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal

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
        (r"ALGORITHM\s*=\s*\w+", ""),  # MariaDB/MySQL ALGORITHM=UNDEFINED etc.
        (r"DEFINER\s*=\s*`[^`]+`@`[^`]+`", ""),  # DEFINER con backticks
        (r"DEFINER\s*=\s*'[^']*'@'[^']*'", ""),  # DEFINER con comillas simples
        (r"DEFINER\s*=\s*\S+@\S+", ""),  # DEFINER sin comillas
        (r"SQL\s+SECURITY\s+(?:DEFINER|INVOKER)", ""),  # SQL SECURITY
        (r"\bFORCE\s+(?=VIEW\b)", ""),  # Oracle FORCE VIEW (elimina solo "FORCE ", preserva "VIEW")
    ]

    #: Patrones a eliminar de DDL de rutinas.
    #: No se elimina LANGUAGE ya que es parte semántica de la rutina PostgreSQL.
    _ROUTINE_STRIP_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        (r"DEFINER\s*=\s*`[^`]+`@`[^`]+`", ""),
        (r"DEFINER\s*=\s*'[^']*'@'[^']*'", ""),
        (r"DEFINER\s*=\s*\S+@\S+", ""),
    ]

    #: Patrones adicionales para normalización orientada a comparación semántica.
    #: Complementa ``_VIEW_STRIP_PATTERNS`` con artefactos de SQL Server y PostgreSQL
    #: que solo tienen sentido al comparar DDLs entre motores (no para display).
    #: Fuente de verdad única: reemplaza ``SchemaComparator._DDL_STRIP_RULES``.
    _COMPARISON_EXTRA_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        # Oracle: elimina FORCE de "CREATE OR REPLACE FORCE VIEW …" — preserva header estándar
        (r"CREATE\s+OR\s+REPLACE\s+FORCE\b", "CREATE OR REPLACE"),
        # SQL Server: escaping de identificadores con corchetes [name] → name
        (r"\[([^\]]+)\]", r"\1"),
        # SQL Server: WITH storage hints (FILLFACTOR, PAD_INDEX, etc.)
        (r"\s+WITH\s*\([^)]*\)(?=\s|$)", ""),
        # PostgreSQL: LANGUAGE clause (no semántica cross-motor)
        (r"\s+LANGUAGE\s+\w+", ""),
        # PostgreSQL: SECURITY clauses
        (r"\s+SECURITY\s+(?:DEFINER|INVOKER)", ""),
        # PostgreSQL: NULL handling modifiers
        (r"\s+(STRICT|RETURNS\s+NULL\s+ON\s+NULL\s+INPUT)", ""),
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
    def strip_dialect_artifacts(raw_ddl: str) -> str:
        """Elimina artefactos dialect-específicos sin normalizar espacios ni cambiar case.

        Aplica ``_VIEW_STRIP_PATTERNS`` + ``_COMPARISON_EXTRA_PATTERNS`` sobre el DDL
        crudo.  No colapsa espacios ni convierte a minúsculas — útil cuando el resultado
        se mostrará al usuario o cuando el código llamador necesita control del case.

        Args:
            raw_ddl: DDL crudo de vista o rutina.

        Returns:
            DDL con artefactos eliminados pero con case y espacios originales.

        Example:
            >>> DdlNormalizer.strip_dialect_artifacts("CREATE OR REPLACE FORCE VIEW v AS SELECT 1")
            'CREATE OR REPLACE  VIEW v AS SELECT 1'

            Note: double space after REPLACE is intentional — spaces are not collapsed
            in this method. Use ``normalize_for_comparison`` if collapsed output is needed.
        """
        result = raw_ddl
        for pattern, replacement in DdlNormalizer._VIEW_STRIP_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        for pattern, replacement in DdlNormalizer._COMPARISON_EXTRA_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    @staticmethod
    def normalize_for_comparison(raw_ddl: str) -> str:
        """Normalización completa para comparación semántica de DDL entre motores.

        Aplica ``_VIEW_STRIP_PATTERNS`` + ``_COMPARISON_EXTRA_PATTERNS`` y colapsa
        espacios en blanco para obtener un DDL canónico independiente del motor.
        Más agresiva que ``normalize_view_ddl`` (que solo limpia para display).

        Args:
            raw_ddl: DDL crudo de vista o rutina, tal como lo retorna el Inspector.

        Returns:
            DDL normalizado en minúsculas con espacios colapsados, apto para
            comparación textual entre motores distintos.

        Example:
            >>> DdlNormalizer.normalize_for_comparison("CREATE OR REPLACE FORCE VIEW v AS SELECT 1")
            'create or replace view v as select 1'
        """
        if not raw_ddl:
            return ""
        result = raw_ddl
        for pattern, replacement in DdlNormalizer._VIEW_STRIP_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        for pattern, replacement in DdlNormalizer._COMPARISON_EXTRA_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", result).strip().lower()

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
            return raw_ddl[match.end() :].strip()
        return raw_ddl.strip()
