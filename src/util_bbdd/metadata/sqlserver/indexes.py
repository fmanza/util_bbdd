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


def fetch_unique_nonclustered_index_columns_sql() -> str:
    """SQL con los índices NONCLUSTERED **únicos** habilitados de una tabla (PK, UNIQUE o unique index) y sus columnas.

    Para ``disable_indexes="all"`` (v3.3.0): se deshabilitan y reconstruyen; el clustered (la tabla) nunca.

    Parámetros: ``:tbl`` y ``:schema`` (``None`` = ``SCHEMA_NAME()``).

    Returns:
        str: SQL para (index_name, is_primary_key, is_unique_constraint, column_name), por índice y orden de clave.
    """
    return (
        "SELECT i.name, i.is_primary_key, i.is_unique_constraint, c.name FROM sys.indexes i "
        "JOIN sys.tables t ON t.object_id = i.object_id "
        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
        "JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id "
        "  AND ic.is_included_column = 0 "
        "JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id "
        "WHERE t.name = :tbl AND s.name = COALESCE(:schema, SCHEMA_NAME()) "
        "  AND i.type_desc = 'NONCLUSTERED' AND i.is_unique = 1 AND i.is_disabled = 0 AND i.name IS NOT NULL "
        "ORDER BY i.name, ic.key_ordinal"
    )


def fetch_inbound_foreign_keys_sql() -> str:
    """SQL con las FK que referencian un índice de la tabla: al deshabilitarlo, SQL Server las deshabilita (v3.3.0).

    ``ALTER INDEX … REBUILD`` no las reactiva: se hace con ``ALTER TABLE <hija> WITH CHECK CHECK CONSTRAINT``.

    Parámetros: ``:tbl`` y ``:schema`` (``None`` = ``SCHEMA_NAME()``).

    Returns:
        str: SQL para (index_name, child_schema, child_table, fk_name, is_disabled, is_not_trusted).
    """
    return (
        "SELECT i.name, SCHEMA_NAME(ct.schema_id), ct.name, fk.name, fk.is_disabled, fk.is_not_trusted "
        "FROM sys.foreign_keys fk "
        "JOIN sys.tables pt ON pt.object_id = fk.referenced_object_id "
        "JOIN sys.schemas ps ON ps.schema_id = pt.schema_id "
        "JOIN sys.indexes i ON i.object_id = fk.referenced_object_id AND i.index_id = fk.key_index_id "
        "JOIN sys.tables ct ON ct.object_id = fk.parent_object_id "
        "WHERE pt.name = :tbl AND ps.name = COALESCE(:schema, SCHEMA_NAME()) "
        "ORDER BY i.name, fk.name"
    )


def fetch_clustered_index_count_sql() -> str:
    """SQL que cuenta los índices clustered de una tabla (0 = heap).

    Lo usa ``BulkCrud.maintenance_scope``: solo deshabilita índices en tablas sin índice clustered.

    Parámetro: ``:tbl`` (nombre para ``OBJECT_ID``, con esquema si hace falta).

    Returns:
        str: SQL con una fila y un entero.
    """
    return "SELECT COUNT(*) FROM sys.indexes WHERE object_id = OBJECT_ID(:tbl) AND type = 1"
