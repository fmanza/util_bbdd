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


def _extract_column_fields(row: tuple[Any, ...]) -> tuple[str, str, int, int, str | None, str, str]:
    """Extrae y normaliza campos básicos de una fila de columna.

    Aplica conversión de tipos, defaults y strip() a todos los campos.

    Args:
        row: Tupla con (column_name, column_type, is_nullable, ordinal_position,
                       column_default, column_comment, extra)

    Returns:
        tuple: (column_name, column_type, is_nullable, ordinal_position,
                column_default, column_comment, extra)
    """
    column_name: str = str(row[0]).strip()
    column_type: str = str(row[1]).strip().upper() if row[1] else "VARCHAR"
    is_nullable: int = 1 if str(row[2]).strip().upper() == "YES" else 0
    ordinal_position: int = int(row[3]) if row[3] is not None else 0
    column_default: str | None = str(row[4]) if row[4] else None
    column_comment: str = str(row[5]).strip() if row[5] else ""
    extra: str = str(row[6]).strip().upper() if len(row) > 6 else ""

    return column_name, column_type, is_nullable, ordinal_position, column_default, column_comment, extra


def _process_column_data(
    column_name: str,
    column_type: str,
    is_nullable: int,
    ordinal_position: int,
    column_default: str | None,
    column_comment: str,
    extra: str,
) -> tuple[str, str, int, int, str | None, str]:
    """Procesa y enriquece datos de columna (normalización, auto_increment).

    Aplica normalización de tipos MySQL → tipos estándar y enriquece comentarios
    con información de auto_increment si aplica.

    Args:
        column_name: Nombre de la columna
        column_type: Tipo en MySQL
        is_nullable: 1 si nullable, 0 si no
        ordinal_position: Posición ordinal en tabla
        column_default: Valor por defecto o None
        column_comment: Comentario original
        extra: Campo EXTRA de information_schema

    Returns:
        tuple: (column_name, normalized_type, is_nullable, ordinal_position,
                column_default, enriched_comment)
    """
    normalized_type: str = normalize_mysql_type(column_type)

    enriched_comment: str = column_comment
    if "AUTO_INCREMENT" in extra:
        enriched_comment = f"Auto-increment. {column_comment}".strip()

    return column_name, normalized_type, is_nullable, ordinal_position, column_default, enriched_comment


def fetch_columns_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene columnas de una tabla.

    Detecta auto_increment via EXTRA field y normaliza tipos MySQL a estándar.

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

    sql: str = build_mysql_columns_query()
    params: dict[str, str] = {"schema_name": schema, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 7:
            continue

        fields = _extract_column_fields(row)
        processed = _process_column_data(*fields)
        result.append(processed)

    return result


def fetch_columns_with_type_for_schema_sql() -> str:
    """SQL de columnas de todo un schema para migración DDL desde MySQL/MariaDB, con ``COLUMN_TYPE`` (D1, 0.21.0).

    Mismas columnas que ``metadata.mariadb.tables.fetch_columns_for_schema_sql`` (``TABLE_NAME`` primero) más
    ``COLUMN_TYPE`` al final, que conserva lo que ``DATA_TYPE`` pierde (``enum('a','b')``, ``int unsigned``,
    ``decimal(10,2)``). Válida en MySQL 8 y en MariaDB.

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION,
             NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT, ORDINAL_POSITION, COLUMN_TYPE).
    """
    return (
        "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
        "NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT, "
        "EXTRA, COLUMN_COMMENT, ORDINAL_POSITION, COLUMN_TYPE "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %(schema)s "
        "ORDER BY TABLE_NAME, ORDINAL_POSITION"
    )
