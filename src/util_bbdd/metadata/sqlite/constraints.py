"""Introspección de constraints (PRIMARY KEY, FOREIGN KEY) en SQLite."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import decode_pragma_fk_rows


def fetch_primary_keys_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene claves primarias de una tabla via PRAGMA table_info.

    SQLite no tiene tabla de constraints; PK se detecta en table_info con pk > 0.

    Args:
        connection: Conexión sqlite3
        schema: Nombre del schema (mapeado a database en SQLite)
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (constraint_name, column_name, ordinal_position)
    """
    if not table:
        return []

    schema_name = schema or "main"

    # PRAGMA table_info retorna columnas con pk > 0 si forman parte de PK
    sql = f"PRAGMA [{schema_name}].table_info([{table}])"

    cursor = connection.execute(sql)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    pk_rows: list[tuple] = []
    for row in rows:
        if not row or len(row) < 6:
            continue

        pk_position = int(row[5]) if row[5] is not None else 0

        if pk_position > 0:
            column_name = str(row[1]).strip()
            ordinal_position = pk_position
            constraint_name = f"pk_{table.lower()}"

            pk_rows.append((constraint_name, column_name, ordinal_position))

    return sorted(pk_rows, key=lambda x: x[2])  # Ordenar por ordinal_position


def fetch_foreign_keys_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene claves foráneas de una tabla via PRAGMA foreign_key_list.

    Nota: Requiere PRAGMA foreign_keys=ON activado en la conexión.

    Args:
        connection: Conexión sqlite3
        schema: Nombre del schema (mapeado a database en SQLite)
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (constraint_name, column_name, ref_table, ref_column,
                           on_delete_action, on_update_action, ordinal_position)
    """
    if not table:
        return []

    schema_name = schema or "main"

    # PRAGMA foreign_key_list retorna: (id, seq, table, from, to, on_delete, on_update, match)
    sql = f"PRAGMA [{schema_name}].foreign_key_list([{table}])"

    cursor = connection.execute(sql)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    # Decodificar usando helper
    decoded = decode_pragma_fk_rows(rows)

    return decoded
