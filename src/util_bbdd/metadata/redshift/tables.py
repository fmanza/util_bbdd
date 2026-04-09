"""Introspección de schemas y tablas en Redshift."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import (
    build_redshift_columns_query,
    build_redshift_schemas_query,
    build_redshift_tables_query,
)
from .common import is_system_schema_redshift, normalize_redshift_type


def fetch_schemas_sync(connection: Any) -> list[tuple]:
    """Obtiene lista de schemas en Redshift via pg_catalog.

    Excluye schemas de sistema (pg_*, information_schema).

    Args:
        connection: Conexión a Redshift (psycopg2/asyncpg)

    Returns:
        list[tuple]: Filas (schema_name,)
    """
    sql = build_redshift_schemas_query()

    cursor = connection.execute(sql)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    return [(str(r[0]).strip(),) if r else ("",) for r in rows if r and not is_system_schema_redshift(r[0])]


def fetch_tables_sync(connection: Any, schema: str | None = None) -> list[tuple]:
    """Obtiene lista de tablas en un schema Redshift.

    Args:
        connection: Conexión a Redshift
        schema: Nombre del schema

    Returns:
        list[tuple]: Filas (table_name, table_type, table_comment)
    """
    if not schema or is_system_schema_redshift(schema):
        return []

    sql = build_redshift_tables_query()
    params = {"schema_name": schema}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    return [
        (str(r[0]), str(r[1]) if len(r) > 1 else "TABLE", str(r[2]) if len(r) > 2 and r[2] else "") for r in rows if r
    ]


def fetch_columns_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene columnas de una tabla en Redshift.

    Normaliza tipos Redshift (subconjunto PostgreSQL) a tipos genéricos.

    Args:
        connection: Conexión a Redshift
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (column_name, column_type, is_nullable,
                           ordinal_position, column_default, column_comment)
    """
    if not schema or not table or is_system_schema_redshift(schema):
        return []

    sql = build_redshift_columns_query()
    params = {"schema_name": schema, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 6:
            continue

        column_name = str(row[0]).strip()
        column_type = str(row[1]).strip() if row[1] else "varchar"
        is_nullable = 1 if (str(row[2]).strip().upper() == "YES" if row[2] else True) else 0
        ordinal_position = int(row[3]) if row[3] is not None else 0
        column_default = str(row[4]) if row[4] else None
        column_comment = str(row[5]).strip() if row[5] else ""

        # Normalizar tipo
        normalized_type = normalize_redshift_type(column_type)

        result.append((column_name, normalized_type, is_nullable, ordinal_position, column_default, column_comment))

    return sorted(result, key=lambda x: x[3])  # Ordenar por ordinal_position
