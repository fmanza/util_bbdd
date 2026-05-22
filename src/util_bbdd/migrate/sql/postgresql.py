"""Re-exportador: queries SQL de extracción de esquema PostgreSQL.

Las implementaciones canónicas viven en
``util_bbdd.metadata.postgresql.tables``. Las 3 funciones con nombre
conflictivo usan aliases ``_for_extract`` (Opción P-A):
  - ``fetch_tables_sql``    → ``fetch_tables_for_extract_sql``
  - ``fetch_columns_sql``   → ``fetch_columns_for_extract_sql``
  - ``fetch_indexes_sql``   → ``fetch_indexes_for_extract_sql``

Este módulo re-exporta las funciones para mantener compatibilidad con los
importadores que usan la ruta ``migrate.sql.postgresql``.
"""

from __future__ import annotations

from ...metadata.postgresql.tables import (
    fetch_columns_for_extract_sql as fetch_columns_sql,
    fetch_fk_sql,
    fetch_indexes_for_extract_sql as fetch_indexes_sql,
    fetch_pk_sql,
    fetch_tables_for_extract_sql as fetch_tables_sql,
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
