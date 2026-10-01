"""Introspección de schemas y tablas en SQL Server."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import (
    build_sqlserver_columns_query,
    build_sqlserver_schemas_query,
    build_sqlserver_tables_query,
)
from .common import normalize_sqlserver_type


def _normalize_sqlserver_column_row(row: Any) -> tuple[str, str, int, int, str | None, str] | None:
    """Normaliza una fila individual de columna SQL Server.

    Args:
        row: Tupla de 7+ elementos de sys.columns

    Returns:
        Tupla (column_name, normalized_type, is_nullable, ordinal_position, column_default, column_comment)
        o None si es inválida
    """
    if not row or len(row) < 7:
        return None

    column_name = str(row[0]).strip()
    column_type = str(row[1]).strip().upper() if row[1] else "SQL_VARIANT"
    is_nullable = int(row[2]) if row[2] is not None else 0
    ordinal_position = int(row[3]) if row[3] is not None else 0
    column_default = str(row[4]) if row[4] else None
    column_comment = str(row[5]).strip() if row[5] else ""
    is_identity = int(row[6]) if row[6] is not None else 0

    normalized_type = normalize_sqlserver_type(column_type)
    if is_identity:
        column_comment = f"Identity column. {column_comment}".strip()

    return (column_name, normalized_type, is_nullable, ordinal_position, column_default, column_comment)


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

    return [normalized for row in rows if (normalized := _normalize_sqlserver_column_row(row)) is not None]


# ---------------------------------------------------------------------------
# SQL para migrate/extractors — queries de extracción de esquema SQL Server
# Parámetros estilo %(name)s (DB-API 2.0 / pymssql).
# ---------------------------------------------------------------------------


def fetch_tables_sql() -> str:
    """SQL para obtener tablas BASE TABLE de un schema SQL Server, con su comentario (``MS_Description``).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, TABLE_COMMENT).
    """
    return (
        "SELECT t.TABLE_NAME, CAST(ep.value AS NVARCHAR(4000)) "
        "FROM INFORMATION_SCHEMA.TABLES t "
        "LEFT JOIN sys.extended_properties ep "
        "  ON ep.class = 1 AND ep.name = 'MS_Description' AND ep.minor_id = 0 "
        "  AND ep.major_id = OBJECT_ID(QUOTENAME(t.TABLE_SCHEMA) + '.' + QUOTENAME(t.TABLE_NAME)) "
        "WHERE t.TABLE_SCHEMA = %(schema)s AND t.TABLE_TYPE = 'BASE TABLE' "
        "ORDER BY t.TABLE_NAME"
    )


# ─── migrate/extractors: una consulta por schema y tipo de objeto (D1, 0.21.0) ─────────────
# La primera columna es siempre el nombre de la tabla, vista o rutina; el resto, en el mismo orden que leen los
# extractores. 200 tablas: 823 consultas (20 s en el banco, ~24 ms cada una) → 8 (0,26 s).


def fetch_columns_for_schema_sql() -> str:
    """SQL de las columnas de todas las tablas y vistas de un schema SQL Server (uso: migrate/extractors).

    Detecta columnas IDENTITY via ``COLUMNPROPERTY`` (SQL Server 2008+).
    ``CHARACTER_MAXIMUM_LENGTH = -1`` indica el tipo MAX (nvarchar(max), etc.).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION,
             NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT, IS_IDENTITY, ORDINAL_POSITION, COLUMN_COMMENT).
    """
    return (
        "SELECT c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.CHARACTER_MAXIMUM_LENGTH, "
        "c.NUMERIC_PRECISION, c.NUMERIC_SCALE, c.IS_NULLABLE, c.COLUMN_DEFAULT, "
        "COLUMNPROPERTY(OBJECT_ID(c.TABLE_SCHEMA + '.' + c.TABLE_NAME), c.COLUMN_NAME, 'IsIdentity') AS IS_IDENTITY, "
        "c.ORDINAL_POSITION, CAST(ep.value AS NVARCHAR(4000)) "
        "FROM INFORMATION_SCHEMA.COLUMNS c "
        "LEFT JOIN sys.extended_properties ep "
        "  ON ep.class = 1 AND ep.name = 'MS_Description' "
        "  AND ep.major_id = OBJECT_ID(QUOTENAME(c.TABLE_SCHEMA) + '.' + QUOTENAME(c.TABLE_NAME)) "
        "  AND ep.minor_id = COLUMNPROPERTY(ep.major_id, c.COLUMN_NAME, 'ColumnId') "
        "WHERE c.TABLE_SCHEMA = %(schema)s "
        "ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION"
    )


def fetch_pk_for_schema_sql() -> str:
    """SQL de las columnas de clave primaria de todas las tablas de un schema SQL Server (uso: migrate/extractors).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, COLUMN_NAME) en el orden de la clave.
    """
    return (
        "SELECT kcu.TABLE_NAME, kcu.COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
        "JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
        "  ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
        "  AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA "
        "WHERE kcu.TABLE_SCHEMA = %(schema)s "
        "  AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY' "
        "ORDER BY kcu.TABLE_NAME, kcu.ORDINAL_POSITION"
    )


def fetch_fk_for_schema_sql() -> str:
    """SQL de las claves foráneas de todas las tablas de un schema SQL Server (uso: migrate/extractors).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REF_SCHEMA, REF_TABLE, REF_COLUMN,
             ORDINAL_POSITION, DELETE_RULE, UPDATE_RULE).
    """
    return (
        "SELECT kcu.TABLE_NAME, kcu.CONSTRAINT_NAME, kcu.COLUMN_NAME, "
        "kcu2.TABLE_SCHEMA AS REF_SCHEMA, kcu2.TABLE_NAME AS REF_TABLE, "
        "kcu2.COLUMN_NAME AS REF_COLUMN, kcu.ORDINAL_POSITION, "
        "rc.DELETE_RULE, rc.UPDATE_RULE "
        "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
        "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
        "  ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME "
        "  AND kcu.TABLE_SCHEMA = rc.CONSTRAINT_SCHEMA "
        "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu2 "
        "  ON kcu2.CONSTRAINT_NAME = rc.UNIQUE_CONSTRAINT_NAME "
        "  AND kcu2.TABLE_SCHEMA = rc.UNIQUE_CONSTRAINT_SCHEMA "
        "  AND kcu2.ORDINAL_POSITION = kcu.ORDINAL_POSITION "
        "WHERE kcu.TABLE_SCHEMA = %(schema)s "
        "ORDER BY kcu.TABLE_NAME, kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
    )


def fetch_indexes_for_schema_sql() -> str:
    """SQL de los índices no-PK de todas las tablas de un schema SQL Server via sys.* (uso: migrate/extractors).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, INDEX_NAME, COLUMN_NAME, is_unique, SEQ_IN_INDEX).
    """
    return (
        "SELECT t.name AS TABLE_NAME, i.name AS INDEX_NAME, c.name AS COLUMN_NAME, i.is_unique, "
        "ic.key_ordinal AS SEQ_IN_INDEX "
        "FROM sys.indexes i "
        "JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id "
        "JOIN sys.columns c ON c.object_id = i.object_id AND c.column_id = ic.column_id "
        "JOIN sys.tables t ON t.object_id = i.object_id "
        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
        "WHERE s.name = %(schema)s "
        "  AND i.is_primary_key = 0 AND i.type > 0 "
        "ORDER BY t.name, i.name, ic.key_ordinal"
    )


def fetch_routine_bodies_for_schema_sql() -> str:
    """SQL del código de todas las rutinas de un schema SQL Server (uso: migrate/extractors).

    Mismos tipos que el inventario de rutinas (``P``, ``FN``, ``IF``, ``TF``), desde ``sys.sql_modules``.

    Parámetros: ``%(schema_name)s``.

    Returns:
        str: SQL query para (ROUTINE_NAME, DEFINITION, ROUTINE_COMMENT); el comentario (``MS_Description``) desde
        0.23.0.
    """
    return (
        "SELECT o.name, sm.definition, CAST(ep.value AS NVARCHAR(4000)) "
        "FROM sys.sql_modules sm "
        "JOIN sys.objects o ON o.object_id = sm.object_id "
        "JOIN sys.schemas s ON s.schema_id = o.schema_id "
        "LEFT JOIN sys.extended_properties ep "
        "  ON ep.class = 1 AND ep.name = 'MS_Description' AND ep.minor_id = 0 AND ep.major_id = o.object_id "
        "WHERE s.name = %(schema_name)s AND o.type IN ('P', 'FN', 'IF', 'TF') "
        "ORDER BY o.name"
    )


def fetch_views_sql() -> str:
    """SQL para obtener vistas de un schema SQL Server.

    Usa ``OBJECT_DEFINITION``: texto completo de la vista, **con** su cabecera ``CREATE VIEW ... AS`` (quitarla es cosa
    del consumidor). ``INFORMATION_SCHEMA.VIEWS.VIEW_DEFINITION`` se trunca a 4000 caracteres, también en SQL Server
    2022 (H7). Devuelve NULL para vistas ``WITH ENCRYPTION`` o sin permiso ``VIEW DEFINITION``.

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (VIEW_NAME, DEFINITION, VIEW_COMMENT); el comentario (``MS_Description``) desde 0.22.0.
    """
    return (
        "SELECT v.name, OBJECT_DEFINITION(v.object_id), CAST(ep.value AS NVARCHAR(4000)) "
        "FROM sys.views v "
        "JOIN sys.schemas s ON s.schema_id = v.schema_id "
        "LEFT JOIN sys.extended_properties ep "
        "  ON ep.class = 1 AND ep.name = 'MS_Description' AND ep.minor_id = 0 AND ep.major_id = v.object_id "
        "WHERE s.name = %(schema)s "
        "ORDER BY v.name"
    )
