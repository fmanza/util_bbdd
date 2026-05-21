"""Queries SQL parametrizadas para extracción de esquema MariaDB.

Estilo de parámetros: ``%(name)s`` (Python DB-API 2.0 para MySQL/MariaDB).
"""

from __future__ import annotations


def fetch_tables_sql() -> str:
    """SQL para obtener tablas BASE TABLE de un schema MariaDB.

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, TABLE_COMMENT).
    """
    return (
        "SELECT TABLE_NAME, TABLE_COMMENT "
        "FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_TYPE = 'BASE TABLE' "
        "ORDER BY TABLE_NAME"
    )


def fetch_columns_sql() -> str:
    """SQL para obtener columnas de una tabla MariaDB.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
             NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT,
             EXTRA, COLUMN_COMMENT, ORDINAL_POSITION).
    """
    return (
        "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
        "NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT, "
        "EXTRA, COLUMN_COMMENT, ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(table_name)s "
        "ORDER BY ORDINAL_POSITION"
    )


def fetch_pk_sql() -> str:
    """SQL para obtener columnas de clave primaria de una tabla MariaDB.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (COLUMN_NAME,) ordenado por ORDINAL_POSITION.
    """
    return (
        "SELECT COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(table_name)s "
        "AND CONSTRAINT_NAME = 'PRIMARY' "
        "ORDER BY ORDINAL_POSITION"
    )


def fetch_fk_sql() -> str:
    """SQL para obtener claves foráneas de una tabla MariaDB.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA,
             REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, ORDINAL_POSITION,
             DELETE_RULE, UPDATE_RULE).
    """
    return (
        "SELECT kcu.CONSTRAINT_NAME, kcu.COLUMN_NAME, "
        "kcu.REFERENCED_TABLE_SCHEMA, kcu.REFERENCED_TABLE_NAME, "
        "kcu.REFERENCED_COLUMN_NAME, kcu.ORDINAL_POSITION, "
        "rc.DELETE_RULE, rc.UPDATE_RULE "
        "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
        "JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
        "  ON rc.CONSTRAINT_SCHEMA = kcu.TABLE_SCHEMA "
        "  AND rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
        "WHERE kcu.TABLE_SCHEMA = %(schema)s AND kcu.TABLE_NAME = %(table_name)s "
        "AND kcu.REFERENCED_TABLE_NAME IS NOT NULL "
        "ORDER BY kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
    )


def fetch_indexes_sql() -> str:
    """SQL para obtener índices no-PK de una tabla MariaDB.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (INDEX_NAME, COLUMN_NAME, NON_UNIQUE, SEQ_IN_INDEX).
    """
    return (
        "SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE, SEQ_IN_INDEX "
        "FROM INFORMATION_SCHEMA.STATISTICS "
        "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(table_name)s "
        "AND INDEX_NAME <> 'PRIMARY' "
        "ORDER BY INDEX_NAME, SEQ_IN_INDEX"
    )


def fetch_views_sql() -> str:
    """SQL para obtener vistas de un schema MariaDB.

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
    """SQL para obtener columnas de una vista MariaDB.

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
