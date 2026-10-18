"""Introspección de índices en SQL Server."""

from __future__ import annotations


def fetch_secondary_nonunique_indexes_sql() -> str:
    """SQL con los índices NONCLUSTERED no únicos y habilitados de una tabla (sin PK ni UNIQUE constraint).

    Lo usan ``dump.IndexManager`` y ``BulkCrud.maintenance_scope`` para deshabilitarlos antes de la carga y reconstruirlos
    después; el índice clustered no se toca porque dejaría la tabla inaccesible.

    Parámetros: ``:tbl`` y ``:schema`` (``None`` = ``SCHEMA_NAME()``).

    Returns:
        str: SQL para (index_name).
    """
    return (
        "SELECT i.name FROM sys.indexes i "
        "JOIN sys.tables t ON t.object_id = i.object_id "
        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
        "WHERE t.name = :tbl "
        "  AND s.name = COALESCE(:schema, SCHEMA_NAME()) "
        "  AND i.type_desc = 'NONCLUSTERED' "
        "  AND i.is_primary_key = 0 "
        "  AND i.is_unique_constraint = 0 "
        "  AND i.is_unique = 0 "
        "  AND i.is_disabled = 0 "
        "  AND i.name IS NOT NULL"
    )


def fetch_clustered_index_count_sql() -> str:
    """SQL que cuenta los índices clustered de una tabla (0 = heap).

    Lo usa ``BulkCrud.maintenance_scope``: solo deshabilita índices en tablas sin índice clustered.

    Parámetro: ``:tbl`` (nombre para ``OBJECT_ID``, con esquema si hace falta).

    Returns:
        str: SQL con una fila y un entero.
    """
    return "SELECT COUNT(*) FROM sys.indexes WHERE object_id = OBJECT_ID(:tbl) AND type = 1"
