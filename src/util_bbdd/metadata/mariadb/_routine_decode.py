"""Helpers internos para decode y normalizacion de rutinas MariaDB."""

from __future__ import annotations

from typing import Any

from ...results import Rows
from .common import decode_mariadb_hex_text


def decode_mariadb_routine_detail_rows(rows: Rows) -> list[dict[str, Any]]:
    """Decodifica filas detalladas de information_schema.routines."""
    decoded_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 10:
            continue
        decoded_rows.append(
            {
                "routine_name": decode_mariadb_hex_text(row[0]).strip(),
                "routine_type": str(row[1] or "").strip().upper(),
                "routine_comment": decode_mariadb_hex_text(row[2]).strip(),
                "definer": decode_mariadb_hex_text(row[3]).strip(),
                "security_type": decode_mariadb_hex_text(row[4]).strip().upper(),
                "sql_data_access": decode_mariadb_hex_text(row[5]).strip().upper(),
                "is_deterministic": str(row[6] or "").strip().upper(),
                "return_type": decode_mariadb_hex_text(row[7]).strip(),
                "sql_mode": decode_mariadb_hex_text(row[8]).strip(),
                "routine_definition": decode_mariadb_hex_text(row[9]).strip(),
            }
        )
    return decoded_rows


def decode_mariadb_routine_parameter_detail_rows(rows: Rows) -> list[dict[str, Any]]:
    """Decodifica filas detalladas de information_schema.parameters."""
    decoded_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 8:
            continue
        mode_value = row[0]
        name_value = row[1]
        decoded_rows.append(
            {
                "mode": (
                    str(mode_value)
                    if str(mode_value) == "RETURN"
                    else decode_mariadb_hex_text(mode_value).strip().upper()
                ),
                "name": (
                    str(name_value)
                    if str(name_value) == "RETURN_VALUE"
                    else decode_mariadb_hex_text(name_value).strip()
                ),
                "routine_type": str(row[2] or "").strip().upper(),
                "routine_name": decode_mariadb_hex_text(row[3]).strip(),
                "data_type": decode_mariadb_hex_text(row[4]).strip(),
                "charset": decode_mariadb_hex_text(row[5]).strip(),
                "collation": decode_mariadb_hex_text(row[6]).strip(),
                "default_value": "",
                "ordinal_position": row[7],
            }
        )
    return decoded_rows


def filter_mariadb_routine_parameter_rows(
    rows: list[dict[str, Any]], *, routine_name: str, routine_type: str
) -> list[dict[str, Any]]:
    """Filtra parametros detallados por rutina y tipo."""
    upper_name: str = str(routine_name or "").upper()
    upper_type: str = str(routine_type or "").upper()
    return [
        row
        for row in rows
        if str(row.get("routine_type") or "").upper() == upper_type
        and str(row.get("routine_name") or "").upper() == upper_name
    ]


def build_public_mariadb_routine_parameter_rows(rows: list[dict[str, Any]]) -> Rows:
    """Convierte parametros detallados al contrato publico actual."""
    return [
        (
            str(row.get("mode") or ""),
            str(row.get("name") or ""),
            str(row.get("data_type") or ""),
            str(row.get("default_value") or ""),
            row.get("ordinal_position"),
        )
        for row in rows
    ]


__all__: list[str] = [
    "build_public_mariadb_routine_parameter_rows",
    "decode_mariadb_routine_detail_rows",
    "decode_mariadb_routine_parameter_detail_rows",
    "filter_mariadb_routine_parameter_rows",
]
