"""Introspección de índices en Snowflake.

IMPORTANTE: Snowflake NO tiene índices nativos.
Usa CLUSTERING KEY para optimización. Los "índices" se documentan como marcadores
pero sin soporte nativo para creación/eliminación.
"""

from __future__ import annotations

import logging

from typing import Any

from .common import is_system_schema_snowflake

logger = logging.getLogger(__name__)


def fetch_indexes_sync(
    connection: Any, database: str | None = None, schema: str | None = None, table: str | None = None
) -> list[tuple]:
    """Obtiene índices de una tabla (stub).

    Snowflake NO tiene índices nativos. Esta función retorna lista vacía.
    Para optimización, Snowflake usa CLUSTERING KEY.

    Args:
        connection: Conexión a Snowflake
        database: Nombre de la base de datos
        schema: Nombre del schema
        table: Nombre de la tabla

    Returns:
        list[tuple]: Lista vacía (Snowflake sin soporte de índices)
    """
    if not database or not schema or not table or is_system_schema_snowflake(schema):
        return []

    logger.info(
        "Snowflake does not have native indexes. "
        "Use CLUSTERING KEY for query optimization instead. "
        "Database=%s, Schema=%s, Table=%s",
        database,
        schema,
        table,
    )

    # Snowflake no expone índices via INFORMATION_SCHEMA
    # CLUSTERING KEY es la alternativa para query optimization
    # Retornar lista vacía
    return []
