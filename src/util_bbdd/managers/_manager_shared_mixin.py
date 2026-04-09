"""Mixin con helpers compartidos entre SyncDatabaseManager y AsyncDatabaseManager.

Contiene únicamente métodos cuya lógica es idéntica en ambos managers y que no
requieren ``async``/``await``.  Cada método delega en las funciones puras de
``_manager_metadata`` y ``_manager_metadata_runtime``, por lo que la lógica real
sigue viviendo en un único lugar.

Requisitos de la clase consumidora (atributos de instancia):
    db_cache:            DatabaseMetadataCache
    relationship_cache:  RelationshipMetadataCache
    logger:              logging.Logger
    db_type:             str
    database:            str
    conn_params:         dict[str, Any]
"""

from __future__ import annotations

import logging

from typing import Any

from ..metadata.cache import DatabaseMetadataCache, RelationshipMetadataCache
from ..metadata.mariadb import escape_mariadb_sql_literal
from ._manager_metadata import (
    add_metadata_context_params,
    cache_context_key,
    cache_routine_key,
    cache_table_key,
    clear_all_caches,
    clear_context_cache,
    clear_routine_cache,
    clear_table_cache,
    clear_tuple_cache_by_context,
    get_query_context_database,
    get_query_context_label,
)
from ._manager_metadata_runtime import (
    normalize_ddl_result as normalize_manager_ddl_result,
    parse_charset_collation_result,
    parse_column_charset_collation_row,
)


class DatabaseManagerSharedMixin:
    """Métodos compartidos extraídos de SyncDatabaseManager y AsyncDatabaseManager."""

    # Declarados para satisfacer mypy; las clases consumidoras los proporcionan.
    db_cache: DatabaseMetadataCache
    relationship_cache: RelationshipMetadataCache
    logger: logging.Logger
    db_type: str
    database: str
    conn_params: dict[str, Any]

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _clear_all_caches(self) -> None:
        """Limpia completamente todas las cachés de metadatos."""
        clear_all_caches(db_cache=self.db_cache, relationship_cache=self.relationship_cache, logger=self.logger)

    def _clear_table_cache(self, context: str, table: str) -> None:
        """Limpia caché para una tabla/vista específica."""
        clear_table_cache(
            db_cache=self.db_cache,
            relationship_cache=self.relationship_cache,
            logger=self.logger,
            context=context,
            table=table,
        )

    def _clear_routine_cache(self, context: str, routine: str, routine_type: str | None = None) -> None:
        """Limpia caché para una rutina específica."""
        clear_routine_cache(
            db_cache=self.db_cache,
            logger=self.logger,
            context=context,
            routine=routine,
            routine_type=routine_type,
        )

    @staticmethod
    def _clear_tuple_cache_by_context(cache: dict[tuple[Any, ...], Any], context: str) -> None:
        clear_tuple_cache_by_context(cache, context)

    def _clear_context_cache(self, context: str) -> None:
        """Limpia caché para un contexto/schema específico."""
        clear_context_cache(db_cache=self.db_cache, logger=self.logger, context=context)

    def clear_cache(
        self,
        context_database: str | None = None,
        table: str | None = None,
        routine: str | None = None,
        routine_type: str | None = None,
    ) -> None:
        """Limpia cachés de metadatos (global o selectiva).

        Sin argumentos limpia todas las cachés. Con argumentos limpia
        únicamente entradas relacionadas.
        """
        if context_database is None and table is None and routine is None and routine_type is None:
            self._clear_all_caches()
            return

        resolved_context: str = str(
            context_database if context_database is not None else self._get_query_context_database() or ""
        )

        if table:
            self._clear_table_cache(resolved_context, str(table))

        if routine:
            self._clear_routine_cache(resolved_context, str(routine), str(routine_type) if routine_type else None)

        if not table and not routine:
            self._clear_context_cache(resolved_context)

    # ------------------------------------------------------------------
    # Query context helpers
    # ------------------------------------------------------------------

    def _get_query_context_database(self) -> str:
        """Obtiene el contexto de esquema/base para consultas de metadatos."""
        return get_query_context_database(
            db_type=self.db_type,
            database=self.database,
            conn_params=self.conn_params,
        )

    def _get_query_context_label(self) -> str:
        """Obtiene etiqueta descriptiva del contexto de consultas de metadatos."""
        return get_query_context_label(self.db_type)

    def _add_metadata_context_params(self, params: dict[str, Any], context: str | None) -> dict[str, Any]:
        """Añade parámetros de contexto metadata según motor."""
        return add_metadata_context_params(db_type=self.db_type, params=params, context=context)

    def get_query_context_database(self) -> str:
        """Expone el contexto de metadatos (schema/database) para consumidores externos."""
        return self._get_query_context_database()

    # ------------------------------------------------------------------
    # Cache key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_context_key(context: str) -> str:
        return cache_context_key(context)

    def _cache_table_key(self, context_database: str, table_name: str) -> tuple[str, str]:
        return cache_table_key(context_database, table_name)

    def _cache_routine_key(self, context_database: str, routine_name: str, routine_type: str) -> tuple[str, str, str]:
        return cache_routine_key(context_database, routine_name, routine_type)

    # ------------------------------------------------------------------
    # Result parsing helpers
    # ------------------------------------------------------------------

    def _normalize_ddl_result(self, ddl: Any) -> str:
        return normalize_manager_ddl_result(ddl)

    @staticmethod
    def _escape_sql_literal(value: str) -> str:
        return escape_mariadb_sql_literal(value)

    def _parse_charset_collation_result(self, result: tuple[Any, ...] | None) -> dict[str, Any]:
        """Parsea resultado de database charset/collation según tipo de BD."""
        return parse_charset_collation_result(self.db_type, result)

    def _parse_column_charset_collation_row(self, row: tuple[Any, ...]) -> tuple[str, str | None, str | None]:
        """Parsea una fila de resultado de charset/collation de columna según el tipo de BD."""
        return parse_column_charset_collation_row(self.db_type, row)
