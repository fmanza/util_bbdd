"""Queries SQL parametrizadas para extracción de esquema SQL Server.

Estilo de parámetros: ``%(name)s`` (Python DB-API 2.0 para pymssql).
Para pyodbc se necesita un manager wrapper que convierta ``%(name)s`` a ``?``.

Detección de IDENTITY: usa ``COLUMNPROPERTY(OBJECT_ID(...), col, 'IsIdentity')``
(compatible con SQL Server 2008+).
"""

from __future__ import annotations


def fetch_tables_sql() -> str:
    """SQL para obtener tablas BASE TABLE de un schema SQL Server.

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
    """SQL para obtener columnas de una tabla SQL Server.

    Detecta columnas IDENTITY via ``COLUMNPROPERTY`` (SQL Server 2008+).
    ``CHARACTER_MAXIMUM_LENGTH = -1`` indica el tipo MAX (nvarchar(max), etc.).

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
             NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT,
             IS_IDENTITY, ORDINAL_POSITION).
    """
    return (
        "SELECT c.COLUMN_NAME, c.DATA_TYPE, c.CHARACTER_MAXIMUM_LENGTH, "
        "c.NUMERIC_PRECISION, c.NUMERIC_SCALE, c.IS_NULLABLE, c.COLUMN_DEFAULT, "
        "COLUMNPROPERTY(OBJECT_ID(c.TABLE_SCHEMA + '.' + c.TABLE_NAME), c.COLUMN_NAME, 'IsIdentity') AS IS_IDENTITY, "
        "c.ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.COLUMNS c "
        "WHERE c.TABLE_SCHEMA = %(schema)s AND c.TABLE_NAME = %(table_name)s "
        "ORDER BY c.ORDINAL_POSITION"
    )


def fetch_pk_sql() -> str:
    """SQL para obtener columnas de clave primaria de una tabla SQL Server.

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
    """SQL para obtener claves foráneas de una tabla SQL Server.

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
        "  AND kcu.TABLE_SCHEMA = rc.CONSTRAINT_SCHEMA "
        "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2 "
        "  ON kcu2.CONSTRAINT_NAME = rc.UNIQUE_CONSTRAINT_NAME "
        "  AND kcu2.TABLE_SCHEMA = rc.UNIQUE_CONSTRAINT_SCHEMA "
        "  AND kcu2.ORDINAL_POSITION = kcu.ORDINAL_POSITION "
        "WHERE kcu.TABLE_SCHEMA = %(schema)s AND kcu.TABLE_NAME = %(table_name)s "
        "ORDER BY kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
    )


def fetch_indexes_sql() -> str:
    """SQL para obtener índices no-PK de una tabla SQL Server via sys.*.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (INDEX_NAME, COLUMN_NAME, is_unique, SEQ_IN_INDEX).
    """
    return (
        "SELECT i.name AS INDEX_NAME, c.name AS COLUMN_NAME, i.is_unique, "
        "ic.key_ordinal AS SEQ_IN_INDEX "
        "FROM sys.indexes i "
        "JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id "
        "JOIN sys.columns c ON c.object_id = i.object_id AND c.column_id = ic.column_id "
        "JOIN sys.tables t ON t.object_id = i.object_id "
        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
        "WHERE s.name = %(schema)s AND t.name = %(table_name)s "
        "  AND i.is_primary_key = 0 AND i.type > 0 "
        "ORDER BY i.name, ic.key_ordinal"
    )


def fetch_views_sql() -> str:
    """SQL para obtener vistas de un schema SQL Server.

    ``VIEW_DEFINITION`` puede estar truncado a 4000 chars en versiones anteriores
    a SQL Server 2019 si la definición supera ese límite.

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
    """SQL para obtener columnas de una vista SQL Server.

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
