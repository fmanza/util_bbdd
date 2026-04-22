"""Introspección de schemas y tablas en SQLite."""

from __future__ import annotations

from typing import Any, Literal

from .common import normalize_sqlite_type


def _normalize_sqlite_column_row(row: Any) -> tuple[str, str, int, int, str | None, str] | None:
    """Normaliza una fila individual de columna SQLite.

    Args:
        row: Tupla de 6+ elementos de PRAGMA table_info

    Returns:
        Tupla (column_name, normalized_type, is_nullable, ordinal_position, column_default, comment)
        o None si es inválida
    """
    if not row or len(row) < 6:
        return None

    column_name: str = str(row[1]).strip()
    column_type: str = str(row[2]).strip().upper() if row[2] else "TEXT"
    notnull = int(row[3]) if row[3] is not None else 0
    ordinal_position: int = int(row[0]) + 1 if row[0] is not None else 0
    column_default: str | None = str(row[4]) if row[4] else None
    is_nullable: Literal[0] | Literal[1] = 0 if notnull else 1
    normalized_type: str = normalize_sqlite_type(column_type)

    return (column_name, normalized_type, is_nullable, ordinal_position, column_default, "")


def fetch_schemas_sync() -> list[tuple]:
    """Retorna lista de pseudoschemas en SQLite.

    SQLite no tiene schemas reales, pero soporta "main" y "temp",
    y bases de datos adjuntas via ATTACH DATABASE.

    Returns:
        list[tuple]: Filas (schema_name,)
    """
    # SQLite tiene "main" (por defecto) y "temp" (temporal)
    # No se incluyen schemas adjuntos para simplicidad en MVP
    return [("main",), ("temp",)]


def fetch_tables_sync(connection: Any, schema: str | None = None) -> list[tuple]:
    """Obtiene lista de tablas en un schema SQLite.

    Query contra sqlite_master con type='table'.

    Args:
        connection: Conexión sqlite3
        schema: Nombre del schema (mapeado a database en SQLite, por defecto "main")

    Returns:
        list[tuple]: Filas (table_name, table_type, table_comment)
    """
    schema_name = schema or "main"

    # SQLite no tiene comentarios; retornar vacío
    sql = f"""
        SELECT name, 'TABLE', '' as comments
        FROM [{schema_name}].sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """

    cursor = connection.execute(sql)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    return [(str(r[0]), str(r[1]), str(r[2])) for r in rows if r]


def fetch_columns_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene columnas de una tabla via PRAGMA table_info.

    Args:
        connection: Conexión sqlite3
        schema: Nombre del schema (mapeado a database en SQLite)
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (column_name, column_type, is_nullable,
                           ordinal_position, column_default, column_comment)
    """
    if not table:
        return []

    schema_name = schema or "main"

    # PRAGMA table_info retorna: (cid, name, type, notnull, dflt_value, pk)
    # Mapear a tupla estándar: (name, type, nullable, ordinal, default, comments)
    sql = f"PRAGMA [{schema_name}].table_info([{table}])"

    cursor = connection.execute(sql)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    return [normalized for row in rows if (normalized := _normalize_sqlite_column_row(row)) is not None]
