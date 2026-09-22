"""Introspección de rutinas (PROCEDURE, FUNCTION) en MySQL."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ._adapter_helpers import (
    build_mysql_routine_parameters_query,
    build_mysql_routines_query,
)
from ._mysql_models import MysqlRoutineDetail
from .common import quote_mysql_identifier


def fetch_routines_sync(connection: Any, schema: str | None = None) -> list[MysqlRoutineDetail]:
    """Obtiene rutinas (PROCEDURE, FUNCTION) de un schema.

    Args:
        connection: Conexión a MySQL
        schema: Nombre del schema

    Returns:
        list[MysqlRoutineDetail]: Detalles de rutinas
    """
    if not schema:
        return []

    sql = build_mysql_routines_query()
    params = {"schema_name": schema}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[MysqlRoutineDetail] = []
    for row in rows:
        if not row or len(row) < 3:
            continue

        routine_name = str(row[0]).strip()
        routine_type = str(row[1]).strip()
        created_datetime: datetime | None = None

        if row[2]:
            try:
                # MySQL devuelve DATETIME o TIMESTAMP
                if isinstance(row[2], datetime):
                    created_datetime = row[2]
                else:
                    created_datetime = datetime.fromisoformat(str(row[2]))
            except (ValueError, TypeError):
                pass

        result.append(MysqlRoutineDetail(routine_name, routine_type, created_datetime))

    return result


def fetch_routine_parameters_sync(
    connection: Any, schema: str | None = None, routine_name: str | None = None
) -> list[tuple]:
    """Obtiene parámetros de una rutina.

    Args:
        connection: Conexión a MySQL
        schema: Nombre del schema
        routine_name: Nombre de la rutina

    Returns:
        list[tuple]: Filas (parameter_name, parameter_mode, data_type, ordinal_position)
    """
    if not schema or not routine_name:
        return []

    sql = build_mysql_routine_parameters_query()
    params = {"schema_name": schema, "routine_name": routine_name}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 4:
            continue

        parameter_name = str(row[0]).strip() if row[0] else ""
        parameter_mode = str(row[1]).strip() if row[1] else "IN"
        data_type = str(row[2]).strip() if row[2] else "VARCHAR"
        ordinal_position = int(row[3]) if row[3] is not None else 0

        result.append((parameter_name, parameter_mode, data_type, ordinal_position))

    return result


def fetch_routine_definition_sync(connection: Any, schema: str, routine_name: str, routine_type: str) -> str:
    """Obtiene el DDL completo de una rutina vía ``SHOW CREATE PROCEDURE``/``FUNCTION``.

    MDC-03 (AUDIT_CODE 2026-09-22): MySQL nunca implementó ``fetch_routine_definition_*``
    pese a estar registrado como productor de metadatos; sin este método no puede
    registrarse como ``RoutineAdapter`` completo (mismo patrón que MPG-01/MSS-02 en
    la Fase 3 de esta sesión).

    ``SHOW CREATE`` no admite bind params para el identificador de la rutina (no es un
    valor, es parte de la sintaxis); se cita con ``quote_mysql_identifier()`` en vez de
    interpolar el valor crudo, igual que el resto de introspección MySQL.

    Args:
        connection: Conexión a MySQL
        schema: Nombre del schema
        routine_name: Nombre de la rutina
        routine_type: Tipo de rutina ('PROCEDURE' o 'FUNCTION')

    Returns:
        str: DDL de la rutina (p.ej. 'CREATE PROCEDURE ...') o cadena vacía si no disponible.
    """
    if not schema or not routine_name:
        return ""

    keyword = "FUNCTION" if routine_type.upper() == "FUNCTION" else "PROCEDURE"
    qualified_name = f"{quote_mysql_identifier(schema)}.{quote_mysql_identifier(routine_name)}"
    sql = f"SHOW CREATE {keyword} {qualified_name}"

    try:
        cursor = connection.execute(sql)
        row = cursor.fetchone()
    except Exception:
        return ""

    if not row or len(row) < 3:
        return ""
    return str(row[2]).strip() if row[2] else ""
