"""Introspección de índices en SQLite."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import build_pragma_index_info_query


def fetch_indexes_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene índices de una tabla via PRAGMA index_list e index_info.

    Args:
        connection: Conexión sqlite3
        schema: Nombre del schema (mapeado a database en SQLite)
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (index_name, column_name, is_unique, ordinal_position)
    """
    if not table:
        return []

    schema_name = schema or "main"

    # PRAGMA index_list retorna: (seq, name, unique, origin, partial)
    sql_list = f"PRAGMA [{schema_name}].index_list([{table}])"

    cursor = connection.execute(sql_list)
    index_rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for index_row in index_rows:
        if not index_row or len(index_row) < 5:
            continue

        index_name = str(index_row[1]).strip()
        is_unique = int(index_row[2]) if index_row[2] is not None else 0

        # Evitar índices del sistema
        if index_name.startswith("sqlite_"):
            continue

        # PRAGMA index_info retorna: (seqno, cid, name)
        sql_info = build_pragma_index_info_query(index_name)

        cursor_info = connection.execute(sql_info)
        column_rows: list[tuple[Any, ...]] = cursor_info.fetchall()

        for seq, col_row in enumerate(column_rows):
            if not col_row or len(col_row) < 3:
                continue

            column_name = str(col_row[2]).strip()
            ordinal_position = int(col_row[0]) + 1 if col_row[0] is not None else seq + 1

            result.append((index_name, column_name, is_unique, ordinal_position))

    return result
