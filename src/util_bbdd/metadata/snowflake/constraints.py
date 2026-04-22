"""Introspección de constraints (PRIMARY KEY, FOREIGN KEY) en Snowflake.

IMPORTANTE: Snowflake no enforza constraints (PK/FK/CHECK).
Son metadata-only para documentación y referencia.
"""

from __future__ import annotations

import logging

from typing import Any

from ._adapter_helpers import build_snowflake_fk_query, build_snowflake_pk_query
from .common import is_system_schema_snowflake

logger = logging.getLogger(__name__)


def _normalize_snowflake_pk_row(row: Any) -> tuple[str, str, int] | None:
    """Normaliza una fila individual de clave primaria Snowflake.

    Args:
        row: Tupla de 3+ elementos de INFORMATION_SCHEMA

    Returns:
        Tupla (constraint_name, column_name, ordinal_position) o None si es inválida
    """
    if not row or len(row) < 3:
        return None

    constraint_name = str(row[0]).strip() if row[0] else ""
    column_name = str(row[1]).strip() if row[1] else ""
    ordinal_position = int(row[2]) if row[2] is not None else 0

    if constraint_name and column_name:
        return (constraint_name, column_name, ordinal_position)
    return None


def _normalize_snowflake_fk_row(row: Any) -> tuple[str, str, str, str, str, str, int] | None:
    """Normaliza una fila individual de clave foránea Snowflake.

    Args:
        row: Tupla de 7+ elementos de INFORMATION_SCHEMA

    Returns:
        Tupla (constraint_name, column_name, ref_table, ref_column, on_delete_action, on_update_action, ordinal_position)
        o None si es inválida
    """
    if not row or len(row) < 7:
        return None

    constraint_name = str(row[0]).strip() if row[0] else ""
    column_name = str(row[1]).strip() if row[1] else ""
    ref_table = str(row[2]).strip() if row[2] else ""
    ref_column = str(row[3]).strip() if row[3] else ""
    on_update_action = str(row[4]).strip() if row[4] else "NO ACTION"
    on_delete_action = str(row[5]).strip() if row[5] else "NO ACTION"
    ordinal_position = int(row[6]) if row[6] is not None else 0

    if constraint_name and column_name and ref_table and ref_column:
        return (
            constraint_name,
            column_name,
            ref_table,
            ref_column,
            on_delete_action,
            on_update_action,
            ordinal_position,
        )
    return None


def fetch_primary_keys_sync(
    connection: Any, database: str | None = None, schema: str | None = None, table: str | None = None
) -> list[tuple]:
    """Obtiene claves primarias de una tabla via INFORMATION_SCHEMA.

    ADVERTENCIA CRÍTICA: Snowflake PK son ADVISORY; NO son enforced.
    Documentar como referencia solamente; confiar en lógica de aplicación para validación.

    Args:
        connection: Conexión a Snowflake
        database: Nombre de la base de datos
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (constraint_name, column_name, ordinal_position)
                    Vacío si no hay constraints o si no están soportados.
    """
    if not database or not schema or not table or is_system_schema_snowflake(schema):
        return []

    logger.warning(
        "Snowflake primary keys are ADVISORY and NOT ENFORCED. "
        "Use for documentation only. "
        "Database=%s, Schema=%s, Table=%s",
        database,
        schema,
        table,
    )

    sql = build_snowflake_pk_query()
    params = {"database_name": database, "schema_name": schema, "table_name": table}

    try:
        cursor = connection.execute(sql, params)
        rows: list[tuple[Any, ...]] = cursor.fetchall()
    except Exception as e:
        logger.warning("Failed to fetch primary keys (Snowflake): %s", e)
        return []

    result = [normalized for row in rows if (normalized := _normalize_snowflake_pk_row(row)) is not None]
    return sorted(result, key=lambda x: x[2])  # Ordenar por ordinal_position


def fetch_foreign_keys_sync(
    connection: Any, database: str | None = None, schema: str | None = None, table: str | None = None
) -> list[tuple]:
    """Obtiene claves foráneas de una tabla via INFORMATION_SCHEMA.

    ADVERTENCIA CRÍTICA: Snowflake FK son ADVISORY y NO son enforced.
    Documentar como referencia solamente; confiar en lógica de aplicación para validación.

    Args:
        connection: Conexión a Snowflake
        database: Nombre de la base de datos
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (constraint_name, column_name, ref_table, ref_column,
                           on_delete_action, on_update_action, ordinal_position)
                    Vacío si no hay constraints o si no están soportados.
    """
    if not database or not schema or not table or is_system_schema_snowflake(schema):
        return []

    logger.warning(
        "Snowflake foreign keys are ADVISORY and NOT ENFORCED. "
        "Use for documentation only. "
        "Database=%s, Schema=%s, Table=%s",
        database,
        schema,
        table,
    )

    sql = build_snowflake_fk_query()
    params = {"database_name": database, "schema_name": schema, "table_name": table}

    try:
        cursor = connection.execute(sql, params)
        rows: list[tuple[Any, ...]] = cursor.fetchall()
    except Exception as e:
        logger.warning("Failed to fetch foreign keys (Snowflake): %s", e)
        return []

    result = [normalized for row in rows if (normalized := _normalize_snowflake_fk_row(row)) is not None]
    return sorted(result, key=lambda x: x[6])  # Ordenar por ordinal_position
