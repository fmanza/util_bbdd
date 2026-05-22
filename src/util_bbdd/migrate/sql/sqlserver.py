"""Re-exportador: queries SQL de extracción de esquema SQL Server.

Las implementaciones canónicas viven en
``util_bbdd.metadata.sqlserver.tables``. Este módulo re-exporta
las funciones para mantener compatibilidad con los importadores
que usan la ruta ``migrate.sql.sqlserver``.
"""

from __future__ import annotations

from ...metadata.sqlserver.tables import (
    fetch_columns_sql,
    fetch_fk_sql,
    fetch_indexes_sql,
    fetch_pk_sql,
    fetch_tables_sql,
    fetch_view_columns_sql,
    fetch_views_sql,
)

__all__: list[str] = [
    "fetch_tables_sql",
    "fetch_columns_sql",
    "fetch_pk_sql",
    "fetch_fk_sql",
    "fetch_indexes_sql",
    "fetch_views_sql",
    "fetch_view_columns_sql",
]
