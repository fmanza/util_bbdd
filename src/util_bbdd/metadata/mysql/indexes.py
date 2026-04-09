"""Introspección de índices en MySQL."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import build_mysql_indexes_query


def fetch_indexes_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene índices de una tabla via information_schema.STATISTICS.

    Excluye PRIMARY KEY (se obtiene por separado via constraints).

    Args:
        connection: Conexión a MySQL
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (index_name, column_name, seq_in_index, is_unique)
    """
    if not schema or not table:
        return []

    sql = build_mysql_indexes_query()
    params = {"schema_name": schema, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 4:
            continue

        index_name = str(row[0]).strip()
        column_name = str(row[1]).strip()
        seq_in_index = int(row[2]) if row[2] is not None else 0
        # MySQL NON_UNIQUE: 0=unique, 1=non-unique
        non_unique = int(row[3]) if row[3] is not None else 1
        is_unique = 1 if non_unique == 0 else 0

        result.append((index_name, column_name, seq_in_index, is_unique))

    return result
