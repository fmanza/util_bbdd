"""Introspección de schemas y tablas en SQL Server."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# SQL para migrate/extractors — queries de extracción de esquema SQL Server
# Parámetros estilo %(name)s (DB-API 2.0 / pymssql).
# ---------------------------------------------------------------------------


# ─── migrate/extractors: una consulta por schema y tipo de objeto (D1, 0.21.0) ─────────────
# La primera columna es siempre el nombre de la tabla, vista o rutina; el resto, en el mismo orden que leen los
# extractores. 200 tablas: 823 consultas (20 s en el banco, ~24 ms cada una) → 8 (0,26 s).


def fetch_pk_details_for_schema_sql() -> str:
    """SQL de las PK de todas las tablas de un schema SQL Server, una fila por columna (uso: comparar).

    Lo mismo que ``MSDialect.get_pk_constraint`` tabla a tabla (columnas en el orden de la clave, nombre y si es
    clustered), en una consulta.

    Parámetro: ``:schema`` (estilo de ``sqlalchemy.text``).

    Returns:
        str: SQL query para (TABLE_NAME, PK_NAME, COLUMN_NAME, IS_CLUSTERED), ordenado por tabla y posición en la clave.
    """
    return (
        "SELECT t.name AS TABLE_NAME, kc.name AS PK_NAME, c.name AS COLUMN_NAME, "
        "CASE WHEN i.type = 1 THEN 1 ELSE 0 END AS IS_CLUSTERED "
        "FROM sys.key_constraints kc "
        "JOIN sys.tables t ON t.object_id = kc.parent_object_id "
        "JOIN sys.indexes i ON i.object_id = kc.parent_object_id AND i.index_id = kc.unique_index_id "
        "JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id "
        "JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id "
        "WHERE kc.type = 'PK' AND t.schema_id = SCHEMA_ID(:schema) "
        "ORDER BY t.name, ic.key_ordinal"
    )


def fetch_index_details_for_schema_sql() -> str:
    """SQL de los índices no PK de todas las tablas de un schema SQL Server (uso: comparar).

    Mismos índices que ``MSDialect.get_indexes`` (sin la PK ni el heap); sus columnas, con
    :func:`fetch_index_columns_for_schema_sql`.

    Parámetro: ``:schema`` (estilo de ``sqlalchemy.text``).

    Returns:
        str: SQL query para (TABLE_NAME, INDEX_ID, INDEX_NAME, IS_UNIQUE, INDEX_TYPE, FILTER_DEFINITION), ordenado por
        tabla y nombre de índice.
    """
    return (
        "SELECT tab.name AS TABLE_NAME, ind.index_id AS INDEX_ID, ind.name AS INDEX_NAME, "
        "ind.is_unique AS IS_UNIQUE, ind.type AS INDEX_TYPE, ind.filter_definition AS FILTER_DEFINITION "
        "FROM sys.indexes ind "
        "JOIN sys.tables tab ON tab.object_id = ind.object_id "
        "WHERE tab.schema_id = SCHEMA_ID(:schema) AND ind.is_primary_key = 0 AND ind.type != 0 "
        "ORDER BY tab.name, ind.name"
    )


def fetch_index_columns_for_schema_sql() -> str:
    """SQL de las columnas de los índices de todas las tablas de un schema SQL Server (uso: comparar).

    Parámetro: ``:schema`` (estilo de ``sqlalchemy.text``).

    Returns:
        str: SQL query para (TABLE_NAME, INDEX_ID, COLUMN_NAME, IS_INCLUDED_COLUMN), ordenado por tabla, índice y
        posición en la clave.
    """
    return (
        "SELECT tab.name AS TABLE_NAME, ic.index_id AS INDEX_ID, col.name AS COLUMN_NAME, "
        "ic.is_included_column AS IS_INCLUDED_COLUMN "
        "FROM sys.index_columns ic "
        "JOIN sys.tables tab ON tab.object_id = ic.object_id "
        "JOIN sys.columns col ON col.object_id = ic.object_id AND col.column_id = ic.column_id "
        "WHERE tab.schema_id = SCHEMA_ID(:schema) "
        "ORDER BY tab.name, ic.index_id, ic.key_ordinal"
    )


def fetch_table_comments_for_schema_sql() -> str:
    """SQL de los comentarios (``MS_Description``) de las tablas de un schema SQL Server (uso: comparar).

    Parámetro: ``:schema`` (estilo de ``sqlalchemy.text``).

    Returns:
        str: SQL query para (TABLE_NAME, TABLE_COMMENT); solo las tablas con comentario.
    """
    return (
        "SELECT t.name AS TABLE_NAME, CAST(ep.value AS NVARCHAR(MAX)) AS TABLE_COMMENT "
        "FROM sys.tables t "
        "JOIN sys.extended_properties ep "
        "  ON ep.class = 1 AND ep.major_id = t.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description' "
        "WHERE t.schema_id = SCHEMA_ID(:schema)"
    )
