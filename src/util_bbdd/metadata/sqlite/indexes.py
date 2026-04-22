"""Introspección de índices en SQLite."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import build_pragma_index_info_query


def _process_sqlite_index_columns(
    connection: Any, schema_name: str, index_name: str, is_unique: int
) -> list[tuple[str, str, int, int]]:
    """Procesa columnas de un índice SQLite.

    Args:
        connection: Conexión sqlite3
        schema_name: Schema name
        index_name: Nombre del índice
        is_unique: Flag de unicidad

    Returns:
        list[tuple]: Filas (index_name, column_name, is_unique, ordinal_position)
    """
    sql_info = build_pragma_index_info_query(index_name)
    cursor_info = connection.execute(sql_info)
    column_rows: list[tuple[Any, ...]] = cursor_info.fetchall()

    return [
        (index_name, str(col_row[2]).strip(), is_unique, int(col_row[0]) + 1 if col_row[0] is not None else seq + 1)
        for seq, col_row in enumerate(column_rows)
        if col_row and len(col_row) >= 3
    ]


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

        # Procesar columnas del índice
        index_columns = _process_sqlite_index_columns(connection, schema_name, index_name, is_unique)
        result.extend(index_columns)

    return result
