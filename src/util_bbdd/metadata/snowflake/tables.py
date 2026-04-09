"""Introspección de schemas y tablas en Snowflake."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import (
    build_snowflake_columns_query,
    build_snowflake_schemas_query,
    build_snowflake_tables_query,
)
from .common import is_system_schema_snowflake, normalize_snowflake_identifier, normalize_snowflake_type


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

    result: list[tuple] = []
    for r in rows:
        if r:
            column_name = normalize_snowflake_identifier(r[0]) if r[0] else ""
            # Normalizar tipo a genérico
            raw_type = str(r[1]).strip() if len(r) > 1 and r[1] else "object"
            column_type = normalize_snowflake_type(raw_type)

            is_nullable = str(r[2]).upper() == "YES" if len(r) > 2 else True
            ordinal_position = int(r[3]) if len(r) > 3 and r[3] is not None else 0
            column_default = str(r[4]).strip() if len(r) > 4 and r[4] else ""
            column_comment = str(r[5]).strip() if len(r) > 5 and r[5] else ""

            result.append((column_name, column_type, is_nullable, ordinal_position, column_default, column_comment))

    return sorted(result, key=lambda x: x[3])  # Ordenar por ordinal_position
