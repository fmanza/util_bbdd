"""Introspección de rutinas (UDFs) en Redshift.

Redshift soporta principalmente funciones UDF. Soporte limitado para procedures
(disponible en ciertas versiones).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ._adapter_helpers import build_redshift_routines_query
from ._redshift_models import RedshiftRoutineDetail
from .common import is_system_schema_redshift


def fetch_routines_sync(connection: Any, schema: str | None = None) -> list[RedshiftRoutineDetail]:
    """Obtiene rutinas (UDFs) de un schema.

    Redshift soporta principalmente funciones UDF. Procedimientos tienen
    soporte limitado en ciertas versiones.

    Args:
        connection: Conexión a Redshift
        schema: Nombre del schema

    Returns:
        list[RedshiftRoutineDetail]: Detalles de rutinas
    """
    if not schema or is_system_schema_redshift(schema):
        return []

    sql = build_redshift_routines_query()
    params = {"schema_name": schema}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[RedshiftRoutineDetail] = []
    for row in rows:
        if not row or len(row) < 3:
            continue

        routine_name = str(row[0]).strip()
        routine_type = str(row[1]).strip()
        created_datetime: datetime | None = None

        if row[2]:
            try:
                # Redshift devuelve TIMESTAMP
                if isinstance(row[2], datetime):
                    created_datetime = row[2]
                else:
                    created_datetime = datetime.fromisoformat(str(row[2]))
            except (ValueError, TypeError):
                pass

        result.append(RedshiftRoutineDetail(routine_name, routine_type, created_datetime))

    return result


def fetch_routine_parameters_sync(
    connection: Any, schema: str | None = None, routine_name: str | None = None
) -> list[tuple]:
    """Obtiene parámetros de una rutina (función UDF).

    Redshift tiene soporte limitado para introspección de parámetros.

    Args:
        connection: Conexión a Redshift
        schema: Nombre del schema
        routine_name: Nombre de la rutina

    Returns:
        list[tuple]: Filas (parameter_name, parameter_mode, data_type, ordinal_position)
    """
    if not schema or not routine_name or is_system_schema_redshift(schema):
        return []

    # Redshift no expone parámetros de funciones UDFS via information_schema
    # Retornar lista vacía (sería necesario parser DDL para extraer parámetros)
    return []
