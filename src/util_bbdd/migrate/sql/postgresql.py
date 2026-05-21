"""Queries SQL parametrizadas para extracción de esquema PostgreSQL.

Estilo de parámetros: ``%(name)s`` (Python DB-API 2.0 para psycopg2/psycopg3).
"""

from __future__ import annotations


def fetch_tables_sql() -> str:
    """SQL para obtener tablas BASE TABLE de un schema PostgreSQL.

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


def fetch_columns_sql() -> str:
    """SQL para obtener columnas de una tabla PostgreSQL.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
             NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT,
             ORDINAL_POSITION).
    """
    return (
        "SELECT c.COLUMN_NAME, c.DATA_TYPE, c.CHARACTER_MAXIMUM_LENGTH, "
        "c.NUMERIC_PRECISION, c.NUMERIC_SCALE, c.IS_NULLABLE, c.COLUMN_DEFAULT, "
        "c.ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.COLUMNS c "
        "WHERE c.TABLE_SCHEMA = %(schema)s AND c.TABLE_NAME = %(table_name)s "
        "ORDER BY c.ORDINAL_POSITION"
    )


def fetch_pk_sql() -> str:
    """SQL para obtener columnas de clave primaria de una tabla PostgreSQL.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (COLUMN_NAME,) ordenado por ORDINAL_POSITION.
    """
    return (
        "SELECT kcu.COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
        "JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
        "  ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
        "  AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA "
        "WHERE kcu.TABLE_SCHEMA = %(schema)s AND kcu.TABLE_NAME = %(table_name)s "
        "  AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY' "
        "ORDER BY kcu.ORDINAL_POSITION"
    )


def fetch_fk_sql() -> str:
    """SQL para obtener claves foráneas de una tabla PostgreSQL.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (CONSTRAINT_NAME, COLUMN_NAME, REF_SCHEMA,
             REF_TABLE, REF_COLUMN, ORDINAL_POSITION, DELETE_RULE, UPDATE_RULE).
    """
    return (
        "SELECT kcu.CONSTRAINT_NAME, kcu.COLUMN_NAME, "
        "kcu2.TABLE_SCHEMA AS REF_SCHEMA, kcu2.TABLE_NAME AS REF_TABLE, "
        "kcu2.COLUMN_NAME AS REF_COLUMN, kcu.ORDINAL_POSITION, "
        "rc.DELETE_RULE, rc.UPDATE_RULE "
        "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
        "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
        "  ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME "
        "  AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA "
        "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2 "
        "  ON kcu2.CONSTRAINT_NAME = rc.UNIQUE_CONSTRAINT_NAME "
        "  AND kcu2.CONSTRAINT_SCHEMA = rc.UNIQUE_CONSTRAINT_SCHEMA "
        "  AND kcu2.ORDINAL_POSITION = kcu.POSITION_IN_UNIQUE_CONSTRAINT "
        "WHERE kcu.TABLE_SCHEMA = %(schema)s AND kcu.TABLE_NAME = %(table_name)s "
        "ORDER BY kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
    )


def fetch_indexes_sql() -> str:
    """SQL para obtener índices no-PK de una tabla PostgreSQL via pg_catalog.

    Usa ``generate_subscripts(ix.indkey, 1)`` para preservar el orden de columnas
    en índices compuestos (PG 8.4+).

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (index_name, column_name, is_unique, seq_in_index).
    """
    return (
        "SELECT i.relname AS index_name, "
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
        "WHERE n.nspname = %(schema)s AND c.relname = %(table_name)s "
        "  AND ix.indisprimary = false AND ix.indisvalid = true "
        "  AND a.attnum > 0 "
        "ORDER BY i.relname, gs"
    )


def fetch_views_sql() -> str:
    """SQL para obtener vistas de un schema PostgreSQL.

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


def fetch_view_columns_sql() -> str:
    """SQL para obtener columnas de una vista PostgreSQL.

    Parámetros: ``%(schema)s``, ``%(view_name)s``.

    Returns:
        str: SQL query para (COLUMN_NAME,) ordenado por ORDINAL_POSITION.
    """
    return (
        "SELECT COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(view_name)s "
        "ORDER BY ORDINAL_POSITION"
    )


__all__: list[str] = [
    "fetch_tables_sql",
    "fetch_columns_sql",
    "fetch_pk_sql",
    "fetch_fk_sql",
    "fetch_indexes_sql",
    "fetch_views_sql",
    "fetch_view_columns_sql",
]
