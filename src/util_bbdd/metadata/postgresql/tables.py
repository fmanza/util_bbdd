"""Helpers puros para metadata y DDL de tablas PostgreSQL."""

from __future__ import annotations

from typing import Any

from ...results import Rows
from .common import quote_pg_identifier


def fetch_schemas_sql() -> str:
    """SQL query para obtener esquemas (schemas) PostgreSQL."""
    return (
        "SELECT schema_name "
        "FROM information_schema.schemata "
        "WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'pg_temp_1') "
        "ORDER BY schema_name"
    )


def fetch_tables_sql(schema: str | None = None) -> str:
    """SQL query para obtener tablas de un esquema PostgreSQL.

    Args:
        schema: Nombre del esquema. Si None, usa public.

    Returns:
        str: SQL query para table_name, table_type, table_comment
    """
    return (
        "SELECT "
        "t.table_name, "
        "t.table_type, "
        "COALESCE(d.description, '') AS table_comment "
        "FROM information_schema.tables t "
        "LEFT JOIN pg_description d "
        "  ON d.objoid = (SELECT oid FROM pg_class WHERE relname = t.table_name AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = %(schema)s)) "
        "  AND d.objsubid = 0 "
        "WHERE t.table_schema = %(schema)s "
        "ORDER BY t.table_name"
    )


def fetch_columns_sql(schema: str, table: str) -> str:
    """SQL query para obtener columnas de una tabla PostgreSQL.

    Args:
        schema: Nombre del esquema
        table: Nombre de la tabla

    Returns:
        str: SQL query para (column_name, column_type, is_nullable, column_key, column_default, extra, column_comment)
    """
    return (
        "SELECT "
        "c.column_name, "
        "c.data_type, "
        "CASE WHEN c.is_nullable = 'YES' THEN 'YES' ELSE 'NO' END AS is_nullable, "
        "CASE WHEN tc.constraint_type = 'PRIMARY KEY' THEN 'PRI' "
        "      WHEN tc.constraint_type = 'UNIQUE' THEN 'UNI' "
        "      ELSE '' END AS column_key, "
        "c.column_default, "
        "CASE WHEN a.attgenerated != '' THEN 'GENERATED' ELSE '' END AS extra, "
        "COALESCE(d.description, '') AS column_comment "
        "FROM information_schema.columns c "
        "LEFT JOIN information_schema.table_constraints tc "
        "  ON tc.table_schema = c.table_schema "
        "  AND tc.table_name = c.table_name "
        "  AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE') "
        "LEFT JOIN information_schema.key_column_usage kcu "
        "  ON kcu.constraint_name = tc.constraint_name "
        "  AND kcu.table_schema = tc.table_schema "
        "  AND kcu.table_name = tc.table_name "
        "  AND kcu.column_name = c.column_name "
        "LEFT JOIN pg_description d "
        "  ON d.objoid = (SELECT oid FROM pg_class WHERE relname = %(table)s AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = %(schema)s)) "
        "  AND d.objsubid = c.ordinal_position "
        "LEFT JOIN pg_attribute a "
        "  ON a.attname = c.column_name "
        "  AND a.attrelid = (SELECT oid FROM pg_class WHERE relname = %(table)s AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = %(schema)s)) "
        "WHERE c.table_schema = %(schema)s "
        "  AND c.table_name = %(table)s "
        "ORDER BY c.ordinal_position"
    )


def _normalize_postgres_column_row(row: Any) -> tuple[str, str, str, str, Any, str, str] | None:
    """Normaliza una fila individual de columna PostgreSQL.

    Args:
        row: Tupla/lista de datos de columna

    Returns:
        Tupla normalizada (column_name, column_type, is_nullable, column_key,
        column_default, extra, column_comment) o None si es inválida
    """
    if not isinstance(row, (tuple, list)) or len(row) < 7:
        return None

    return (
        str(row[0]) if row[0] else "",  # column_name
        str(row[1]) if row[1] else "text",  # column_type
        str(row[2]) if row[2] else "YES",  # is_nullable
        str(row[3]) if row[3] else "",  # column_key
        str(row[4]) if row[4] else None,  # column_default (puede ser None)
        str(row[5]) if row[5] else "",  # extra (GENERATED, etc)
        str(row[6]) if row[6] else "",  # column_comment
    )


def decode_postgres_column_rows(safe_rows: Rows) -> Rows:
    """Decodifica y normaliza filas de columnas PostgreSQL.

    Args:
        safe_rows: Filas del query fetch_columns_sql

    Returns:
        Rows normalizadas con estructura (column_name, column_type, is_nullable, column_key, column_default, extra, column_comment)
    """
    return [normalized for row in safe_rows if (normalized := _normalize_postgres_column_row(row)) is not None]


def fetch_pk_constraint_sql(schema: str, table: str) -> str:
    """SQL query para obtener columnas de clave primaria en PostgreSQL."""
    return (
        "SELECT a.attname AS column_name, a.attnum AS ordinal_position "
        "FROM pg_class t "
        "JOIN pg_namespace n ON t.relnamespace = n.oid "
        "JOIN pg_index i ON i.indrelid = t.oid "
        "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(i.indkey) "
        "WHERE i.indisprimary "
        "  AND n.nspname = %(schema)s "
        "  AND t.relname = %(table)s "
        "ORDER BY a.attnum"
    )


def fetch_fk_constraint_sql(schema: str, table: str) -> str:
    """SQL query para obtener claves foráneas en PostgreSQL."""
    return (
        "SELECT "
        "rc.constraint_name, "
        "kcu.column_name, "
        "ccu.table_schema AS referenced_table_schema, "
        "ccu.table_name AS referenced_table_name, "
        "ccu.column_name AS referenced_column_name, "
        "rc.delete_rule, "
        "rc.update_rule "
        "FROM information_schema.referential_constraints rc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON rc.constraint_name = kcu.constraint_name "
        "  AND rc.table_name = kcu.table_name "
        "  AND rc.table_schema = kcu.table_schema "
        "JOIN information_schema.constraint_column_usage ccu "
        "  ON rc.unique_constraint_name = ccu.constraint_name "
        "WHERE rc.table_schema = %(schema)s "
        "  AND rc.table_name = %(table)s "
        "ORDER BY rc.constraint_name, kcu.ordinal_position"
    )


def fetch_unique_constraint_sql(schema: str, table: str) -> str:
    """SQL query para obtener constraints UNIQUE en PostgreSQL."""
    return (
        "SELECT "
        "tc.constraint_name, "
        "kcu.column_name, "
        "kcu.ordinal_position "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON tc.constraint_name = kcu.constraint_name "
        "WHERE tc.table_schema = %(schema)s "
        "  AND tc.table_name = %(table)s "
        "  AND tc.constraint_type = 'UNIQUE' "
        "ORDER BY tc.constraint_name, kcu.ordinal_position"
    )


def fetch_indexes_sql(schema: str, table: str) -> str:
    """SQL query para obtener índices de una tabla PostgreSQL."""
    return (
        "SELECT "
        "indexname, "
        "indexdef, "
        "CASE WHEN ix.indisunique THEN 1 ELSE 0 END AS is_unique, "
        "CASE WHEN ix.indisprimary THEN 1 ELSE 0 END AS is_primary_key "
        "FROM pg_indexes pi "
        "LEFT JOIN pg_class c ON c.relname = pi.indexname "
        "LEFT JOIN pg_index ix ON ix.indexrelid = c.oid "
        "WHERE pi.schemaname = %(schema)s "
        "  AND pi.tablename = %(table)s "
        "ORDER BY pi.indexname"
    )


def build_schema_qualified_table_name(schema: str | None, table: str) -> str:
    """Construye nombre de tabla con schema en PostgreSQL.

    Args:
        schema: Nombre del schema o None para usar public
        table: Nombre de la tabla

    Returns:
        "schema.table" con quoting apropiado
    """
    schema_name = schema or "public"
    return f"{quote_pg_identifier(schema_name)}.{quote_pg_identifier(table)}"


def build_postgres_table_ddl(table: str, rows: list[Any], pk_rows: list[Any]) -> str:
    """Construye CREATE TABLE PostgreSQL desde filas de columnas y PK.

    Args:
        table: Nombre de la tabla
        rows: Filas de columnas del query (column_name, column_type, is_nullable, ...)
        pk_rows: Filas de PK (column_name, ordinal_position)

    Returns:
        str: SQL CREATE TABLE
    """
    if not rows:
        return ""

    column_defs: list[str] = [_build_postgres_column_definition(row) for row in rows if _is_valid_column_row(row)]
    if not column_defs:
        return ""

    pk_constraint: str = _build_postgres_pk_constraint(pk_rows)
    if pk_constraint:
        column_defs.append(pk_constraint)

    table_identifier: str = quote_pg_identifier(table)
    col_defs_str: str = ",\n".join(column_defs)
    return f"CREATE TABLE {table_identifier} (\n{col_defs_str}\n);"


def _is_valid_column_row(row: Any) -> bool:
    """Valida estructura básica de fila de columna."""
    return isinstance(row, (tuple, list)) and bool(row)


def _build_postgres_column_definition(row: Any) -> str:
    """Construye definición de columna PostgreSQL."""
    column_name: str = str(row[0]) if row else ""
    column_type: str = str(row[1]) if len(row) > 1 else "text"
    nullable_flag: str = str(row[2]).upper() if len(row) > 2 else "YES"
    nullable: str = "NOT NULL" if nullable_flag == "NO" else "NULL"

    parts: list[str] = [quote_pg_identifier(column_name), column_type, nullable]

    # Agregar DEFAULT si existe
    if len(row) > 4 and row[4] is not None:
        parts.append(f"DEFAULT {_format_postgres_default(row[4])}")

    # Agregar GENERATED si aplica
    if len(row) > 5 and row[5] and "GENERATED" in str(row[5]).upper():
        parts.append("GENERATED ALWAYS AS IDENTITY")

    return "  " + " ".join(parts)


def _build_postgres_pk_constraint(pk_rows: list[Any]) -> str:
    """Construye constraint PRIMARY KEY."""
    pk_columns: list[str] = [
        quote_pg_identifier(str(row[0])) for row in pk_rows if isinstance(row, (tuple, list)) and len(row) > 0
    ]
    if not pk_columns:
        return ""
    return f"  PRIMARY KEY ({', '.join(pk_columns)})"


def _format_postgres_default(default_value: Any) -> str:
    """Renderiza DEFAULT PostgreSQL."""
    raw = str(default_value).strip()

    # Valores especiales
    if raw.upper() in {"NULL", "CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME"}:
        return raw.upper()

    if raw.upper().startswith("NEXTVAL"):
        return raw

    # Intentar parsear como número
    try:
        float(raw)
        return raw
    except ValueError:
        pass

    # Es string: escapar
    escaped = raw.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


__all__: list[str] = [
    "fetch_schemas_sql",
    "fetch_tables_sql",
    "fetch_columns_sql",
    "fetch_pk_constraint_sql",
    "fetch_fk_constraint_sql",
    "fetch_unique_constraint_sql",
    "fetch_indexes_sql",
    "decode_postgres_column_rows",
    "build_schema_qualified_table_name",
    "build_postgres_table_ddl",
]
