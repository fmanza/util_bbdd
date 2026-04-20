"""Helpers internos para construir DDL de rutinas MariaDB."""

from __future__ import annotations

from typing import Any

from ._routine_format import (
    format_mariadb_definer,
    format_mariadb_return_type,
    format_mariadb_routine_parameter,
)
from .common import quote_mariadb_identifier


def _process_mariadb_routine_parameters(
    parameters: list[dict[str, Any]], routine_type: str, return_type: str
) -> tuple[list[str], str]:
    """Procesa parametros y extrae return type si es necesario."""
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
    """Construye la especificacion de un parametro."""
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
    """Construye partes del header CREATE/DEFINER/tipo/nombre."""
    header_parts: list[str] = ["CREATE"]
    if definer:
        header_parts.append(f"DEFINER={format_mariadb_definer(definer)}")
    header_parts.append(routine_type)
    header_parts.append(qualified_name)
    return header_parts


def _build_mariadb_signature(routine_type: str, parameter_specs: list[str]) -> str:
    """Construye la signatura de parametros segun el tipo de rutina."""
    if routine_type == "FUNCTION":
        return f"({', '.join(parameter_specs)})" if parameter_specs else "()"

    if parameter_specs:
        specs_str: str = ",\n".join(f"  {spec}" for spec in parameter_specs)
        return f"(\n{specs_str}\n)"
    return "()"


def _build_mariadb_header_line(
    header_parts: list[str], signature: str, routine_type: str, effective_return_type: str
) -> str:
    """Construye la linea de cabecera completa."""
    header_line: str = " ".join(header_parts) + signature
    if routine_type == "FUNCTION" and effective_return_type:
        header_line += f" RETURNS {effective_return_type}"
    return header_line


def _add_mariadb_optional_clauses(
    ddl_lines: list[str], routine_type: str, is_deterministic: str, security_type: str, routine_comment: str
) -> None:
    """Agrega clausulas opcionales al DDL."""
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


__all__: list[str] = ["build_mariadb_routine_ddl"]
