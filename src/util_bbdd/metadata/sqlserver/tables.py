"""Introspección de schemas y tablas en SQL Server."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import (
    build_sqlserver_columns_query,
    build_sqlserver_schemas_query,
    build_sqlserver_tables_query,
)
from .common import normalize_sqlserver_type


def fetch_schemas_sync(connection: Any) -> list[tuple]:
    """Obtiene lista de schemas en SQL Server.

    Excluye schemas de sistema (sys, INFORMATION_SCHEMA, etc.)

    Args:
        connection: Conexión a SQL Server (pyodbc)

    Returns:
        list[tuple]: Filas (schema_name,)
    """
    sql = build_sqlserver_schemas_query()

    cursor = connection.execute(sql)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    return [(str(r[0]).strip(),) if r else ("",) for r in rows if r]


def fetch_tables_sync(connection: Any, schema: str | None = None) -> list[tuple]:
    """Obtiene lista de tablas en un schema SQL Server.

    Args:
        connection: Conexión a SQL Server
        schema: Nombre del schema (por defecto 'dbo')

    Returns:
        list[tuple]: Filas (table_name, table_type, table_comment)
    """
    schema_name = schema or "dbo"

    sql = build_sqlserver_tables_query()
    params = {"schema_name": schema_name}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    return [(str(r[0]), str(r[1]) if len(r) > 1 else "TABLE", str(r[2]) if len(r) > 2 else "") for r in rows if r]


def fetch_columns_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene columnas de una tabla via sys.columns.

    Args:
        connection: Conexión a SQL Server
        schema: Nombre del schema (por defecto 'dbo')
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (column_name, column_type, is_nullable,
                           ordinal_position, column_default, column_comment, is_identity)
    """
    if not table:
        return []

    schema_name = schema or "dbo"

    sql = build_sqlserver_columns_query()
    params = {"schema_name": schema_name, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 7:
            continue

        column_name = str(row[0]).strip()
        column_type = str(row[1]).strip().upper() if row[1] else "SQL_VARIANT"
        is_nullable = int(row[2]) if row[2] is not None else 0
        ordinal_position = int(row[3]) if row[3] is not None else 0
        column_default = str(row[4]) if row[4] else None
        column_comment = str(row[5]).strip() if row[5] else ""
        is_identity = int(row[6]) if row[6] is not None else 0

        # Normalizar tipo
        normalized_type = normalize_sqlserver_type(column_type)

        # Agregar identity info al comment si aplica
        if is_identity:
            column_comment = f"Identity column. {column_comment}".strip()

        result.append((column_name, normalized_type, is_nullable, ordinal_position, column_default, column_comment))

    return result
