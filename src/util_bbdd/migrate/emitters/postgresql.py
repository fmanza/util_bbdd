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

from ..ir.models import CanonicalColumn, CanonicalFK, CanonicalTable
from .mariadb import _topological_sort

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

    def emit(self, tables: list[CanonicalTable]) -> str:
        """Genera el script DDL completo listo para guardar en fichero .sql.

        Args:
            tables: Tablas canónicas transformadas.

        Returns:
            Script SQL con sentencias separadas por ';\\n\\n' y terminado en ';\\n'.
        """
        stmts = self.emit_statements(tables)
        return ";\n\n".join(stmts) + ";\n"

    def emit_statements(self, tables: list[CanonicalTable]) -> list[str]:
        """Genera lista de sentencias DDL individuales sin ';' al final.

        Args:
            tables: Tablas canónicas transformadas.

        Returns:
            Lista de sentencias DDL (SET search_path, CREATE TABLE, CREATE INDEX,
            ALTER TABLE) en el orden correcto para ejecución sin desactivar FK_CHECKS.
        """
        ordered, circular_fk_pairs = _topological_sort(tables)

        external_fk_pairs: list[tuple[str, CanonicalFK]] = [
            (t.name, fk)
            for t in ordered
            for fk in t.foreign_keys
            if fk.is_external
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

        return statements

    # ─── CREATE TABLE ─────────────────────────────────────────────────────────

    def _emit_create_table(self, table: CanonicalTable, skip_fk_names: set[str]) -> str:
        lines: list[str] = [f"CREATE TABLE {_dq(table.name)} ("]
        comment_lines: list[str] = []
        ddl_lines: list[str] = []

        for col in table.columns:
            line = self._emit_column(col)
            if col.omit:
                comment_lines.append(line)
            else:
                ddl_lines.append(line)

        if table.primary_key:
            pk_cols = ", ".join(_dq(c) for c in table.primary_key)
            pk_name_raw = f"PK_{table.name}"[:63]
            ddl_lines.append(f"    CONSTRAINT {_dq(pk_name_raw)} PRIMARY KEY ({pk_cols})")

        for fk in table.foreign_keys:
            if fk.is_external:
                continue
            if fk.name in skip_fk_names:
                continue
            ddl_lines.append(self._emit_fk_inline(fk))

        if not ddl_lines:
            comment_lines.append(
                "    -- ERROR: tabla sin columnas activas tras omisión de tipos incompatibles"
            )

        body_parts: list[str] = []
        if comment_lines:
            body_parts.append("\n".join(comment_lines))
        if ddl_lines:
            body_parts.append(",\n".join(ddl_lines))

        lines.append("\n".join(body_parts))
        lines.append(")")

        return "\n".join(lines)

    def _emit_column(self, col: CanonicalColumn) -> str:
        if col.omit:
            comment = col.ddl_comment or f"-- AVISO: columna '{col.original_name}' omitida"
            return f"    {comment}"

        if col.auto_increment:
            serial = _serial_type(col.target_type) or "SERIAL"
            line = f"    {_dq(col.name)} {serial}"
            trailing: list[str] = []
            if col.comment:
                trailing.append(col.comment)
            if trailing:
                line += " -- " + " | ".join(trailing)
            return line

        parts = [f"    {_dq(col.name)}", col.target_type]
        parts.append("NOT NULL" if not col.nullable else "NULL")

        if col.default is not None:
            default_val = _format_default_postgresql(col.default)
            parts.append(f"DEFAULT {default_val}")

        line = " ".join(parts)

        trailing_items: list[str] = []
        if col.comment:
            trailing_items.append(col.comment)
        if col.ddl_comment:
            aviso = col.ddl_comment.lstrip("- ").strip()
            if aviso:
                trailing_items.append(aviso)

        if trailing_items:
            line += " -- " + " | ".join(trailing_items)

        return line

    def _emit_fk_inline(self, fk: CanonicalFK) -> str:
        cols = ", ".join(_dq(c) for c in fk.columns)
        ref_cols = ", ".join(_dq(c) for c in fk.ref_columns)
        stmt = (
            f"    CONSTRAINT {_dq(fk.name)} FOREIGN KEY ({cols}) "
            f"REFERENCES {_dq(fk.ref_table)} ({ref_cols})"
        )
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

    # Valores numéricos
    try:
        float(v)
        return v
    except ValueError:
        pass

    # String literal
    escaped = v.replace("'", "''")
    return f"'{escaped}'"


__all__: list[str] = ["PostgreSQLDDLEmitter"]
