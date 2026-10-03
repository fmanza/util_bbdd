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
        # MySQL marca en EXTRA los defaults de expresión con DEFAULT_GENERATED, que no es SQL (MariaDB no lo usa).
        extra: str = " ".join(token for token in str(row[5]).split() if token.upper() != "DEFAULT_GENERATED")
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


# ─── migrate/extractors: una consulta por schema y tipo de objeto (D1, 0.21.0) ─────────────
# La primera columna es siempre el nombre de la tabla (o vista); el resto, en el mismo orden que leen los
# extractores. 200 tablas: 823 consultas (1,06 s MariaDB / 0,84 s MySQL en el banco) → 8.


def fetch_columns_for_schema_sql() -> str:
    """SQL de las columnas de todas las tablas y vistas de un schema MariaDB (uso: migrate/extractors).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION,
             NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT, ORDINAL_POSITION).
    """
    return (
        "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
        "NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE, COLUMN_DEFAULT, "
        "EXTRA, COLUMN_COMMENT, ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %(schema)s "
        "ORDER BY TABLE_NAME, ORDINAL_POSITION"
    )


def fetch_pk_for_schema_sql() -> str:
    """SQL de las columnas de clave primaria de todas las tablas de un schema MariaDB (uso: migrate/extractors).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, COLUMN_NAME) en el orden de la clave.
    """
    return (
        "SELECT TABLE_NAME, COLUMN_NAME "
        "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = %(schema)s "
        "AND CONSTRAINT_NAME = 'PRIMARY' "
        "ORDER BY TABLE_NAME, ORDINAL_POSITION"
    )


def fetch_fk_for_schema_sql() -> str:
    """SQL de las columnas de las claves foráneas de todas las tablas de un schema MariaDB (uso: migrate/extractors).

    Sin las reglas ``ON DELETE``/``ON UPDATE``: se leen aparte con :func:`fetch_fk_rules_for_schema_sql` y se unen en
    Python. Unir ``KEY_COLUMN_USAGE`` con ``REFERENTIAL_CONSTRAINTS`` en SQL es cuadrático en el nº de FK
    (H-16, sesión 2026-10-03-metadata-centralization: 5000 tablas, MySQL 15,7 s y MariaDB 4,5 s; las dos consultas por
    separado, 52 ms y 183 ms).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA,
             REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, ORDINAL_POSITION).
    """
    return (
        "SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, "
        "REFERENCED_COLUMN_NAME, ORDINAL_POSITION "
        "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = %(schema)s "
        "AND REFERENCED_TABLE_NAME IS NOT NULL "
        "ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION"
    )


def fetch_fk_rules_for_schema_sql() -> str:
    """SQL de las reglas ``ON DELETE``/``ON UPDATE`` de todas las FK de un schema MariaDB (uso: migrate/extractors).

    Complementa :func:`fetch_fk_for_schema_sql` (ver H-16 allí). Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE, UPDATE_RULE).
    """
    return (
        "SELECT TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE, UPDATE_RULE "
        "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = %(schema)s"
    )


def fetch_indexes_for_schema_sql() -> str:
    """SQL de los índices no-PK de todas las tablas de un schema MariaDB (uso: migrate/extractors).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (TABLE_NAME, INDEX_NAME, COLUMN_NAME, NON_UNIQUE, SEQ_IN_INDEX).
    """
    return (
        "SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, NON_UNIQUE, SEQ_IN_INDEX "
        "FROM INFORMATION_SCHEMA.STATISTICS "
        "WHERE TABLE_SCHEMA = %(schema)s "
        "AND INDEX_NAME <> 'PRIMARY' "
        "ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX"
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


def fetch_routines_sql() -> str:
    """SQL para obtener routines (procedures/functions) de un schema MariaDB.

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (ROUTINE_NAME, ROUTINE_TYPE, ROUTINE_SCHEMA,
        ROUTINE_DEFINITION, DTD_IDENTIFIER, ROUTINE_COMMENT, IS_DETERMINISTIC, SQL_DATA_ACCESS, SECURITY_TYPE).
        DTD_IDENTIFIER contiene el tipo de retorno para FUNCTION; ROUTINE_COMMENT, desde 0.23.0; las características,
        desde 0.23.1 (para reconstruir el ``CREATE``: ``ROUTINE_DEFINITION`` es solo el cuerpo).
    """
    return (
        "SELECT ROUTINE_NAME, ROUTINE_TYPE, ROUTINE_SCHEMA, "
        "ROUTINE_DEFINITION, DTD_IDENTIFIER, ROUTINE_COMMENT, IS_DETERMINISTIC, SQL_DATA_ACCESS, SECURITY_TYPE "
        "FROM INFORMATION_SCHEMA.ROUTINES "
        "WHERE ROUTINE_SCHEMA = %(schema)s "
        "ORDER BY ROUTINE_NAME"
    )


_ROUTINE_KINDS: frozenset[str] = frozenset({"PROCEDURE", "FUNCTION"})


def fetch_routine_status_sql(kind: str) -> str:
    """SQL ``SHOW PROCEDURE STATUS`` / ``SHOW FUNCTION STATUS`` de un schema MariaDB/MySQL (uso: comparar).

    Parámetros: ``:db`` (estilo de ``sqlalchemy.text``).

    Args:
        kind: ``"PROCEDURE"`` o ``"FUNCTION"``.

    Returns:
        str: SQL con una fila por routine (columna ``Name``, entre otras).
    """
    if kind not in _ROUTINE_KINDS:
        msg = f"kind debe ser PROCEDURE o FUNCTION, no {kind!r}"
        raise ValueError(msg)
    return f"SHOW {kind} STATUS WHERE Db=:db"


def fetch_show_create_routine_sql(kind: str, database: str, routine_name: str) -> str:
    """SQL ``SHOW CREATE PROCEDURE/FUNCTION`` de una routine MariaDB/MySQL (uso: comparar).

    El nombre va calificado con ``database`` (si no está vacío): sin él, ``SHOW CREATE`` busca en la base de datos de
    la conexión. ``SHOW CREATE`` no admite bind params para el identificador: se cita con backticks.

    Args:
        kind: ``"PROCEDURE"`` o ``"FUNCTION"``.
        database: Schema de la routine; vacío para el de la conexión.
        routine_name: Nombre de la routine.

    Returns:
        str: SQL con una fila (columna ``Create Procedure`` o ``Create Function``).
    """
    if kind not in _ROUTINE_KINDS:
        msg = f"kind debe ser PROCEDURE o FUNCTION, no {kind!r}"
        raise ValueError(msg)
    qualified: str = quote_mariadb_identifier(routine_name)
    if database:
        qualified = f"{quote_mariadb_identifier(database)}.{qualified}"
    return f"SHOW CREATE {kind} {qualified}"


def fetch_routine_parameters_for_schema_sql() -> str:
    """SQL de los parámetros de todas las rutinas de un schema MySQL/MariaDB (uso: migrate/extractors, 0.23.1).

    Sin el valor de retorno de las funciones (``ORDINAL_POSITION = 0``, que ya da ``DTD_IDENTIFIER`` de ROUTINES).

    Parámetros: ``%(schema)s``.

    Returns:
        str: SQL query para (SPECIFIC_NAME, ROUTINE_TYPE, PARAMETER_MODE, PARAMETER_NAME, DTD_IDENTIFIER) en orden.
    """
    return (
        "SELECT SPECIFIC_NAME, ROUTINE_TYPE, PARAMETER_MODE, PARAMETER_NAME, DTD_IDENTIFIER "
        "FROM INFORMATION_SCHEMA.PARAMETERS "
        "WHERE SPECIFIC_SCHEMA = %(schema)s AND ORDINAL_POSITION > 0 "
        "ORDER BY SPECIFIC_NAME, ROUTINE_TYPE, ORDINAL_POSITION"
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
