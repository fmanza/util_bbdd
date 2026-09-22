"""Introspección de routines (triggers, procedimientos) en SQLite.

SQLite no tiene procedimientos o funciones definidas por usuario.
Se incluyen triggers para completitud.
"""

from __future__ import annotations

from typing import Any

from .common import quote_sqlite_identifier


def fetch_triggers_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene triggers para una tabla en SQLite.

    Args:
        connection: Conexión sqlite3
        schema: Nombre del schema (mapeado a database en SQLite)
        table: Nombre de la tabla (opcional, filtra por tabla si se proporciona)

    Returns:
        list[tuple]: Filas (trigger_name, table_name, trigger_event, trigger_action)
    """
    schema_name = schema or "main"
    escaped_schema = quote_sqlite_identifier(schema_name)

    # Query sqlite_master para triggers
    if table:
        sql = f"""
            SELECT name, tbl_name, 'TRIGGER', ''
            FROM {escaped_schema}.sqlite_master
            WHERE type='trigger'
            AND tbl_name = :table_name
            ORDER BY name
        """
        cursor = connection.execute(sql, {"table_name": table})
    else:
        sql = f"""
            SELECT name, tbl_name, 'TRIGGER', ''
            FROM {escaped_schema}.sqlite_master
            WHERE type='trigger'
            ORDER BY name
        """
        cursor = connection.execute(sql)

    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 4:
            continue

        trigger_name = str(row[0]).strip()
        table_name = str(row[1]).strip() if row[1] else ""
        event = str(row[2]).strip()
        action = str(row[3]).strip() if row[3] else ""

        result.append((trigger_name, table_name, event, action))

    return result


def fetch_procedures_sync(connection: Any, schema: str | None = None) -> list[tuple]:
    """Retorna lista vacía (SQLite no tiene procedimientos).

    Args:
        connection: Conexión sqlite3
        schema: Nombre del schema (no usado)

    Returns:
        list[tuple]: Lista vacía
    """
    return []


def fetch_functions_sync(connection: Any, schema: str | None = None) -> list[tuple]:
    """Retorna lista vacía (SQLite no tiene funciones definidas por usuario).

    Args:
        connection: Conexión sqlite3
        schema: Nombre del schema (no usado)

    Returns:
        list[tuple]: Lista vacía
    """
    return []
