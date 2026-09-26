"""Helpers puros para metadata y DDL de tablas MariaDB."""

from __future__ import annotations

from typing import Any

from ...results import Rows
from .common import decode_mariadb_hex_text, format_mariadb_default, quote_mariadb_identifier


def decode_mariadb_safe_column_rows(safe_rows: Rows) -> Rows:
    """Decodifica filas de columnas obtenidas con HEX(...)."""
    decoded_rows: Rows = []
    for row in safe_rows:
        if not isinstance(row, (tuple, list)) or len(row) < 8:
            continue

        default_is_null: bool = str(row[4]).strip() in {"1", "True", "true"}
        column_default: str | None = None
        if not default_is_null:
            column_default = decode_mariadb_hex_text(row[5])

        decoded_rows.append(
            (
                decode_mariadb_hex_text(row[0]),
                decode_mariadb_hex_text(row[1]),
                str(row[2]),
                str(row[3]),
                column_default,
                decode_mariadb_hex_text(row[6]),
                decode_mariadb_hex_text(row[7]),
            )
        )
    return decoded_rows


def build_mariadb_table_ddl(tabla: str, rows: list[Any], pk_rows: list[Any]) -> str:
    """Construye CREATE TABLE MariaDB desde filas de columnas y PK."""
    if not rows:
        return ""

    column_defs: list[str] = [_build_column_definition(row) for row in rows if _is_valid_column_row(row)]
    if not column_defs:
        return ""

    pk_constraint: str = _build_primary_key_constraint(pk_rows)
    if pk_constraint:
        column_defs.append(pk_constraint)

    table_identifier: str = quote_mariadb_identifier(tabla)
    col_defs_str: str = ",\n".join(column_defs)
    return f"CREATE TABLE {table_identifier} (\n{col_defs_str}\n)"


def _is_valid_column_row(row: Any) -> bool:
    return isinstance(row, (tuple, list)) and bool(row)


def _build_column_definition(row: Any) -> str:
    column_name: str = str(row[0]) if row else ""
    column_type: str = str(row[1]) if len(row) > 1 else "TEXT"
    nullable_flag: str = str(row[2]).upper() if len(row) > 2 else "YES"
    nullable: str = "NOT NULL" if nullable_flag == "NO" else "NULL"

    parts: list[str] = [quote_mariadb_identifier(column_name), column_type, nullable]
    if len(row) > 4 and row[4] is not None:
        parts.append(f"DEFAULT {format_mariadb_default(row[4])}")
    if len(row) > 5 and row[5]:
        extra: str = str(row[5]).strip()
        if extra:
            parts.append(extra)
    return "  " + " ".join(parts)


def _build_primary_key_constraint(pk_rows: list[Any]) -> str:
    pk_columns: list[str] = [
        quote_mariadb_identifier(str(row[0])) for row in pk_rows if isinstance(row, (tuple, list)) and len(row) > 0
    ]
    if not pk_columns:
        return ""
    return f"  PRIMARY KEY ({', '.join(pk_columns)})"


# ---------------------------------------------------------------------------
# SQL para migrate/extractors — queries de extracción de esquema MariaDB
# ---------------------------------------------------------------------------


def fetch_tables_sql() -> str:
    """SQL para obtener tablas BASE TABLE de un schema MariaDB.

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, TABLE_COMMENT).
    """
    return (
        "SELECT TABLE_NAME, TABLE_COMMENT "
        "FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_TYPE = 'BASE TABLE' "
        "ORDER BY TABLE_NAME"
    )


def fetch_columns_sql() -> str:
    """SQL para obtener columnas de una tabla MariaDB.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
             NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT,
             EXTRA, COLUMN_COMMENT, ORDINAL_POSITION).
    """
    return (
        "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
        "NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT, "
        "EXTRA, COLUMN_COMMENT, ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(table_name)s "
        "ORDER BY ORDINAL_POSITION"
    )


def fetch_pk_sql() -> str:
    """SQL para obtener columnas de clave primaria de una tabla MariaDB.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (COLUMN_NAME,) ordenado por ORDINAL_POSITION.
    """
    return (
        "SELECT COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(table_name)s "
        "AND CONSTRAINT_NAME = 'PRIMARY' "
        "ORDER BY ORDINAL_POSITION"
    )


def fetch_fk_sql() -> str:
    """SQL para obtener claves foráneas de una tabla MariaDB.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA,
             REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, ORDINAL_POSITION,
             DELETE_RULE, UPDATE_RULE).
    """
    return (
        "SELECT kcu.CONSTRAINT_NAME, kcu.COLUMN_NAME, "
        "kcu.REFERENCED_TABLE_SCHEMA, kcu.REFERENCED_TABLE_NAME, "
        "kcu.REFERENCED_COLUMN_NAME, kcu.ORDINAL_POSITION, "
        "rc.DELETE_RULE, rc.UPDATE_RULE "
        "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
        "JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
        "  ON rc.CONSTRAINT_SCHEMA = kcu.TABLE_SCHEMA "
        "  AND rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
        "WHERE kcu.TABLE_SCHEMA = %(schema)s AND kcu.TABLE_NAME = %(table_name)s "
        "AND kcu.REFERENCED_TABLE_NAME IS NOT NULL "
        "ORDER BY kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION"
    )


def fetch_indexes_sql() -> str:
    """SQL para obtener índices no-PK de una tabla MariaDB.

    Parámetros: ``%(schema)s``, ``%(table_name)s``.

    Returns:
        str: SQL query para (INDEX_NAME, COLUMN_NAME, NON_UNIQUE, SEQ_IN_INDEX).
    """
    return (
        "SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE, SEQ_IN_INDEX "
        "FROM INFORMATION_SCHEMA.STATISTICS "
        "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(table_name)s "
        "AND INDEX_NAME <> 'PRIMARY' "
        "ORDER BY INDEX_NAME, SEQ_IN_INDEX"
    )


def fetch_views_sql() -> str:
    """SQL para obtener vistas de un schema MariaDB.

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, VIEW_DEFINITION).
    """
    return (
        "SELECT TABLE_NAME, VIEW_DEFINITION "
        "FROM INFORMATION_SCHEMA.VIEWS "
        "WHERE TABLE_SCHEMA = %(schema)s "
        "ORDER BY TABLE_NAME"
    )


def fetch_view_columns_sql() -> str:
    """SQL para obtener columnas de una vista MariaDB.

    Parámetros: ``%(schema)s``, ``%(view_name)s``.

    Returns:
        str: SQL query para (COLUMN_NAME,) ordenado por ORDINAL_POSITION.
    """
    return (
        "SELECT COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(view_name)s "
        "ORDER BY ORDINAL_POSITION"
    )


def fetch_routines_sql() -> str:
    """SQL para obtener routines (procedures/functions) de un schema MariaDB.

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (ROUTINE_NAME, ROUTINE_TYPE, ROUTINE_SCHEMA,
        ROUTINE_DEFINITION, DTD_IDENTIFIER).
        DTD_IDENTIFIER contiene el tipo de retorno para FUNCTION.
    """
    return (
        "SELECT ROUTINE_NAME, ROUTINE_TYPE, ROUTINE_SCHEMA, "
        "ROUTINE_DEFINITION, DTD_IDENTIFIER "
        "FROM INFORMATION_SCHEMA.ROUTINES "
        "WHERE ROUTINE_SCHEMA = %(schema)s "
        "ORDER BY ROUTINE_NAME"
    )


def fetch_table_storage_engine_sql() -> str:
    """SQL con el motor de almacenamiento (``InnoDB``, ``MyISAM``, ``Aria``…) de una tabla. Vale también para MySQL.

    Lo usa ``BulkCrud.maintenance_scope``: ``DISABLE KEYS`` solo tiene efecto en MyISAM/Aria y en InnoDB provocaría un
    commit implícito.

    Parámetros: ``:schema`` (``None`` = ``DATABASE()``) y ``:tbl``.

    Returns:
        str: SQL con una fila y el nombre del motor.
    """
    return (
        "SELECT ENGINE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = COALESCE(:schema, DATABASE()) AND TABLE_NAME = :tbl"
    )
