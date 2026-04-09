"""Introspección de rutinas (UDFs, stored procedures) en Snowflake."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ._adapter_helpers import build_snowflake_routine_parameters_query, build_snowflake_routines_query
from ._snowflake_models import SnowflakeRoutineDetail
from .common import is_system_schema_snowflake


def fetch_routines_sync(
    connection: Any, database: str | None = None, schema: str | None = None
) -> list[SnowflakeRoutineDetail]:
    """Obtiene rutinas (UDFs, stored procedures) de un schema.

    Snowflake soporta:
    - FUNCTION (User-Defined Functions) en SQL, JavaScript, Java, Python, etc.
    - PROCEDURE (Stored Procedures, disponible en Snowflake 7.3+)

    Args:
        connection: Conexión a Snowflake
        database: Nombre de la base de datos
        schema: Nombre del schema

    Returns:
        list[SnowflakeRoutineDetail]: Detalles de rutinas
    """
    if not database or not schema or is_system_schema_snowflake(schema):
        return []

    sql = build_snowflake_routines_query()
    params = {"database_name": database, "schema_name": schema}

    try:
        cursor = connection.execute(sql, params)
        rows: list[tuple[Any, ...]] = cursor.fetchall()
    except Exception:
        # Si la query falla (versión antigua sin ROUTINES), retornar vacío
        return []

    result: list[SnowflakeRoutineDetail] = []
    for row in rows:
        if not row or len(row) < 3:
            continue

        routine_name = str(row[0]).strip() if row[0] else ""
        routine_type = str(row[1]).strip().upper() if len(row) > 1 and row[1] else "FUNCTION"
        created_datetime: datetime | None = None
        language = "SQL"

        # Parsear fecha de creación
        if len(row) > 2:
            try:
                if isinstance(row[2], datetime):
                    created_datetime = row[2]
                elif row[2]:
                    created_datetime = datetime.fromisoformat(str(row[2]))
            except (ValueError, TypeError):
                pass

        # Extraer lenguaje si se incluye en la query
        if len(row) > 4 and row[4]:
            language = str(row[4]).strip().upper()

        if routine_name:
            result.append(SnowflakeRoutineDetail(routine_name, routine_type, created_datetime, language))

    return result


def fetch_routine_parameters_sync(
    connection: Any, database: str | None = None, schema: str | None = None, routine_name: str | None = None
) -> list[tuple]:
    """Obtiene parámetros de una rutina (función/procedimiento).

    Args:
        connection: Conexión a Snowflake
        database: Nombre de la base de datos
        schema: Nombre del schema
        routine_name: Nombre de la rutina

    Returns:
        list[tuple]: Filas (parameter_name, parameter_mode, data_type, ordinal_position)
    """
    if not database or not schema or not routine_name or is_system_schema_snowflake(schema):
        return []

    sql = build_snowflake_routine_parameters_query()
    params = {"database_name": database, "schema_name": schema, "routine_name": routine_name}

    try:
        cursor = connection.execute(sql, params)
        rows: list[tuple[Any, ...]] = cursor.fetchall()
    except Exception:
        # Si la query falla (versión antigua), retornar vacío
        return []

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 4:
            continue

        parameter_name = str(row[0]).strip() if row[0] else ""
        parameter_mode = str(row[1]).strip() if len(row) > 1 and row[1] else "IN"
        data_type = str(row[2]).strip() if len(row) > 2 and row[2] else "VARIANT"
        ordinal_position = int(row[3]) if len(row) > 3 and row[3] is not None else 0

        if parameter_name:
            result.append((parameter_name, parameter_mode, data_type, ordinal_position))

    return sorted(result, key=lambda x: x[3])  # Ordenar por posición
