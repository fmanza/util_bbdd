"""Introspección de schemas y tablas en Snowflake."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import (
    build_snowflake_columns_query,
    build_snowflake_schemas_query,
    build_snowflake_tables_query,
)
from .common import is_system_schema_snowflake, normalize_snowflake_identifier, normalize_snowflake_type


def _normalize_snowflake_column_row(row: Any) -> tuple[str, str, bool, int, str, str] | None:
    """Normaliza una fila individual de columna Snowflake.

    Args:
        row: Tupla de 6+ elementos de INFORMATION_SCHEMA.COLUMNS

    Returns:
        Tupla (column_name, column_type, is_nullable, ordinal_position, column_default, column_comment)
        o None si es inválida
    """
    if not row:
        return None

    column_name = normalize_snowflake_identifier(row[0]) if row[0] else ""
    raw_type = str(row[1]).strip() if len(row) > 1 and row[1] else "object"
    column_type = normalize_snowflake_type(raw_type)
    is_nullable = str(row[2]).upper() == "YES" if len(row) > 2 else True
    ordinal_position = int(row[3]) if len(row) > 3 and row[3] is not None else 0
    column_default = str(row[4]).strip() if len(row) > 4 and row[4] else ""
    column_comment = str(row[5]).strip() if len(row) > 5 and row[5] else ""

    return (column_name, column_type, is_nullable, ordinal_position, column_default, column_comment)


def fetch_schemas_sync(connection: Any, database: str | None = None) -> list[tuple]:
    """Obtiene lista de schemas en Snowflake via INFORMATION_SCHEMA.SCHEMATA.

    Excluye schemas de sistema (INFORMATION_SCHEMA, SNOWFLAKE).

    Args:
        connection: Conexión a Snowflake (snowflake-connector-python)
        database: Nombre de la base de datos (database, no schema)

    Returns:
        list[tuple]: Filas (schema_name,)
    """
    if not database or not connection:
        return []

    sql = build_snowflake_schemas_query()
    params = {"database_name": database}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for r in rows:
        if r and not is_system_schema_snowflake(r[0]):
            # Normalizar schema name a UPPERCASE (Snowflake default)
            schema_name = normalize_snowflake_identifier(r[0])
            result.append((schema_name,))

    return result


def fetch_tables_sync(connection: Any, database: str | None = None, schema: str | None = None) -> list[tuple]:
    """Obtiene lista de tablas en un schema Snowflake.

    Maneja multi-nivel: DATABASE.SCHEMA.TABLE.

    Args:
        connection: Conexión a Snowflake
        database: Nombre de la base de datos
        schema: Nombre del schema

    Returns:
        list[tuple]: Filas (table_name, table_type, table_comment)
    """
    if not database or not schema or is_system_schema_snowflake(schema):
        return []

    sql = build_snowflake_tables_query()
    params = {"database_name": database, "schema_name": schema}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for r in rows:
        if r:
            table_name = normalize_snowflake_identifier(r[0]) if r[0] else ""
            table_type = str(r[1]).strip() if len(r) > 1 else "TABLE"
            table_comment = str(r[2]).strip() if len(r) > 2 and r[2] else ""
            result.append((table_name, table_type, table_comment))

    return result


def fetch_columns_sync(
    connection: Any, database: str | None = None, schema: str | None = None, table: str | None = None
) -> list[tuple]:
    """Obtiene columnas de una tabla en Snowflake.

    Normaliza tipos Snowflake a tipos genéricos.
    Maneja multi-nivel: DATABASE.SCHEMA.TABLE.

    Args:
        connection: Conexión a Snowflake
        database: Nombre de la base de datos
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (column_name, column_type, is_nullable,
                           ordinal_position, column_default, column_comment)
    """
    if not database or not schema or not table or is_system_schema_snowflake(schema):
        return []

    sql = build_snowflake_columns_query()
    params = {"database_name": database, "schema_name": schema, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result = [normalized for row in rows if (normalized := _normalize_snowflake_column_row(row)) is not None]
    return sorted(result, key=lambda x: x[3])  # Ordenar por ordinal_position
