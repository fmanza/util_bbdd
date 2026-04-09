"""Helpers para rutinas (procedures/functions) Oracle."""

from __future__ import annotations

from ...results import Rows
from ._oracle_models import OracleParameterDetail, OracleRoutineDetail


def decode_oracle_routine_parameter_rows(
    routine_name: str, routine_type: str, rows: Rows
) -> list[OracleParameterDetail]:
    """Decodifica parámetros de rutina Oracle.

    Args:
        routine_name: Nombre de la rutina
        routine_type: Tipo de rutina
        rows: Filas desde query

    Returns:
        list[OracleParameterDetail]: Parámetros decodificados
    """
    decoded: list[OracleParameterDetail] = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 3:
            continue

        try:
            param_name = str(row[0]).strip() if row[0] else ""
            if not param_name:
                continue

            decoded.append(
                OracleParameterDetail(
                    param_name=param_name,
                    routine_name=routine_name,
                    routine_type=routine_type,
                    routine_owner="",
                    in_out=str(row[2]).strip().upper() if len(row) > 2 and row[2] else "IN",
                    data_type=str(row[3]).strip() if len(row) > 3 and row[3] else "VARCHAR2",
                    data_length=int(row[4]) if len(row) > 4 and row[4] is not None else None,
                    data_precision=int(row[5]) if len(row) > 5 and row[5] is not None else None,
                    data_scale=int(row[6]) if len(row) > 6 and row[6] is not None else None,
                    ordinal_position=int(row[1]) if len(row) > 1 and row[1] is not None else None,
                )
            )
        except (ValueError, TypeError):
            continue

    return decoded


def filter_routine_parameters(
    all_parameters: list[OracleParameterDetail], routine_name: str, routine_type: str
) -> list[OracleParameterDetail]:
    """Filtra parámetros para una rutina específica.

    Args:
        all_parameters: Lista de todos los parámetros
        routine_name: Nombre de la rutina a filtrar
        routine_type: Tipo de la rutina a filtrar

    Returns:
        list[OracleParameterDetail]: Parámetros filtrados
    """
    return [
        p
        for p in all_parameters
        if p.routine_name.upper() == routine_name.upper() and p.routine_type.upper() == routine_type.upper()
    ]


def routine_rows_to_public_format(routine_rows: list[OracleRoutineDetail]) -> Rows:
    """Convierte rutinas a formato público de fila.

    Args:
        routine_rows: Rutinas decodificadas

    Returns:
        Rows: (routine_name, routine_type, routine_owner)
    """
    result: Rows = []
    for routine in routine_rows:
        result.append((routine.routine_name, routine.routine_type, routine.routine_owner))
    return result


def parameter_rows_to_public_format(parameter_rows: list[OracleParameterDetail]) -> Rows:
    """Convierte parámetros a formato público de fila.

    Args:
        parameter_rows: Parámetros decodificados

    Returns:
        Rows: (in_out, param_name, data_type, ordinal_position)
    """
    result: Rows = []
    for param in parameter_rows:
        result.append(param.to_public_row())
    return result


__all__: list[str] = [
    "decode_oracle_routine_parameter_rows",
    "filter_routine_parameters",
    "routine_rows_to_public_format",
    "parameter_rows_to_public_format",
]
