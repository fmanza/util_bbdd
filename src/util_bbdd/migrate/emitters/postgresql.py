"""Emisor DDL para PostgreSQL.

Responsabilidades:
  - Generar CREATE TABLE con comillas dobles "name".
  - Emitir SERIAL/BIGSERIAL/SMALLSERIAL para columnas AUTO_INCREMENT.
  - Incluir SET search_path = schema; al inicio si pg_schema no es None.
  - Ordenar tablas topológicamente (FKs primero la tabla referenciada).
  - Detectar FKs circulares y emitirlas como ALTER TABLE al final.
  - Emitir FK externas como ALTER TABLE con comentario al final del script.
  - Traducir defaults Oracle a equivalentes PostgreSQL.
  - Incluir comentarios -- AVISO: para tipos sin equivalente exacto.
"""

from __future__ import annotations

import re

from .._compat.identifier_rules import MAX_POSTGRESQL_IDENTIFIER_LENGTH, truncate_identifier
from ..ir.models import CanonicalColumn, CanonicalFK, CanonicalRoutine, CanonicalTable, CanonicalView
from ._default_fallback import default_fallback_warning
from .mariadb import _topological_sort, _topological_sort_views

# Tipos PG que admiten SERIAL: mapa tipo → variante SERIAL
_PG_SERIAL_MAP: dict[str, str] = {
    "SMALLINT": "SMALLSERIAL",
    "INTEGER": "SERIAL",
    "BIGINT": "BIGSERIAL",
}

# Traducción de defaults Oracle a equivalentes PostgreSQL
_ORACLE_TO_PG_DEFAULTS: dict[str, str] = {
    "SYSDATE": "NOW()",
    "SYSTIMESTAMP": "NOW()",
    "SYS_GUID()": "gen_random_uuid()",
    "USER": "CURRENT_USER",
    "NOW()": "NOW()",
    "CURRENT_TIMESTAMP": "CURRENT_TIMESTAMP",
    "CURRENT_DATE": "CURRENT_DATE",
    "NULL": "NULL",
    "0": "0",
    "1": "1",
}


def _dq(name: str) -> str:
    """Escapa un identificador PostgreSQL con comillas dobles."""
    return f'"{name.replace(chr(34), chr(34) + chr(34))}"'


def _serial_type(target_type: str) -> str | None:
    """Retorna la variante SERIAL correspondiente al tipo entero, o None."""
    base = target_type.split("(")[0].upper().strip()
    return _PG_SERIAL_MAP.get(base)


class PostgreSQLDDLEmitter:
    """Genera DDL PostgreSQL desde IR canónico.

    Args:
        pg_schema: Schema PostgreSQL. Si se indica, emite ``SET search_path = schema;``
            al inicio del script (útil para ejecutar en esquemas no públicos).
    """

    def __init__(self, pg_schema: str | None = None) -> None:
        self._pg_schema = pg_schema

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

        Returns:
            Lista de sentencias DDL (SET search_path, CREATE TABLE, CREATE INDEX,
            ALTER TABLE, CREATE OR REPLACE VIEW) en el orden correcto.
        """
        ordered, circular_fk_pairs = _topological_sort(tables)

        external_fk_pairs: list[tuple[str, CanonicalFK]] = [
            (t.name, fk) for t in ordered for fk in t.foreign_keys if fk.is_external
        ]

        statements: list[str] = []

        if self._pg_schema:
            statements.append(f"SET search_path = {_dq(self._pg_schema)}")

        for table in ordered:
            skip_fk_names = {fk.name for _, fk in circular_fk_pairs if _ == table.name}
            stmt = self._emit_create_table(table, skip_fk_names=skip_fk_names)
            if table.comment:
                stmt = f"-- COMMENT: {table.comment}\n{stmt}"
            statements.append(stmt)

        for table in ordered:
            for stmt in self._emit_indexes(table):
                statements.append(stmt)

        for table_name, fk in circular_fk_pairs:
            statements.append(self._emit_alter_table_add_fk(table_name, fk))

        for table_name, fk in external_fk_pairs:
            fk_stmt = self._emit_alter_table_add_fk(table_name, fk)
            stmt = (
                f"-- FK externa: {_dq(fk.name)} en {_dq(table_name)} referencia "
                f"{_dq(fk.ref_table)} (fuera del schema migrado) — verificar que existe\n"
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
                f"-- PACKAGE MEMBER: {pkg}.{routine.name} ({routine.routine_type})\n"
                f"-- No direct equivalent in PostgreSQL; manual migration required"
            )
        lines.append(f"-- {routine.routine_type}: {_dq(routine.name)}")
        if routine.warnings:
            lines.append("-- NOTE: requires manual review (see migration warnings)")
        if routine.comment:
            lines.append(f"-- COMMENT: {routine.comment.replace(chr(10), ' ')}")
        if not routine.body:
            lines.append(
                f"-- TODO: {routine.routine_type} {_dq(routine.name)} — "
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
                f"-- AVISO: vista '{v.name}' participa en una dependencia circular "
                "— verificar orden de ejecución manualmente\n"
            )
            stmts.append(aviso + self._emit_create_view(v))
        return stmts

    def _emit_create_view(self, view: CanonicalView) -> str:
        lines: list[str] = []
        if view.warnings:
            lines.append("-- NOTE: requires manual review (see migration warnings)")
        if view.comment:
            lines.append(f"-- COMMENT: {view.comment.replace(chr(10), ' ')}")
        lines.append(f"CREATE OR REPLACE VIEW {_dq(view.name)} AS")
        lines.append(view.query)
        return "\n".join(lines)

    # ─── CREATE TABLE ─────────────────────────────────────────────────────────

    def _emit_create_table(self, table: CanonicalTable, skip_fk_names: set[str]) -> str:
        lines: list[str] = [f"CREATE TABLE {_dq(table.name)} ("]
        comment_lines: list[str] = []
        ddl_lines: list[str] = []

        for col in table.columns:
            line = self._emit_column(col, table.name)
            if col.omit:
                comment_lines.append(line)
            else:
                ddl_lines.append(line)

        if table.primary_key:
            pk_cols = ", ".join(_dq(c) for c in table.primary_key)
            pk_name_raw = truncate_identifier(f"PK_{table.name}", MAX_POSTGRESQL_IDENTIFIER_LENGTH)[0]
            ddl_lines.append(f"    CONSTRAINT {_dq(pk_name_raw)} PRIMARY KEY ({pk_cols})")

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
            body_parts.append(",\n".join(ddl_lines))

        lines.append("\n".join(body_parts))
        lines.append(")")

        return "\n".join(lines)

    def _emit_column(self, col: CanonicalColumn, table_name: str) -> str:
        if col.omit:
            comment = col.ddl_comment or f"-- AVISO: columna '{col.original_name}' omitida"
            return f"    {comment}"

        if col.auto_increment:
            return self._emit_auto_increment_column(col)

        return self._emit_regular_column(col, table_name)

    def _emit_auto_increment_column(self, col: CanonicalColumn) -> str:
        serial = _serial_type(col.target_type) or "SERIAL"
        line = f"    {_dq(col.name)} {serial}"
        trailing: list[str] = []
        if col.comment:
            trailing.append(col.comment)
        if trailing:
            line += " -- " + " | ".join(trailing)
        return line

    def _emit_regular_column(self, col: CanonicalColumn, table_name: str) -> str:
        parts = [f"    {_dq(col.name)}", col.target_type]
        parts.append("NOT NULL" if not col.nullable else "NULL")

        if col.default is not None:
            self._handle_column_default(col, table_name, parts)

        line = " ".join(parts)
        trailing_items = self._build_trailing_items(col)

        if trailing_items:
            line += " -- " + " | ".join(trailing_items)

        return line

    def _handle_column_default(self, col: CanonicalColumn, table_name: str, parts: list[str]) -> None:
        default_value = col.default
        if default_value is None:
            return

        default_val = _format_default_postgresql(default_value)
        parts.append(f"DEFAULT {default_val}")
        fallback_warning = default_fallback_warning(
            raw_value=default_value,
            formatted_value=default_val,
            table=table_name,
            column=col.name,
            source_type=col.oracle_type,
            target_type=col.target_type,
        )
        if fallback_warning is not None and fallback_warning not in col.warnings:
            col.warnings.append(fallback_warning)

    def _build_trailing_items(self, col: CanonicalColumn) -> list[str]:
        trailing_items: list[str] = []
        if col.comment:
            trailing_items.append(col.comment)
        if col.ddl_comment:
            aviso = col.ddl_comment.lstrip("- ").strip()
            if aviso:
                trailing_items.append(aviso)
        return trailing_items

    def _emit_fk_inline(self, fk: CanonicalFK) -> str:
        cols = ", ".join(_dq(c) for c in fk.columns)
        ref_cols = ", ".join(_dq(c) for c in fk.ref_columns)
        stmt = f"    CONSTRAINT {_dq(fk.name)} FOREIGN KEY ({cols}) REFERENCES {_dq(fk.ref_table)} ({ref_cols})"
        if fk.on_delete and fk.on_delete.upper() not in ("NO ACTION", ""):
            stmt += f" ON DELETE {fk.on_delete.upper()}"
        if fk.on_update and fk.on_update.upper() not in ("NO ACTION", ""):
            stmt += f" ON UPDATE {fk.on_update.upper()}"
        return stmt

    def _emit_alter_table_add_fk(self, table_name: str, fk: CanonicalFK) -> str:
        fk_inline = self._emit_fk_inline(fk).strip()
        return f"ALTER TABLE {_dq(table_name)} ADD {fk_inline}"

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
            cols = ", ".join(_dq(c) for c in idx.columns)
            stmt = f"CREATE {unique_kw}INDEX {_dq(idx.name)} ON {_dq(table.name)} ({cols})"
            stmts.append(stmt)

        return stmts


def _format_default_postgresql(value: str) -> str:
    """Traduce un valor DEFAULT Oracle a su equivalente PostgreSQL."""
    if not value:
        return "NULL"

    v = value.strip()
    upper_v = v.upper()

    if upper_v in _ORACLE_TO_PG_DEFAULTS:
        return _ORACLE_TO_PG_DEFAULTS[upper_v]

    # Funciones temporales con argumento de precisión, ej. CURRENT_TIMESTAMP(6)
    if re.match(
        r"^(NOW|CURRENT_TIMESTAMP|CURRENT_DATE|CURRENT_TIME)\s*\(\s*\d*\s*\)$",
        v,
        re.IGNORECASE,
    ):
        return v

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


__all__: list[str] = ["PostgreSQLDDLEmitter"]
