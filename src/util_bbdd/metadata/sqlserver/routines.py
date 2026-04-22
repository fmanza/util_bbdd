"""Introspección de routines (procedimientos, funciones) en SQL Server."""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import (
    build_sqlserver_parameters_query,
    build_sqlserver_routines_query,
)
from ._sqlserver_models import SqlServerParameterDetail, SqlServerRoutineDetail


def _normalize_sqlserver_parameter_row(row: Any) -> SqlServerParameterDetail | None:
    """Normaliza una fila individual de parámetro SQL Server.

    Args:
        row: Tupla de 7+ elementos de sys.parameters

    Returns:
        SqlServerParameterDetail o None si es inválida
    """
    if not row or len(row) < 7:
        return None

    param_name = str(row[0]).strip()
    obj_id = int(row[1]) if row[1] is not None else 0
    parameter_id = int(row[2]) if row[2] is not None else 0
    data_type = str(row[3]).strip()
    is_output = bool(int(row[4])) if row[4] is not None else False
    precision = int(row[5]) if row[5] is not None else None
    scale = int(row[6]) if row[6] is not None else None

    return SqlServerParameterDetail(
        param_name=param_name,
        object_id=obj_id,
        parameter_id=parameter_id,
        data_type=data_type,
        is_output=is_output,
        precision=precision if precision and precision > 0 else None,
        scale=scale if scale and scale > 0 else None,
    )


def fetch_routines_sync(connection: Any, schema: str | None = None) -> list[SqlServerRoutineDetail]:
    """Obtiene procedimientos almacenados y funciones.

    Args:
        connection: Conexión a SQL Server
        schema: Nombre del schema (por defecto 'dbo')

    Returns:
        list[SqlServerRoutineDetail]: Detalles de routines
    """
    schema_name = schema or "dbo"

    sql = build_sqlserver_routines_query()
    params = {"schema_name": schema_name}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[SqlServerRoutineDetail] = []
    for row in rows:
        if not row or len(row) < 4:
            continue

        routine_name = str(row[0]).strip()
        routine_type = str(row[1]).strip()
        object_id = int(row[2]) if row[2] is not None else 0
        parameters_count = int(row[3]) if row[3] is not None else 0

        result.append(
            SqlServerRoutineDetail(
                routine_name=routine_name,
                routine_type=routine_type,
                object_id=object_id,
                parameters_count=parameters_count,
            )
        )

    return result


def fetch_routine_parameters_sync(connection: Any, object_id: int | None = None) -> list[SqlServerParameterDetail]:
    """Obtiene parámetros de un procedimiento/función.

    Args:
        connection: Conexión a SQL Server
        object_id: ID del procedimiento/función en SQL Server

    Returns:
        list[SqlServerParameterDetail]: Detalles de parámetros
    """
    if not object_id:
        return []

    sql = build_sqlserver_parameters_query()
    params = {"object_id": object_id}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    return [normalized for row in rows if (normalized := _normalize_sqlserver_parameter_row(row)) is not None]
