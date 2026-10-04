"""Mixin con helpers compartidos entre SyncDatabaseManager y AsyncDatabaseManager.

Contiene únicamente métodos cuya lógica es idéntica en ambos managers y que no
requieren ``async``/``await``: cachés, contexto de metadatos y fuente de catálogo
por lotes (ADR-003).

Requisitos de la clase consumidora (atributos de instancia):
    db_cache:            DatabaseMetadataCache
    logger:              logging.Logger
    db_type:             str
    database:            str
    conn_params:         dict[str, Any]
"""

from __future__ import annotations

import logging

from typing import Any

from ..metadata.cache import DatabaseMetadataCache
from ..metadata.catalog_registry import get_catalog_dialect
from ..metadata.snapshot_cache import SnapshotCache
from ._metadata_cache import CacheManager
from ._metadata_context import CacheKeyFactory, MetadataContextResolver


class DatabaseManagerSharedMixin:
    """Métodos compartidos extraídos de SyncDatabaseManager y AsyncDatabaseManager."""

    # Declarados para satisfacer mypy; las clases consumidoras los proporcionan.
    db_cache: DatabaseMetadataCache
    logger: logging.Logger
    db_type: str
    database: str
    conn_params: dict[str, Any]

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_manager(self) -> CacheManager:
        return CacheManager(db_cache=self.db_cache, logger=self.logger)

    def _clear_all_caches(self) -> None:
        """Limpia completamente todas las cachés de metadatos."""
        self._cache_manager().clear_all()
        self._invalidate_catalog()

    # ------------------------------------------------------------------
    # Lectura por lotes del catálogo (ADR-003, C1)
    # ------------------------------------------------------------------

    def _catalog_cache(self) -> SnapshotCache:
        """Caché de snapshots del manager (una por instancia, compartida por la fuente sync o async)."""
        cache: SnapshotCache | None = self.__dict__.get("_catalog_snapshot_cache")
        if cache is None:
            cache = SnapshotCache()
            self.__dict__["_catalog_snapshot_cache"] = cache
        return cache

    def _catalog_default_schema(self) -> str:
        """Schema que lee ``get_schema_metadata()`` sin argumento: el contexto de metadatos (``main`` en SQLite)."""
        return "main" if self.db_type == "sqlite" else self._get_query_context_database()

    def _catalog_source_id(self) -> str:
        """Identifica la base de datos en la caché, sin credenciales."""
        params = self.conn_params
        location = params.get("dsn") or f"{params.get('host', '')}:{params.get('port', '')}"
        return f"{self.db_type}://{location}/{self.database}"

    def _invalidate_catalog(self, context: str | None = None) -> None:
        """Descarta los snapshots leídos (todos, o los del schema del contexto) y el DDL de tablas leído."""
        self.__dict__.pop("_table_ddl_cache", None)
        cache: SnapshotCache | None = self.__dict__.get("_catalog_snapshot_cache")
        if cache is None:
            return
        if context is None:
            cache.invalidate(self._catalog_source_id())
            return
        schema = "main" if self.db_type == "sqlite" else context
        cache.invalidate(self._catalog_source_id(), get_catalog_dialect(self.db_type).normalize_name(schema))

    def _clear_table_cache(self, context: str, table: str) -> None:
        """Limpia caché para una tabla/vista específica."""
        self._cache_manager().clear_table(context=context, table=table)

    def _clear_routine_cache(self, context: str, routine: str, routine_type: str | None = None) -> None:
        """Limpia caché para una rutina específica."""
        self._cache_manager().clear_routine(context=context, routine=routine, routine_type=routine_type)

    def _clear_context_cache(self, context: str) -> None:
        """Limpia caché para un contexto/schema específico."""
        self._cache_manager().clear_context(context=context)

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

        # El snapshot es por schema: cualquier limpieza selectiva descarta el del schema afectado
        self._invalidate_catalog(resolved_context)

    # ------------------------------------------------------------------
    # Query context helpers
    # ------------------------------------------------------------------

    def _get_query_context_database(self) -> str:
        """Obtiene el contexto de esquema/base para consultas de metadatos."""
        return MetadataContextResolver.get_context_database(
            db_type=self.db_type,
            database=self.database,
            conn_params=self.conn_params,
        )

    def _get_query_context_label(self) -> str:
        """Obtiene etiqueta descriptiva del contexto de consultas de metadatos."""
        return MetadataContextResolver.get_context_label(self.db_type)

    def get_query_context_database(self) -> str:
        """Expone el contexto de metadatos (schema/database) para consumidores externos."""
        return self._get_query_context_database()

    # ------------------------------------------------------------------
    # Cache key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_context_key(context: str) -> str:
        return CacheKeyFactory.context_key(context)

    # ------------------------------------------------------------------
    # Result parsing helpers
    # ------------------------------------------------------------------
