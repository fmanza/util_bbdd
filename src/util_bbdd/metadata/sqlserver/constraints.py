"""Introspección de constraints (PRIMARY KEY, FOREIGN KEY) en SQL Server."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import (
    build_sqlserver_fk_query,
    build_sqlserver_pk_query,
)
from .common import decode_sqlserver_cascade_action


def fetch_primary_keys_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene claves primarias de una tabla via sys.key_constraints.

    Args:
        connection: Conexión a SQL Server
        schema: Nombre del schema (por defecto 'dbo')
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (constraint_name, column_name, ordinal_position)
    """
    if not table:
        return []

    schema_name = schema or "dbo"

    sql = build_sqlserver_pk_query()
    params = {"schema_name": schema_name, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 3:
            continue

        constraint_name = str(row[0]).strip()
        column_name = str(row[1]).strip()
        ordinal_position = int(row[2]) if row[2] is not None else 0

        result.append((constraint_name, column_name, ordinal_position))

    return sorted(result, key=lambda x: x[2])  # Ordenar por ordinal_position


def fetch_foreign_keys_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene claves foráneas de una tabla via sys.foreign_keys.

    Decodifica acciones CASCADE (0-4 map a CASCADE, SET NULL, etc.)

    Args:
        connection: Conexión a SQL Server
        schema: Nombre del schema (por defecto 'dbo')
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (constraint_name, column_name, ref_table, ref_column,
                           on_delete_action, on_update_action, ordinal_position)
    """
    if not table:
        return []

    schema_name = schema or "dbo"

    sql = build_sqlserver_fk_query()
    params = {"schema_name": schema_name, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 7:
            continue

        constraint_name = str(row[0]).strip()
        column_name = str(row[1]).strip()
        ref_table = str(row[2]).strip()
        ref_column = str(row[3]).strip()
        on_delete_code = int(row[4]) if row[4] is not None else 0
        on_update_code = int(row[5]) if row[5] is not None else 0
        ordinal_position = int(row[6]) if row[6] is not None else 0

        # Decodificar acciones
        on_delete_action = decode_sqlserver_cascade_action(on_delete_code)
        on_update_action = decode_sqlserver_cascade_action(on_update_code)

        result.append(
            (constraint_name, column_name, ref_table, ref_column, on_delete_action, on_update_action, ordinal_position)
        )

    return result
