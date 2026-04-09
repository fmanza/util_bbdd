"""Introspección de índices en Redshift.

Redshift tiene soporte limitado para índices. Se usa principalmente pg_catalog.pg_indexes
para listar índices presentes.
"""

from __future__ import annotations

from typing import Any

from ._adapter_helpers import build_redshift_indexes_query
from .common import is_system_schema_redshift


def fetch_indexes_sync(connection: Any, schema: str | None = None, table: str | None = None) -> list[tuple]:
    """Obtiene índices de una tabla via pg_catalog.pg_indexes.

    Redshift tiene soporte limitado y no expone información de uniqueness
    a través de pg_catalog como PostgreSQL.

    Args:
        connection: Conexión a Redshift
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Filas (index_name, column_name, seq_in_index, is_unique)
    """
    if not schema or not table or is_system_schema_redshift(schema):
        return []

    sql = build_redshift_indexes_query()
    params = {"schema_name": schema, "table_name": table}

    cursor = connection.execute(sql, params)
    rows: list[tuple[Any, ...]] = cursor.fetchall()

    result: list[tuple] = []
    for row in rows:
        if not row or len(row) < 3:
            continue

        index_name = str(row[0]).strip()

        # Redshift pg_indexes no expone uniqueness, asumimos non-unique
        seq_in_index = 1
        is_unique = 0

        result.append((index_name, index_name, seq_in_index, is_unique))

    return result
