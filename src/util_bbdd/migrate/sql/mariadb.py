"""Re-exportador: queries SQL de extracción de esquema MariaDB.

Las implementaciones canónicas viven en
``util_bbdd.metadata.mariadb.tables``. Este módulo re-exporta
las funciones para mantener compatibilidad con los importadores
que usan la ruta ``migrate.sql.mariadb``.
"""

from __future__ import annotations

from ...metadata.mariadb.tables import (
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
