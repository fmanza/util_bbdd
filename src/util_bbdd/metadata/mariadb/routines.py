"""Helpers puros para metadata y DDL de rutinas MariaDB."""

from __future__ import annotations

from typing import Any

from ...results import Rows
from .common import decode_mariadb_hex_text, quote_mariadb_identifier


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
    """Filtra parámetros detallados por rutina y tipo."""
    upper_name: str = str(routine_name or "").upper()
    upper_type: str = str(routine_type or "").upper()
    return [
        row
        for row in rows
        if str(row.get("routine_type") or "").upper() == upper_type
        and str(row.get("routine_name") or "").upper() == upper_name
    ]


def build_public_mariadb_routine_parameter_rows(rows: list[dict[str, Any]]) -> Rows:
    """Convierte parámetros detallados al contrato público actual."""
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


def format_mariadb_definer(definer: str) -> str:
    """Renderiza DEFINER con quoting MariaDB."""
    normalized: str = str(definer or "").strip()
    if not normalized:
        return ""
    if normalized.startswith("`") and "`@" in normalized:
        return normalized
    if "@" in normalized:
        user, host = normalized.split("@", 1)
        safe_user: str = user.replace("`", "``")
        safe_host: str = host.replace("`", "``")
        return f"`{safe_user}`@`{safe_host}`"
    safe_definer: str = normalized.replace("`", "``")
    return f"`{safe_definer}`"


def format_mariadb_routine_parameter(
    *, routine_type: str, mode: str, name: str, data_type: str, default_value: str
) -> str:
    """Renderiza un parámetro de rutina MariaDB."""
    pieces: list[str] = []
    normalized_routine_type: str = str(routine_type or "").strip().upper()
    normalized_mode: str = str(mode or "").strip().upper()
    if normalized_mode and not (normalized_routine_type == "FUNCTION" and normalized_mode == "IN"):
        pieces.append(normalized_mode)
    if name:
        pieces.append(name)
    if data_type:
        pieces.append(data_type)
    if default_value:
        pieces.append(f"DEFAULT {default_value}")
    return " ".join(pieces)


def format_mariadb_return_type(*, data_type: str, charset: str, collation: str) -> str:
    """Renderiza RETURNS de FUNCTION MariaDB."""
    rendered: str = str(data_type or "").strip()
    if charset:
        rendered += f" CHARSET {charset}"
    if collation:
        rendered += f" COLLATE {collation}"
    return rendered


def _process_mariadb_routine_parameters(
    parameters: list[dict[str, Any]], routine_type: str, return_type: str
) -> tuple[list[str], str]:
    """Procesa parámetros y extrae return type si es necesario."""
    parameter_specs: list[str] = []
    effective_return_type: str = return_type

    for row in parameters:
        mode: str = str(row.get("mode") or "").strip().upper()
        if mode == "RETURN":
            data_type: str = str(row.get("data_type") or "").strip()
            if data_type:
                effective_return_type = format_mariadb_return_type(
                    data_type=data_type,
                    charset=str(row.get("charset") or "").strip(),
                    collation=str(row.get("collation") or "").strip(),
                )
            continue

        parameter_spec = _build_parameter_spec(routine_type, row)
        if parameter_spec:
            parameter_specs.append(parameter_spec)

    return parameter_specs, effective_return_type


def _build_parameter_spec(routine_type: str, row: dict[str, Any]) -> str:
    """Construye especificación de un parámetro."""
    mode: str = str(row.get("mode") or "").strip().upper()
    name: str = str(row.get("name") or "").strip()
    data_type: str = str(row.get("data_type") or "").strip()
    default_value: str = str(row.get("default_value") or "").strip()

    return format_mariadb_routine_parameter(
        routine_type=routine_type,
        mode=mode,
        name=name,
        data_type=data_type,
        default_value=default_value,
    )


def _build_mariadb_qualified_name(database: str, routine_name: str) -> str:
    """Construye nombre calificado de la rutina."""
    return (
        f"{quote_mariadb_identifier(database)}.{quote_mariadb_identifier(routine_name)}"
        if database
        else quote_mariadb_identifier(routine_name)
    )


def _build_mariadb_header_parts(routine_type: str, qualified_name: str, definer: str) -> list[str]:
    """Construye partes del header (CREATE, DEFINER, tipo, nombre)."""
    header_parts: list[str] = ["CREATE"]
    if definer:
        header_parts.append(f"DEFINER={format_mariadb_definer(definer)}")
    header_parts.append(routine_type)
    header_parts.append(qualified_name)
    return header_parts


def _build_mariadb_signature(routine_type: str, parameter_specs: list[str]) -> str:
    """Construye la signatura de parámetros según el tipo de rutina."""
    if routine_type == "FUNCTION":
        return f"({', '.join(parameter_specs)})" if parameter_specs else "()"

    if parameter_specs:
        return "(\n" + ",\n".join(f"  {spec}" for spec in parameter_specs) + "\n)"
    return "()"


def _build_mariadb_header_line(
    header_parts: list[str], signature: str, routine_type: str, effective_return_type: str
) -> str:
    """Construye la línea de header completa."""
    header_line: str = " ".join(header_parts) + signature
    if routine_type == "FUNCTION" and effective_return_type:
        header_line += f" RETURNS {effective_return_type}"
    return header_line


def _add_mariadb_optional_clauses(
    ddl_lines: list[str], routine_type: str, is_deterministic: str, security_type: str, routine_comment: str
) -> None:
    """Agrega cláusulas opcionales al DDL."""
    if routine_type == "FUNCTION" and is_deterministic == "YES":
        ddl_lines.append("DETERMINISTIC")
    if security_type and security_type != "DEFINER":
        ddl_lines.append(f"SQL SECURITY {security_type}")
    if routine_comment:
        escaped_comment: str = routine_comment.replace("\\", "\\\\").replace("'", "''")
        ddl_lines.append(f"COMMENT '{escaped_comment}'")


def build_mariadb_routine_ddl(
    *,
    database: str,
    routine_name: str,
    routine_type: str,
    routine_definition: str,
    definer: str,
    security_type: str,
    sql_data_access: str,
    is_deterministic: str,
    return_type: str,
    routine_comment: str,
    parameters: list[dict[str, Any]],
) -> str:
    """Construye CREATE PROCEDURE/FUNCTION MariaDB desde metadata."""
    del sql_data_access

    parameter_specs, effective_return_type = _process_mariadb_routine_parameters(parameters, routine_type, return_type)
    qualified_name: str = _build_mariadb_qualified_name(database, routine_name)
    header_parts: list[str] = _build_mariadb_header_parts(routine_type, qualified_name, definer)
    signature: str = _build_mariadb_signature(routine_type, parameter_specs)
    header_line: str = _build_mariadb_header_line(header_parts, signature, routine_type, effective_return_type)

    ddl_lines: list[str] = [header_line]
    _add_mariadb_optional_clauses(ddl_lines, routine_type, is_deterministic, security_type, routine_comment)
    ddl_lines.append(routine_definition)
    return "\n".join(line for line in ddl_lines if line is not None)
