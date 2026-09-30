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
    """SQL query para obtener columnas de clave primaria en PostgreSQL.

    Retorna (constraint_name, column_name, ordinal_position) — mismo contrato que Oracle/MariaDB.
    """
    return (
        "SELECT c.conname AS constraint_name, a.attname AS column_name, a.attnum AS ordinal_position "
        "FROM pg_class t "
        "JOIN pg_namespace n ON t.relnamespace = n.oid "
        "JOIN pg_index i ON i.indrelid = t.oid "
        "JOIN pg_constraint c ON c.conindid = i.indexrelid AND c.contype = 'p' "
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


# ---------------------------------------------------------------------------
# SQL para migrate/extractors — queries de extracción de esquema PostgreSQL
# (Opción P-A: aliases _for_extract para funciones con nombre conflictivo)
# Parámetros estilo %(name)s (DB-API 2.0 / psycopg2/psycopg3).
# ---------------------------------------------------------------------------


def fetch_tables_for_extract_sql() -> str:
    """SQL para obtener tablas BASE TABLE de un schema PostgreSQL (uso: migrate/extractors).

    Retorna solo TABLE_NAME filtrando por TABLE_TYPE='BASE TABLE'.
    Difiere de ``fetch_tables_sql`` que incluye vistas y retorna 3 columnas.

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME,).
    """
    return (
        "SELECT TABLE_NAME "
        "FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_TYPE = 'BASE TABLE' "
        "ORDER BY TABLE_NAME"
    )


# ─── migrate/extractors: una consulta por schema y tipo de objeto (D1, 0.21.0) ─────────────
# La primera columna es siempre el nombre de la tabla (o vista); el resto, en el mismo orden que leen los extractores.
# Filas ordenadas por tabla y, dentro de cada una, por el orden propio del objeto (posición, constraint, índice).
# PK y FK sobre pg_catalog: en INFORMATION_SCHEMA la consulta de FK de un schema de 200 tablas tarda ~1,4 s.

_FK_RULE_SQL: str = (
    "CASE {col} WHEN 'a' THEN 'NO ACTION' WHEN 'r' THEN 'RESTRICT' WHEN 'c' THEN 'CASCADE' "
    "WHEN 'n' THEN 'SET NULL' WHEN 'd' THEN 'SET DEFAULT' END"
)


def fetch_columns_for_schema_sql() -> str:
    """SQL de las columnas de todas las tablas y vistas de un schema PostgreSQL (uso: migrate/extractors).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION,
             NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT, ORDINAL_POSITION).
    """
    return (
        "SELECT c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.CHARACTER_MAXIMUM_LENGTH, "
        "c.NUMERIC_PRECISION, c.NUMERIC_SCALE, c.IS_NULLABLE, c.COLUMN_DEFAULT, "
        "c.ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.COLUMNS c "
        "WHERE c.TABLE_SCHEMA = %(schema)s "
        "ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION"
    )


def fetch_indexes_for_schema_sql() -> str:
    """SQL de los índices no-PK de todas las tablas de un schema PostgreSQL via pg_catalog (uso: migrate/extractors).

    Usa ``generate_subscripts(ix.indkey, 1)`` para preservar el orden de columnas en índices compuestos.

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (table_name, index_name, column_name, is_unique, seq_in_index).
    """
    return (
        "SELECT c.relname AS table_name, "
        "       i.relname AS index_name, "
        "       a.attname AS column_name, "
        "       ix.indisunique AS is_unique, "
        "       gs AS seq_in_index "
        "FROM pg_catalog.pg_class c "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_catalog.pg_index ix ON ix.indrelid = c.oid "
        "JOIN pg_catalog.pg_class i ON i.oid = ix.indexrelid "
        "JOIN generate_subscripts(ix.indkey, 1) AS gs ON true "
        "JOIN pg_catalog.pg_attribute a "
        "     ON a.attrelid = c.oid AND a.attnum = ix.indkey[gs] "
        "WHERE n.nspname = %(schema)s "
        "  AND ix.indisprimary = false AND ix.indisvalid = true "
        "  AND a.attnum > 0 "
        "ORDER BY c.relname, i.relname, gs"
    )


def fetch_pk_for_schema_sql() -> str:
    """SQL de las columnas de clave primaria de todas las tablas de un schema PostgreSQL (uso: migrate/extractors).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (table_name, column_name) en el orden de la clave.
    """
    return (
        "SELECT c.relname AS table_name, a.attname AS column_name "
        "FROM pg_catalog.pg_constraint con "
        "JOIN pg_catalog.pg_class c ON c.oid = con.conrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON true "
        "JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum "
        "WHERE n.nspname = %(schema)s AND con.contype = 'p' "
        "ORDER BY c.relname, k.ord"
    )


def fetch_fk_for_schema_sql() -> str:
    """SQL de las claves foráneas de todas las tablas de un schema PostgreSQL (uso: migrate/extractors).

    Las reglas ``ON DELETE``/``ON UPDATE`` se devuelven con los mismos textos que INFORMATION_SCHEMA.

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (table_name, CONSTRAINT_NAME, COLUMN_NAME, REF_SCHEMA, REF_TABLE, REF_COLUMN,
             ORDINAL_POSITION, DELETE_RULE, UPDATE_RULE).
    """
    return (
        "SELECT c.relname AS table_name, con.conname AS constraint_name, a.attname AS column_name, "
        "rn.nspname AS ref_schema, rc.relname AS ref_table, ra.attname AS ref_column, k.ord AS ordinal_position, "
        f"{_FK_RULE_SQL.format(col='con.confdeltype')} AS delete_rule, "
        f"{_FK_RULE_SQL.format(col='con.confupdtype')} AS update_rule "
        "FROM pg_catalog.pg_constraint con "
        "JOIN pg_catalog.pg_class c ON c.oid = con.conrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_catalog.pg_class rc ON rc.oid = con.confrelid "
        "JOIN pg_catalog.pg_namespace rn ON rn.oid = rc.relnamespace "
        "JOIN LATERAL unnest(con.conkey, con.confkey) WITH ORDINALITY AS k(attnum, refattnum, ord) ON true "
        "JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum "
        "JOIN pg_catalog.pg_attribute ra ON ra.attrelid = rc.oid AND ra.attnum = k.refattnum "
        "WHERE n.nspname = %(schema)s AND con.contype = 'f' "
        "ORDER BY c.relname, con.conname, k.ord"
    )


def fetch_views_sql() -> str:
    """SQL para obtener vistas de un schema PostgreSQL (uso: migrate/extractors).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, VIEW_DEFINITION).
    """
    return (
        "SELECT TABLE_NAME, VIEW_DEFINITION "
        "FROM INFORMATION_SCHEMA.VIEWS "
        "WHERE TABLE_SCHEMA = %(schema)s "
        "ORDER BY TABLE_NAME"
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


def fetch_can_disable_triggers_sql() -> str:
    """SQL que devuelve si el usuario actual puede ejecutar ``ALTER TABLE … DISABLE TRIGGER ALL`` en una tabla.

    Puede si es superusuario o propietario de la tabla. Lo usan ``BulkCrud.maintenance_scope`` y
    ``ParallelBulkLoader`` (desactivación previa al pool de workers) para no intentar un DDL que fallaría.

    Parámetros: ``:schema`` (``None`` = ``current_schema()``) y ``:tbl``.

    Returns:
        str: SQL con una fila y una columna booleana.
    """
    return (
        "SELECT current_setting('is_superuser') = 'on' "
        "OR EXISTS ("
        "  SELECT 1 FROM pg_tables "
        "  WHERE schemaname = COALESCE(:schema, current_schema()) "
        "  AND tablename = :tbl AND tableowner = current_user"
        ")"
    )


def fetch_secondary_nonunique_indexes_sql() -> str:
    """SQL con los índices secundarios no únicos de una tabla y su DDL (``pg_get_indexdef``).

    Excluye los de PK, los únicos y los que respaldan una constraint. Lo usa ``dump.IndexManager`` para eliminarlos antes
    de la carga y recrearlos después con el DDL guardado.

    Parámetros: ``:tbl`` y ``:schema`` (``None`` = ``current_schema()``).

    Returns:
        str: SQL para (index_name, ddl).
    """
    return (
        "SELECT ic.relname AS index_name, pg_get_indexdef(i.indexrelid) AS ddl "
        "FROM pg_index i "
        "JOIN pg_class ic ON ic.oid = i.indexrelid "
        "JOIN pg_class tc ON tc.oid = i.indrelid "
        "JOIN pg_namespace n ON n.oid = tc.relnamespace "
        "WHERE tc.relname = :tbl "
        "  AND n.nspname = COALESCE(:schema, current_schema()) "
        "  AND NOT i.indisprimary AND NOT i.indisunique "
        "  AND NOT EXISTS (SELECT 1 FROM pg_constraint con WHERE con.conindid = i.indexrelid)"
    )


def fetch_fk_definition_sql() -> str:
    """SQL con la definición de una FK desde el catálogo: tabla referenciada y columnas de la hija y de la referenciada.

    La tabla referenciada sale como ``regclass`` (ya citada y con esquema si hace falta) y las columnas citadas con
    ``quote_ident``, en el orden de la constraint. Lo usa ``dump.ConstraintManager`` para buscar filas huérfanas tras
    reactivar los triggers (PD-04).

    Parámetros: ``:tbl`` (nombre de tabla citado, convertible a ``regclass``) y ``:name`` (nombre de la FK).

    Returns:
        str: SQL para (tabla_referenciada, columnas_hija[], columnas_referenciadas[]).
    """
    return """
        SELECT c.confrelid::regclass::text,
          (SELECT array_agg(quote_ident(a.attname) ORDER BY k.ord)
             FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum),
          (SELECT array_agg(quote_ident(a.attname) ORDER BY k.ord)
             FROM unnest(c.confkey) WITH ORDINALITY AS k(attnum, ord)
             JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.attnum)
        FROM pg_constraint c
        WHERE c.conrelid = CAST(:tbl AS regclass) AND c.conname = :name AND c.contype = 'f'
    """


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
    "fetch_can_disable_triggers_sql",
    "fetch_secondary_nonunique_indexes_sql",
    "fetch_fk_definition_sql",
]
