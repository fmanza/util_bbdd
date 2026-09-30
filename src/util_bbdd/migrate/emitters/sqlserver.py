"""Emisor DDL para SQL Server.

Responsabilidades:
  - Generar CREATE TABLE con corchetes [name] y sin ENGINE/CHARSET.
  - Emitir IDENTITY(1,1) para columnas AUTO_INCREMENT.
  - Aplicar COLLATE a nivel columna en tipos string (opcional).
  - Ordenar tablas topológicamente (FKs primero la tabla referenciada).
  - Detectar FKs circulares y emitirlas como ALTER TABLE al final.
  - Emitir FK externas como ALTER TABLE con comentario al final del script.
  - Traducir defaults Oracle a equivalentes SQL Server.
  - Incluir comentarios -- AVISO: para tipos sin equivalente exacto.
"""

from __future__ import annotations

import re

from .._compat.identifier_rules import MAX_SQLSERVER_IDENTIFIER_LENGTH, truncate_identifier
from ..ir.models import CanonicalColumn, CanonicalFK, CanonicalRoutine, CanonicalTable, CanonicalView
from ._default_fallback import default_fallback_warning
from ._trailing_comment import join_definitions, one_line, with_trailing_comment
from .mariadb import _topological_sort, _topological_sort_views

# Tipos string en SQL Server que aceptan cláusula COLLATE a nivel columna
_SQLSERVER_STRING_TYPES: frozenset[str] = frozenset({"NVARCHAR", "VARCHAR", "NCHAR", "CHAR", "NTEXT", "TEXT"})

# Traducción de defaults Oracle a equivalentes SQL Server
_ORACLE_TO_SS_DEFAULTS: dict[str, str] = {
    "SYSDATE": "GETDATE()",
    "SYSTIMESTAMP": "SYSDATETIME()",
    "SYS_GUID()": "NEWID()",
    "USER": "SYSTEM_USER",
    "NOW()": "GETDATE()",
    "CURRENT_TIMESTAMP": "CURRENT_TIMESTAMP",
    "CURRENT_DATE": "CAST(GETDATE() AS DATE)",
    "NULL": "NULL",
    "0": "0",
    "1": "1",
}

# Acciones ON DELETE / ON UPDATE válidas en T-SQL (RESTRICT no existe en SQL Server)
_SS_FK_VALID_ACTIONS: frozenset[str] = frozenset({"CASCADE", "SET NULL", "SET DEFAULT"})


def _br(name: str) -> str:
    """Escapa un identificador SQL Server con corchetes."""
    return f"[{name.replace(']', ']]')}]"


def _is_string_type(target_type: str) -> bool:
    """True si el tipo SQL Server es string y acepta cláusula COLLATE."""
    base = target_type.split("(")[0].upper().strip()
    return base in _SQLSERVER_STRING_TYPES


class SQLServerDDLEmitter:
    """Genera DDL SQL Server desde IR canónico.

    Args:
        collation: COLLATE a nivel columna para tipos string (opcional).
            Si None, no se emite cláusula COLLATE (usa collation de la BD).
    """

    def __init__(self, collation: str | None = None) -> None:
        self._collation = collation

    # ─── API pública ──────────────────────────────────────────────────────────

    def emit(
        self,
        tables: list[CanonicalTable],
        views: list[CanonicalView] | None = None,
        routines: list[CanonicalRoutine] | None = None,
    ) -> str:
        """Genera el script DDL completo listo para guardar en fichero .sql.

        Args:
            tables: Tablas canónicas transformadas.
            views: Vistas canónicas transformadas. Se emiten después de las tablas.
            routines: Rutinas canónicas transformadas. Se emiten al final.

        Returns:
            Script SQL con sentencias separadas por ';\\n\\n' y terminado en ';\\n'.
        """
        stmts = self.emit_statements(tables, views, routines)
        return ";\n\n".join(stmts) + ";\n"

    def emit_statements(
        self,
        tables: list[CanonicalTable],
        views: list[CanonicalView] | None = None,
        routines: list[CanonicalRoutine] | None = None,
    ) -> list[str]:
        """Genera lista de sentencias DDL individuales sin ';' al final.

        Args:
            tables: Tablas canónicas transformadas.
            views: Vistas canónicas transformadas. Se emiten después de las tablas.
            routines: Rutinas canónicas transformadas. Se emiten al final.

        Returns:
            Lista de sentencias DDL (CREATE TABLE, CREATE INDEX, ALTER TABLE,
            CREATE OR ALTER VIEW, CREATE PROCEDURE/FUNCTION) en el orden correcto
            para ejecución.
        """
        ordered, circular_fk_pairs = _topological_sort(tables)

        external_fk_pairs: list[tuple[str, CanonicalFK]] = [
            (t.name, fk) for t in ordered for fk in t.foreign_keys if fk.is_external
        ]

        statements: list[str] = []

        for table in ordered:
            skip_fk_names = {fk.name for _, fk in circular_fk_pairs if _ == table.name}
            stmt = self._emit_create_table(table, skip_fk_names=skip_fk_names)
            if table.comment:
                stmt = f"-- COMMENT: {one_line(table.comment)}\n{stmt}"
            statements.append(stmt)

        for table in ordered:
            for stmt in self._emit_indexes(table):
                statements.append(stmt)

        for table_name, fk in circular_fk_pairs:
            statements.append(self._emit_alter_table_add_fk(table_name, fk))

        for table_name, fk in external_fk_pairs:
            fk_stmt = self._emit_alter_table_add_fk(table_name, fk)
            stmt = (
                f"-- FK externa: [{one_line(fk.name)}] en [{one_line(table_name)}] referencia "
                f"[{one_line(fk.ref_table)}] (fuera del schema migrado) — verificar que existe\n"
                f"{fk_stmt}"
            )
            statements.append(stmt)

        # Vistas DESPUÉS de todas las tablas
        statements.extend(self._emit_view_statements(views))

        # Rutinas AL FINAL
        statements.extend(self._emit_routine_statements(routines))

        return statements

    def _emit_routine_statements(self, routines: list[CanonicalRoutine] | None) -> list[str]:
        return [self._emit_create_routine(r) for r in (routines or [])]

    def _emit_create_routine(self, routine: CanonicalRoutine) -> str:
        lines: list[str] = []
        if routine.is_package_member:
            pkg = routine.package_name or routine.name
            lines.append(
                f"-- PACKAGE MEMBER: {one_line(pkg)}.{one_line(routine.name)} ({one_line(routine.routine_type)})\n"
                f"-- No direct equivalent in SQL Server; manual migration required"
            )
        lines.append(f"-- {one_line(routine.routine_type)}: {one_line(_br(routine.name))}")
        if routine.warnings:
            lines.append("-- NOTE: requires manual review (see migration warnings)")
        if routine.comment:
            lines.append(f"-- COMMENT: {one_line(routine.comment)}")
        if not routine.body:
            lines.append(
                f"-- TODO: {one_line(routine.routine_type)} {one_line(_br(routine.name))} — "
                f"body not available; manual implementation required"
            )
            return "\n".join(lines)
        lines.append(routine.body)
        return "\n".join(lines)

    def _emit_view_statements(self, views: list[CanonicalView] | None) -> list[str]:
        active = [v for v in (views or []) if v.query]
        ordered, circular = _topological_sort_views(active)
        stmts: list[str] = [self._emit_create_view(v) for v in ordered]
        for v in circular:
            aviso = (
                f"-- AVISO: vista '{one_line(v.name)}' participa en una dependencia circular "
                "— verificar orden de ejecución manualmente\n"
            )
            stmts.append(aviso + self._emit_create_view(v))
        return stmts

    def _emit_create_view(self, view: CanonicalView) -> str:
        lines: list[str] = []
        # CREATE OR ALTER VIEW requiere SQL Server 2016+ (compatibilidad 130+)
        lines.append("-- NOTE: CREATE OR ALTER VIEW requires SQL Server 2016+ (compatibility level 130+)")
        if view.warnings:
            lines.append("-- NOTE: requires manual review (see migration warnings)")
        if view.comment:
            lines.append(f"-- COMMENT: {one_line(view.comment)}")
        lines.append(f"CREATE OR ALTER VIEW {_br(view.name)} AS")
        lines.append(view.query)
        return "\n".join(lines)

    # ─── CREATE TABLE ─────────────────────────────────────────────────────────

    def _emit_create_table(self, table: CanonicalTable, skip_fk_names: set[str]) -> str:
        lines: list[str] = [f"CREATE TABLE {_br(table.name)} ("]
        comment_lines: list[str] = []
        ddl_lines: list[str] = []

        for col in table.columns:
            line = self._emit_column(col, table.name)
            if col.omit:
                comment_lines.append(line)
            else:
                ddl_lines.append(line)

        if table.primary_key:
            pk_cols = ", ".join(_br(c) for c in table.primary_key)
            pk_name = _br(truncate_identifier(f"PK_{table.name}", MAX_SQLSERVER_IDENTIFIER_LENGTH)[0])
            ddl_lines.append(f"    CONSTRAINT {pk_name} PRIMARY KEY ({pk_cols})")

        for fk in table.foreign_keys:
            if fk.is_external:
                continue
            if fk.name in skip_fk_names:
                continue
            ddl_lines.append(self._emit_fk_inline(fk))

        if not ddl_lines:
            comment_lines.append("    -- ERROR: tabla sin columnas activas tras omisión de tipos incompatibles")

        body_parts: list[str] = []
        if comment_lines:
            body_parts.append("\n".join(comment_lines))
        if ddl_lines:
            body_parts.append(join_definitions(ddl_lines))

        lines.append("\n".join(body_parts))
        lines.append(")")

        return "\n".join(lines)

    def _emit_column(self, col: CanonicalColumn, table_name: str) -> str:
        if col.omit:
            comment = one_line(col.ddl_comment or f"-- AVISO: columna '{col.original_name}' omitida")
            return f"    {comment}"

        parts = [f"    {_br(col.name)}", col.target_type]

        if self._collation and _is_string_type(col.target_type):
            parts.append(f"COLLATE {self._collation}")

        if col.auto_increment:
            parts.append("IDENTITY(1,1)")

        parts.append("NOT NULL" if not col.nullable else "NULL")

        if not col.auto_increment and col.default is not None:
            default_val = _format_default_sqlserver(col.default)
            parts.append(f"DEFAULT {default_val}")
            fallback_warning = default_fallback_warning(
                raw_value=col.default,
                formatted_value=default_val,
                table=table_name,
                column=col.name,
                source_type=col.source_type,
                target_type=col.target_type,
            )
            if fallback_warning is not None and fallback_warning not in col.warnings:
                col.warnings.append(fallback_warning)

        line = " ".join(parts)

        # Comentarios trailing: comment Oracle + aviso de migración
        trailing: list[str] = []
        if col.comment:
            trailing.append(col.comment)
        if col.ddl_comment:
            aviso = col.ddl_comment.lstrip("- ").strip()
            if aviso:
                trailing.append(aviso)

        if trailing:
            line = with_trailing_comment(line, "-- " + one_line(" | ".join(trailing)))

        return line

    def _emit_fk_inline(self, fk: CanonicalFK) -> str:
        cols = ", ".join(_br(c) for c in fk.columns)
        ref_cols = ", ".join(_br(c) for c in fk.ref_columns)
        stmt = f"    CONSTRAINT {_br(fk.name)} FOREIGN KEY ({cols}) REFERENCES {_br(fk.ref_table)} ({ref_cols})"
        # SQL Server sólo acepta CASCADE, SET NULL y SET DEFAULT; RESTRICT no es T-SQL válido.
        if fk.on_delete and fk.on_delete.upper() in _SS_FK_VALID_ACTIONS:
            stmt += f" ON DELETE {fk.on_delete.upper()}"
        if fk.on_update and fk.on_update.upper() in _SS_FK_VALID_ACTIONS:
            stmt += f" ON UPDATE {fk.on_update.upper()}"
        return stmt

    def _emit_alter_table_add_fk(self, table_name: str, fk: CanonicalFK) -> str:
        fk_inline = self._emit_fk_inline(fk).strip()
        return f"ALTER TABLE {_br(table_name)} ADD {fk_inline}"

    # ─── Índices ──────────────────────────────────────────────────────────────

    def _emit_indexes(self, table: CanonicalTable) -> list[str]:
        pk_set = {c.upper() for c in table.primary_key}
        omitted_cols = {col.name.upper() for col in table.columns if col.omit}
        stmts: list[str] = []

        for idx in table.indexes:
            idx_col_set = {c.upper() for c in idx.columns}
            if idx_col_set == pk_set and idx.unique:
                continue
            if idx_col_set & omitted_cols:
                continue

            unique_kw = "UNIQUE " if idx.unique else ""
            cols = ", ".join(_br(c) for c in idx.columns)
            stmt = f"CREATE {unique_kw}INDEX {_br(idx.name)} ON {_br(table.name)} ({cols})"
            stmts.append(stmt)

        return stmts


def _format_default_sqlserver(value: str) -> str:
    """Traduce un valor DEFAULT Oracle a su equivalente SQL Server."""
    if not value:
        return "NULL"

    v = value.strip()
    upper_v = v.upper()

    if upper_v in _ORACLE_TO_SS_DEFAULTS:
        return _ORACLE_TO_SS_DEFAULTS[upper_v]

    # Funciones temporales con argumento de precisión, ej. NOW(3) → SYSDATETIME()
    if re.match(
        r"^(NOW|CURRENT_TIMESTAMP|GETDATE)\s*\(\s*\d+\s*\)$",
        v,
        re.IGNORECASE,
    ):
        return "SYSDATETIME()"

    # Valores numéricos
    try:
        float(v)
        return v
    except ValueError:
        pass

    # String literal ya entrecomillado (Oracle almacena DATA_DEFAULT con comillas, p.ej. '6')
    if len(v) >= 2 and v.startswith("'") and v.endswith("'"):
        return v

    # String literal sin entrecomillar
    escaped = v.replace("'", "''")
    return f"'{escaped}'"


__all__: list[str] = ["SQLServerDDLEmitter"]
