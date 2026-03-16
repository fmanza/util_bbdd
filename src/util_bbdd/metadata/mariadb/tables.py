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
    return "CREATE TABLE " + table_identifier + " (\n" + ",\n".join(column_defs) + "\n)"


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
        quote_mariadb_identifier(str(row[0]))
        for row in pk_rows
        if isinstance(row, (tuple, list)) and len(row) > 0
    ]
    if not pk_columns:
        return ""
    return f"  PRIMARY KEY ({', '.join(pk_columns)})"
