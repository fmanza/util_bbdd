"""Introspección de constraints (PRIMARY KEY, FOREIGN KEY) en Redshift.

IMPORTANTE: Redshift no enforza constraints (PK/FK/CHECK).
Son metadata-only para documentación y referencia.
"""

from __future__ import annotations

import logging

from typing import Any

from ._adapter_helpers import build_redshift_fk_query, build_redshift_pk_query
from .common import is_system_schema_redshift

logger = logging.getLogger(__name__)


def _normalize_redshift_fk_row(row: Any) -> tuple[str, str, str, str, str, str, int] | None:
    """Normaliza una fila individual de clave foránea Redshift.

    Args:
        row: Tupla de 7+ elementos de information_schema

    Returns:
        Tupla (constraint_name, column_name, ref_table, ref_column, on_delete_action, on_update_action, ordinal_position)
        o None si es inválida
    """
    if not row or len(row) < 7:
        return None

    constraint_name = str(row[0]).strip()
    column_name = str(row[1]).strip()
    ref_table = str(row[2]).strip() if row[2] else ""
    ref_column = str(row[3]).strip() if row[3] else ""
    update_action = str(row[4]).strip() if row[4] else "RESTRICT"
    delete_action = str(row[5]).strip() if row[5] else "RESTRICT"
    ordinal_position = int(row[6]) if row[6] is not None else 0

    on_delete = normalize_redshift_action(delete_action)
    on_update = normalize_redshift_action(update_action)

    return (constraint_name, column_name, ref_table, ref_column, on_delete, on_update, ordinal_position)


def fetch_primary_keys_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene claves primarias de una tabla via information_schema.

    ADVERTENCIA: Redshift PK son ADVISORY; no son enforced.

    Args:
        connection: Conexión a Redshift
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (constraint_name, column_name, ordinal_position)
    """
    if not schema or not table or is_system_schema_redshift(schema):
        return []

    logger.warning(
        "Redshift primary keys are advisory (not enforced). Use for documentation only. Schema=%s, Table=%s",
        schema,
        table,
    )

    sql = build_redshift_pk_query()
    params = {"schema_name": schema, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 3:
            continue

        constraint_name = str(row[0]).strip()
        column_name = str(row[1]).strip()
        ordinal_position = int(row[2]) if row[2] is not None else 0

        result.append((constraint_name, column_name, ordinal_position))

    return sorted(result, key=lambda x: x[2])  # Ordenar por ordinal_position


def fetch_foreign_keys_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene claves foráneas de una tabla via information_schema.

    ADVERTENCIA: Redshift FK son ADVISORY; no son enforced.

    Args:
        connection: Conexión a Redshift
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (constraint_name, column_name, ref_table, ref_column,
                           on_delete_action, on_update_action, ordinal_position)
    """
    if not schema or not table or is_system_schema_redshift(schema):
        return []

    logger.warning(
        "Redshift foreign keys are advisory (not enforced). Use for documentation only. Schema=%s, Table=%s",
        schema,
        table,
    )

    sql = build_redshift_fk_query()
    params = {"schema_name": schema, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    return [normalized for row in rows if (normalized := _normalize_redshift_fk_row(row)) is not None]


def normalize_redshift_action(action: str) -> str:
    """Normaliza acciones Redshift a formas comunes.

    Args:
        action: Acción como 'NO ACTION', 'RESTRICT', 'CASCADE', etc.

    Returns:
        str: Acción normalizada
    """
    if not action:
        return "RESTRICT"

    a = action.strip().upper()
    mapping = {
        "NO ACTION": "NO ACTION",
        "RESTRICT": "RESTRICT",
        "CASCADE": "CASCADE",
        "SET NULL": "SET NULL",
        "SET DEFAULT": "SET DEFAULT",
    }
    return mapping.get(a, "RESTRICT")
