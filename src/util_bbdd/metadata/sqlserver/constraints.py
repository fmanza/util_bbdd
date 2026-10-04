"""Introspección de constraints (PRIMARY KEY, FOREIGN KEY) en SQL Server."""

from __future__ import annotations


def fetch_schema_fk_references_sql() -> str:
    """SQL con una fila por clave foránea de las tablas de un schema: ``(tabla, schema_referido, tabla_referida)``.

    Una sola consulta por schema, para quien necesita el grafo de dependencias FK de muchas tablas (``dump``: orden de
    carga y tablas referenciadas en la limpieza). El ``get_foreign_keys`` de SQLAlchemy para SQL Server hace una
    consulta por tabla sobre ``INFORMATION_SCHEMA`` que tarda ≈ 34 ms: 200 tablas × 3 llamadas eran 20,6 s de un
    volcado de 33,9 s (Q9, performance-audit de dump 2026-09-26).

    Parámetro: ``:schema`` (estilo de ``sqlalchemy.text``, válido con pymssql y pyodbc). Las FK deshabilitadas
    (``NOCHECK``) también se devuelven, igual que en ``Inspector.get_foreign_keys``.

    Returns:
        str: SQL query para (TABLE_NAME, REF_SCHEMA, REF_TABLE), ordenado por tabla y nombre de FK.
    """
    return (
        "SELECT t.name AS TABLE_NAME, SCHEMA_NAME(rt.schema_id) AS REF_SCHEMA, rt.name AS REF_TABLE "
        "FROM sys.foreign_keys fk "
        "JOIN sys.tables t ON t.object_id = fk.parent_object_id "
        "JOIN sys.tables rt ON rt.object_id = fk.referenced_object_id "
        "WHERE t.schema_id = SCHEMA_ID(:schema) "
        "ORDER BY t.name, fk.name"
    )


def fetch_schema_fk_details_sql() -> str:
    """SQL con una fila por columna de cada clave foránea de las tablas de un schema (uso: comparar).

    Lo que necesita ``SchemaComparator`` para comparar FKs de muchas tablas con una consulta en vez de un
    ``Inspector.get_foreign_keys`` por tabla (≈ 34 ms cada uno en SQL Server; ver
    :func:`fetch_schema_fk_references_sql`). Lee ``sys.foreign_keys``, como ``Inspector``, así que también devuelve
    las FK hacia índices únicos y las deshabilitadas (``NOCHECK``).

    Parámetro: ``:schema`` (estilo de ``sqlalchemy.text``, válido con pymssql y pyodbc).

    Returns:
        str: SQL query para (TABLE_NAME, FK_NAME, COLUMN_NAME, REF_SCHEMA, REF_TABLE, REF_COLUMN, DELETE_ACTION,
        UPDATE_ACTION), ordenado por tabla, FK y posición de la columna en la FK.
    """
    return (
        "SELECT t.name AS TABLE_NAME, fk.name AS FK_NAME, pc.name AS COLUMN_NAME, "
        "SCHEMA_NAME(rt.schema_id) AS REF_SCHEMA, rt.name AS REF_TABLE, rc.name AS REF_COLUMN, "
        "fk.delete_referential_action_desc AS DELETE_ACTION, fk.update_referential_action_desc AS UPDATE_ACTION "
        "FROM sys.foreign_keys fk "
        "JOIN sys.tables t ON t.object_id = fk.parent_object_id "
        "JOIN sys.tables rt ON rt.object_id = fk.referenced_object_id "
        "JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id "
        "JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id "
        "JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id "
        "WHERE t.schema_id = SCHEMA_ID(:schema) "
        "ORDER BY t.name, fk.name, fkc.constraint_column_id"
    )
