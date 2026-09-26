"""Introspección de índices en SQL Server."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import build_sqlserver_indexes_query


def fetch_indexes_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene índices de una tabla via sys.indexes.

    Args:
        connection: Conexión a SQL Server
        schema: Nombre del schema (por defecto 'dbo')
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (index_name, column_name, is_unique, ordinal_position, index_type)
    """
    if not table:
        return []

    schema_name = schema or "dbo"

    sql = build_sqlserver_indexes_query()
    params = {"schema_name": schema_name, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 5:
            continue

        index_name = str(row[0]).strip()
        column_name = str(row[1]).strip()
        is_unique = int(row[2]) if row[2] is not None else 0
        index_type = int(row[3]) if len(row) > 3 else 2  # 1=clustered, 2=nonclustered
        ordinal_position = int(row[4]) if len(row) > 4 else 0

        result.append((index_name, column_name, is_unique, ordinal_position, index_type))

    return result


def fetch_secondary_nonunique_indexes_sql() -> str:
    """SQL con los índices NONCLUSTERED no únicos y habilitados de una tabla (sin PK ni UNIQUE constraint).

    Lo usa ``dump.IndexManager`` para deshabilitarlos antes de la carga y reconstruirlos después; el índice clustered no
    se toca porque dejaría la tabla inaccesible.

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

    Lo usa ``BulkCrud.maintenance_scope``: ``ALTER INDEX ALL … DISABLE`` solo se aplica a tablas sin índice clustered.

    Parámetro: ``:tbl`` (nombre para ``OBJECT_ID``, con esquema si hace falta).

    Returns:
        str: SQL con una fila y un entero.
    """
    return "SELECT COUNT(*) FROM sys.indexes WHERE object_id = OBJECT_ID(:tbl) AND type = 1"
