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
