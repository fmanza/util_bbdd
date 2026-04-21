"""Fachada pública de helpers puros para rutinas PostgreSQL."""

from __future__ import annotations

from typing import Any

from ...results import Rows
from ._postgres_models import PgParameterDetail, PgRoutineDetail
from .common import normalize_postgres_type, quote_pg_identifier


def fetch_routines_sql(schema: str | None = None) -> str:
    """SQL query para obtener funciones y procedimientos PostgreSQL.

    Args:
        schema: Nombre del schema. Si None, usa public.

    Returns:
        str: SQL query para (routine_name, routine_type, routine_owner, routine_definition, return_type)
    """
    _schema = schema or "public"
    return (
        "SELECT "
        "p.proname AS routine_name, "
        "CASE WHEN p.prokind = 'f' THEN 'FUNCTION' "
        "     WHEN p.prokind = 'p' THEN 'PROCEDURE' "
        "     WHEN p.prokind = 'a' THEN 'AGGREGATE' "
        "     WHEN p.prokind = 'w' THEN 'WINDOW' "
        "     ELSE 'FUNCTION' END AS routine_type, "
        "u.usename AS routine_owner, "
        "pg_get_functiondef(p.oid) AS routine_definition, "
        "CASE WHEN p.proretset THEN 'TABLE(' || t.typname || ')' "
        "     ELSE t.typname END AS return_type, "
        "CASE WHEN p.prokind = 'a' THEN 1 ELSE 0 END AS is_aggregate, "
        "CASE WHEN p.prokind = 'w' THEN 1 ELSE 0 END AS is_window, "
        "p.prosecdef AS security_definer "
        "FROM pg_proc p "
        "JOIN pg_namespace ns ON p.pronamespace = ns.oid "
        "JOIN pg_user u ON p.proowner = u.usesysid "
        "LEFT JOIN pg_type t ON p.prorettype = t.oid "
        "WHERE ns.nspname = %(schema)s "
        "ORDER BY p.proname"
    )


def fetch_routine_parameters_sql() -> str:
    """SQL query para obtener parámetros de una función/procedimiento en PostgreSQL.

    Returns:
        str: SQL query para (ordinal_position, param_mode, param_name, param_type, default_value)
    """
    return (
        "SELECT "
        "ia.ordinal_position, "
        "ia.parameter_mode, "
        "ia.parameter_name, "
        "ia.data_type, "
        "pg_get_pardef(p.oid, ia.ordinal_position - 1) AS default_value "
        "FROM information_schema.parameters ia "
        "JOIN pg_namespace ns ON TRUE "
        "JOIN pg_proc p ON p.proname = ia.specific_name AND ns.oid = p.pronamespace "
        "WHERE ia.specific_schema = %(schema)s "
        "  AND ia.routine_name = %(routine_name)s "
        "  AND ia.parameter_mode IS NOT NULL "
        "ORDER BY ia.ordinal_position"
    )


def _extract_routine_detail_from_row(row: Any) -> PgRoutineDetail | None:
    """Extrae los detalles de una fila PostgreSQL individual.

    Args:
        row: Tupla/lista de rutina del query

    Returns:
        PgRoutineDetail si la fila es válida, None en caso contrario
    """
    routine_name = str(row[0]).strip() if row[0] else ""
    routine_type = str(row[1]).strip().upper() if len(row) > 1 and row[1] else "FUNCTION"
    routine_owner = str(row[2]).strip() if len(row) > 2 and row[2] else ""
    routine_definition = str(row[3]).strip() if len(row) > 3 and row[3] else ""
    return_type = str(row[4]).strip() if len(row) > 4 and row[4] else ""
    is_aggregate = bool(row[5]) if len(row) > 5 else False
    is_window = bool(row[6]) if len(row) > 6 else False
    security_definer = bool(row[7]) if len(row) > 7 else False

    if not routine_name:
        return None

    return PgRoutineDetail(
        routine_name=routine_name,
        routine_type=routine_type,
        routine_owner=routine_owner,
        routine_definition=routine_definition,
        return_type=return_type,
        is_aggregate=is_aggregate,
        is_window=is_window,
        security_definer=security_definer,
    )


def decode_postgres_routine_rows(rows: Rows) -> list[PgRoutineDetail]:
    """Decodifica filas de rutinas PostgreSQL en modelos IR.

    Args:
        rows: Filas del query fetch_routines_sql

    Returns:
        list[PgRoutineDetail]
    """
    routines: list[PgRoutineDetail] = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 5:
            continue

        detail = _extract_routine_detail_from_row(row)
        if detail:
            routines.append(detail)

    return routines


def _extract_parameter_detail_from_row(row: Any) -> PgParameterDetail | None:
    """Extrae los detalles de una fila de parámetro PostgreSQL individual.

    Args:
        row: Tupla/lista de parámetro del query

    Returns:
        PgParameterDetail si la fila es válida, None en caso contrario
    """
    ordinal_position = int(row[0]) if row[0] else None
    mode = str(row[1]).strip().upper() if len(row) > 1 and row[1] else "IN"
    param_name = str(row[2]).strip() if len(row) > 2 and row[2] else f"param_{ordinal_position}"
    data_type = str(row[3]).strip() if len(row) > 3 and row[3] else "unknown"
    default_value = str(row[4]).strip() if len(row) > 4 and row[4] else None

    # Normalizar tipo usando funciones compartidas
    normalized_type = normalize_postgres_type(data_type)

    return PgParameterDetail(
        mode=mode,
        name=param_name,
        routine_name="",  # Se asigna en filtro
        routine_type="",  # Se asigna en filtro
        data_type=normalized_type,
        ordinal_position=ordinal_position,
        default_value=default_value,
    )


def decode_postgres_parameter_rows(rows: Rows) -> list[PgParameterDetail]:
    """Decodifica filas de parámetros PostgreSQL en modelos IR.

    Args:
        rows: Filas del query fetch_routine_parameters_sql

    Returns:
        list[PgParameterDetail]
    """
    parameters: list[PgParameterDetail] = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 4:
            continue

        detail = _extract_parameter_detail_from_row(row)
        if detail:
            parameters.append(detail)

    return parameters


def filter_postgres_routine_parameter_entries(
    entries: list[PgParameterDetail], *, routine_name: str, routine_type: str
) -> list[PgParameterDetail]:
    """Filtra parámetros de una rutina específica.

    Args:
        entries: Lista de parámetros decodificados
        routine_name: Nombre de la rutina
        routine_type: Tipo de rutina (FUNCTION, PROCEDURE, etc)

    Returns:
        Parámetros coincidentes
    """
    return [param for param in entries if param.matches(routine_name=routine_name, routine_type=routine_type)]


def build_public_postgres_routine_parameter_entry_rows(entries: list[PgParameterDetail]) -> Rows:
    """Convierte parámetros a filas públicas (mode, name, data_type, default, ordinal).

    Args:
        entries: Parámetros decodificados

    Returns:
        Rows[(mode, name, data_type, default, ordinal), ...]
    """
    return sorted([entry.to_public_row() for entry in entries], key=lambda row: row[4] or 999)


def build_postgres_routine_ddl(
    *,
    schema: str | None,
    routine_name: str,
    routine_type: str,
    routine_definition: str,
    routine_owner: str = "",
    security_definer: bool = False,
    is_aggregate: bool = False,
    is_window: bool = False,
) -> str:
    """Construye DDL de función/procedimiento desde componentes.

    Args:
        schema: Nombre del schema (para comentarios)
        routine_name: Nombre de la rutina
        routine_type: FUNCTION, PROCEDURE, AGGREGATE, WINDOW
        routine_definition: Cuerpo/definición completa
        routine_owner: Propietario (usuario)
        security_definer: Si debe ser SECURITY DEFINER
        is_aggregate: Si es agregado
        is_window: Si es función ventana

    Returns:
        str: DDL completo con comentarios
    """
    lines: list[str] = []

    # Comentario informativo
    if schema:
        lines.append(f"-- Schema: {schema}")
    if routine_owner:
        lines.append(f"-- Owner: {routine_owner}")
    if is_aggregate:
        lines.append("-- Type: AGGREGATE")
    if is_window:
        lines.append("-- Type: WINDOW FUNCTION")
    if security_definer:
        lines.append("-- Security: DEFINER")

    lines.append("")

    # La definición completa ya viene de pg_get_functiondef o pg_get_functiondef
    # que incluye CREATE FUNCTION/PROCEDURE, parámetros, etc.
    if routine_definition:
        lines.append(routine_definition)
    else:
        # Fallback mínimo si no hay definición
        qual_name = quote_pg_identifier(routine_name)
        lines.append(f"-- {routine_type} {qual_name} definition unavailable")

    return "\n".join(lines)


def routine_entries_to_rows(routine_rows: list[PgRoutineDetail]) -> Rows:
    """Convierte entradas de rutinas PostgreSQL al formato de fila pública (nombre, tipo, propietario).

    Args:
        routine_rows: Rutinas decodificadas

    Returns:
        Rows[(routine_name, routine_type, routine_owner), ...]
    """
    return sorted(
        [
            (entry.routine_name, entry.routine_type, entry.routine_owner)
            for entry in routine_rows
            if entry.routine_name.strip()
        ],
        key=lambda row: (str(row[1]), str(row[0])),
    )


__all__: list[str] = [
    "fetch_routines_sql",
    "fetch_routine_parameters_sql",
    "decode_postgres_routine_rows",
    "decode_postgres_parameter_rows",
    "filter_postgres_routine_parameter_entries",
    "build_public_postgres_routine_parameter_entry_rows",
    "build_postgres_routine_ddl",
    "routine_entries_to_rows",
]
