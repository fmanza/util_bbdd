"""Introspección de schemas y tablas en MySQL."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import (
    build_mysql_columns_query,
    build_mysql_schemas_query,
    build_mysql_tables_query,
)
from .common import normalize_mysql_type


def fetch_schemas_sync(connection: Any) -> list[tuple]:
    """Obtiene lista de schemas en MySQL.

    Excluye schemas de sistema (mysql, information_schema, performance_schema, sys).

    Args:
        connection: Conexión a MySQL (pymysql, MySQLdb, mysql.connector, etc.)

    Returns:
        list[tuple]: Filas (schema_name,)
    """
    sql = build_mysql_schemas_query()

    cursor = connection.execute(sql)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    return [(str(r[0]).strip(),) if r else ("",) for r in rows if r]


def fetch_tables_sync(connection: Any, schema: str | None = None) -> list[tuple]:
    """Obtiene lista de tablas en un schema MySQL.

    Args:
        connection: Conexión a MySQL
        schema: Nombre del schema

    Returns:
        list[tuple]: Filas (table_name, table_type, table_comment)
    """
    if not schema:
        return []

    sql = build_mysql_tables_query()
    params = {"schema_name": schema}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    return [
        (str(r[0]), str(r[1]) if len(r) > 1 else "TABLE", str(r[2]) if len(r) > 2 and r[2] else "") for r in rows if r
    ]


def fetch_columns_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene columnas de una tabla.

    Detecta auto_increment via EXTRA field.

    Args:
        connection: Conexión a MySQL
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (column_name, column_type, is_nullable,
                           ordinal_position, column_default, column_comment)
    """
    if not schema or not table:
        return []

    sql = build_mysql_columns_query()
    params = {"schema_name": schema, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 7:
            continue

        column_name = str(row[0]).strip()
        column_type = str(row[1]).strip().upper() if row[1] else "VARCHAR"
        is_nullable = 1 if str(row[2]).strip().upper() == "YES" else 0
        ordinal_position = int(row[3]) if row[3] is not None else 0
        column_default = str(row[4]) if row[4] else None
        column_comment = str(row[5]).strip() if row[5] else ""
        extra = str(row[6]).strip().upper() if len(row) > 6 else ""

        # Normalizar tipo
        normalized_type = normalize_mysql_type(column_type)

        # Agregar auto_increment info al comment si aplica
        if "AUTO_INCREMENT" in extra:
            column_comment = f"Auto-increment. {column_comment}".strip()

        result.append((column_name, normalized_type, is_nullable, ordinal_position, column_default, column_comment))

    return result
