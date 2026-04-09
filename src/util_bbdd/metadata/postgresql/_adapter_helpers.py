"""Helpers puros compartidos por los adaptadores sync y async de PostgreSQL.

Responsabilidad: encapsular construcción de SQL y procesamiento de resultados
que son idénticos entre PostgreSQLSyncAdapter y PostgreSQLAsyncAdapter.
"""

from __future__ import annotations

from ...results import Rows
from ._postgres_models import PgParameterDetail, PgRoutineDetail
from .routines import (
    build_postgres_routine_ddl,
)
from .tables import (
    fetch_columns_sql,
    fetch_fk_constraint_sql,
    fetch_indexes_sql,
    fetch_pk_constraint_sql,
    fetch_tables_sql,
    fetch_unique_constraint_sql,
)


def build_tables_sql(schema: str | None = None) -> str:
    """Construye la consulta SQL para obtener tablas de PostgreSQL.

    Args:
        schema: Nombre del schema. Si None, usa public.

    Returns:
        str: SQL query
    """
    return fetch_tables_sql(schema)


def build_columns_safe_sql(schema: str, table: str) -> str:
    """Construye la consulta para obtener columnas de una tabla PostgreSQL.

    Args:
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        str: SQL query con información de columnas
    """
    return fetch_columns_sql(schema, table)


def build_pk_constraint_sql(schema: str, table: str) -> str:
    """Construye la consulta para obtener PK de una tabla PostgreSQL."""
    return fetch_pk_constraint_sql(schema, table)


def build_fk_constraint_sql(schema: str, table: str) -> str:
    """Construye la consulta para obtener FK de una tabla PostgreSQL."""
    return fetch_fk_constraint_sql(schema, table)


def build_unique_constraint_sql(schema: str, table: str) -> str:
    """Construye la consulta para obtener constraints UNIQUE."""
    return fetch_unique_constraint_sql(schema, table)


def build_indexes_safe_sql(schema: str, table: str) -> str:
    """Construye la consulta para obtener índices de una tabla PostgreSQL."""
    return fetch_indexes_sql(schema, table)


def process_routine_result(
    routine_rows: list[PgRoutineDetail],
    routine_name: str,
    routine_type: str,
    parameter_rows: list[PgParameterDetail],
) -> str:
    """Construye el DDL completo de una rutina desde componentes decodificados.

    Args:
        routine_rows: Rutinas decodificadas
        routine_name: Nombre de la rutina a buscar
        routine_type: Tipo de rutina (FUNCTION, PROCEDURE, etc)
        parameter_rows: Parámetros decodificados

    Returns:
        str: DDL completo o comentario de fallback
    """
    target_row = next(
        (row for row in routine_rows if row.matches(routine_name=routine_name, routine_type=routine_type)), None
    )

    if target_row and target_row.routine_definition:
        # Filtrar parámetros de esta rutina específica
        routine_params = [
            p
            for p in parameter_rows
            if p.routine_name.upper() == routine_name.upper() and p.routine_type.upper() == routine_type.upper()
        ]

        return build_postgres_routine_ddl(
            schema=None,  # No tenemos schema en este contexto
            routine_name=routine_name,
            routine_type=routine_type,
            routine_definition=target_row.routine_definition,
            routine_owner=target_row.routine_owner,
            return_type=target_row.return_type,
            security_definer=target_row.security_definer,
            is_aggregate=target_row.is_aggregate,
            is_window=target_row.is_window,
            parameters=[p.to_dict() for p in routine_params],
        )

    return f"-- {routine_type} {routine_name} definition unavailable\n"


def routine_entries_to_rows(routine_rows: list[PgRoutineDetail]) -> Rows:
    """Convierte entradas de rutinas PostgreSQL al formato de fila pública (nombre, tipo, propietario)."""
    from .routines import routine_entries_to_rows as _routine_to_rows

    return _routine_to_rows(routine_rows)


__all__: list[str] = [
    "build_tables_sql",
    "build_columns_safe_sql",
    "build_pk_constraint_sql",
    "build_fk_constraint_sql",
    "build_unique_constraint_sql",
    "build_indexes_safe_sql",
    "process_routine_result",
    "routine_entries_to_rows",
]
