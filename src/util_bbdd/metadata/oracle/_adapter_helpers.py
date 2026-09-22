"""Helpers puros compartidos por los adaptadores sync y async de Oracle.

Responsabilidad: encapsular construcción de SQL y procesamiento de resultados
que son idénticos entre OracleSyncAdapter y OracleAsyncAdapter.
"""

from __future__ import annotations

from ...results import Rows
from ._oracle_models import OracleParameterDetail, OracleRoutineDetail
from .tables import (
    fetch_columns_sql,
    fetch_fk_constraint_sql,
    fetch_indexes_sql,
    fetch_pk_constraint_sql,
    fetch_routine_body_sql,
    fetch_routine_parameters_sql,
    fetch_routines_sql,
    fetch_schemas_sql,
    fetch_tables_sql,
)


def build_oracle_schemas_query() -> str:
    """Construye la consulta SQL para obtener schemas de Oracle.

    Returns:
        str: SQL query
    """
    return fetch_schemas_sql()


def build_oracle_tables_query() -> str:
    """Construye la consulta parametrizada para obtener tablas de Oracle.

    Parametrizado con :owner.

    Returns:
        str: SQL query
    """
    return fetch_tables_sql()


def build_oracle_columns_query() -> str:
    """Construye la consulta para obtener columnas de una tabla Oracle.

    Parametrizado con :owner y :table_name.

    Returns:
        str: SQL query
    """
    return fetch_columns_sql()


def build_oracle_pk_query() -> str:
    """Construye la consulta para obtener PK de una tabla Oracle.

    Parametrizado con :owner y :table_name.
    """
    return fetch_pk_constraint_sql()


def build_oracle_fk_query() -> str:
    """Construye la consulta para obtener FK de una tabla Oracle.

    Parametrizado con :owner y :table_name.
    """
    return fetch_fk_constraint_sql()


def build_oracle_indexes_query() -> str:
    """Construye la consulta para obtener índices de una tabla Oracle.

    Parametrizado con :owner y :table_name.
    """
    return fetch_indexes_sql()


def build_oracle_routines_query() -> str:
    """Construye la consulta para obtener rutinas del schema.

    Parametrizado con :owner.
    """
    return fetch_routines_sql()


def build_oracle_parameters_query() -> str:
    """Construye la consulta para obtener parámetros de rutinas.

    Parametrizado con :owner y :routine_name.
    """
    return fetch_routine_parameters_sql()


def build_oracle_routine_body_query() -> str:
    """Construye la consulta para obtener el body de una rutina desde ALL_SOURCE.

    Parametrizado con :owner, :routine_name y :routine_type.
    """
    return fetch_routine_body_sql()


def decode_oracle_routine_body(routine_type: str, routine_name: str, rows: Rows) -> str:
    """Reconstruye el DDL completo de una rutina Oracle a partir de las líneas de ALL_SOURCE.

    ``ALL_SOURCE.TEXT`` no incluye la cabecera ``CREATE OR REPLACE`` (empieza directamente en
    ``PROCEDURE "NOMBRE" (...) IS``); se antepone aquí para que el resultado cumpla el contrato
    de ``RoutineAdapterSync/Async.fetch_routine_definition_*`` (DDL ejecutable), a diferencia del
    extractor de ``migrate/`` que deja el body verbatim porque el emisor destino añade su propia
    cabecera.

    Args:
        routine_type: Tipo de rutina ('PROCEDURE' o 'FUNCTION'), usado solo para el fallback.
        routine_name: Nombre de la rutina, usado solo para el fallback.
        rows: Filas (line, text) de ``fetch_routine_body_sql()``, ya ordenadas por ``line``.

    Returns:
        str: DDL completo, o un comentario de fallback si ALL_SOURCE no tiene body accesible.
    """
    lines = [str(row[1]) for row in rows if isinstance(row, (tuple, list)) and len(row) > 1 and row[1]]
    body = "".join(lines).strip()
    if not body:
        return f"-- {routine_type} {routine_name} definition unavailable\n"
    return f"CREATE OR REPLACE {body}"


def decode_oracle_routine_rows(rows: Rows) -> list[OracleRoutineDetail]:
    """Decodifica filas de routines de Oracle a OracleRoutineDetail.

    Args:
        rows: Filas del query fetch_routines_sql

    Returns:
        list[OracleRoutineDetail]: Rutinas decodificadas
    """
    decoded: list[OracleRoutineDetail] = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 2:
            continue

        try:
            decoded.append(
                OracleRoutineDetail(
                    routine_name=str(row[0]).strip() if row[0] else "",
                    routine_type=str(row[1]).strip().upper() if row[1] else "PROCEDURE",
                    routine_owner=str(row[2]).strip() if len(row) > 2 and row[2] else "",
                    object_id=int(row[3]) if len(row) > 3 and row[3] is not None else None,
                )
            )
        except (ValueError, TypeError, IndexError):
            continue

    return decoded


def decode_oracle_parameter_rows(
    routine_owner: str, routine_name: str, routine_type: str, rows: Rows
) -> list[OracleParameterDetail]:
    """Decodifica filas de parámetros de Oracle a OracleParameterDetail.

    Args:
        routine_owner: Propietario de la rutina
        routine_name: Nombre de la rutina
        routine_type: Tipo de rutina (PROCEDURE, FUNCTION, etc)
        rows: Filas del query fetch_routine_parameters_sql

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
                    routine_owner=routine_owner,
                    in_out=str(row[2]).strip().upper() if len(row) > 2 and row[2] else "IN",
                    data_type=str(row[3]).strip() if len(row) > 3 and row[3] else "VARCHAR2",
                    data_length=int(row[4]) if len(row) > 4 and row[4] is not None else None,
                    data_precision=int(row[5]) if len(row) > 5 and row[5] is not None else None,
                    data_scale=int(row[6]) if len(row) > 6 and row[6] is not None else None,
                    ordinal_position=int(row[1]) if len(row) > 1 and row[1] is not None else None,
                    object_id=int(row[7]) if len(row) > 7 and row[7] is not None else None,
                    argument_id=int(row[8]) if len(row) > 8 and row[8] is not None else None,
                )
            )
        except (ValueError, TypeError, IndexError):
            continue

    return decoded


def routine_entries_to_rows(routine_rows: list[OracleRoutineDetail]) -> Rows:
    """Convierte entradas de rutinas Oracle al formato de fila pública.

    Args:
        routine_rows: Rutinas decodificadas

    Returns:
        Rows: Lista de tuples (routine_name, routine_type, routine_owner)
    """
    result: Rows = []
    for routine in routine_rows:
        result.append((routine.routine_name, routine.routine_type, routine.routine_owner))
    return result


__all__: list[str] = [
    "build_oracle_schemas_query",
    "build_oracle_tables_query",
    "build_oracle_columns_query",
    "build_oracle_pk_query",
    "build_oracle_fk_query",
    "build_oracle_indexes_query",
    "build_oracle_routines_query",
    "build_oracle_parameters_query",
    "build_oracle_routine_body_query",
    "decode_oracle_routine_rows",
    "decode_oracle_parameter_rows",
    "decode_oracle_routine_body",
    "routine_entries_to_rows",
]
