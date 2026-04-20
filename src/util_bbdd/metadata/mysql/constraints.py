"""Introspección de constraints (PRIMARY KEY, FOREIGN KEY) en MySQL."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import build_mysql_fk_query, build_mysql_pk_query
from .common import decode_mysql_cascade_action


def _process_fk_row(row: tuple) -> tuple | None:
    """Procesa una fila de foreign key: validación y decodificación de acciones.

    Args:
        row: Tupla de la BD con (constraint_name, column_name, ref_table, ref_column,
                                 update_action, delete_action, ordinal_position)

    Returns:
        tuple: Fila procesada o None si la validación falla
    """
    if not row or len(row) < 7:
        return None

    constraint_name: str = str(row[0]).strip()
    column_name: str = str(row[1]).strip()
    ref_table: str = str(row[2]).strip() if row[2] else ""
    ref_column: str = str(row[3]).strip() if row[3] else ""
    update_action: str = str(row[4]).strip() if row[4] else "RESTRICT"
    delete_action: str = str(row[5]).strip() if row[5] else "RESTRICT"
    ordinal_position: int = int(row[6]) if row[6] is not None else 0

    on_delete_action: str = decode_mysql_cascade_action(delete_action)
    on_update_action: str = decode_mysql_cascade_action(update_action)

    return (
        constraint_name,
        column_name,
        ref_table,
        ref_column,
        on_delete_action,
        on_update_action,
        ordinal_position,
    )


def fetch_primary_keys_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene claves primarias de una tabla via information_schema.KEY_COLUMN_USAGE.

    Args:
        connection: Conexión a MySQL
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (constraint_name, column_name, ordinal_position)
    """
    if not schema or not table:
        return []

    sql: str = build_mysql_pk_query()
    params: dict[str, str] = {"schema_name": schema, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 3:
            continue

        constraint_name: str = str(row[0]).strip()
        column_name: str = str(row[1]).strip()
        ordinal_position: int = int(row[2]) if row[2] is not None else 0

        result.append((constraint_name, column_name, ordinal_position))

    return sorted(result, key=lambda x: x[2])  # Ordenar por ordinal_position


def fetch_foreign_keys_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene claves foráneas de una tabla via information_schema.REFERENTIAL_CONSTRAINTS.

    Decodifica acciones CASCADE/RESTRICT/SET NULL/NO ACTION/SET DEFAULT.

    Args:
        connection: Conexión a MySQL
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (constraint_name, column_name, ref_table, ref_column,
                           on_delete_action, on_update_action, ordinal_position)
    """
    if not schema or not table:
        return []

    sql: str = build_mysql_fk_query()
    params: dict[str, str] = {"schema_name": schema, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    return [processed for processed in (_process_fk_row(row) for row in rows) if processed is not None]
