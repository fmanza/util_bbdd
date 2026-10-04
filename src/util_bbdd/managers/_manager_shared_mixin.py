"""Mixin con helpers compartidos entre SyncDatabaseManager y AsyncDatabaseManager.

Contiene únicamente métodos cuya lógica es idéntica en ambos managers y que no
requieren ``async``/``await``: contexto de metadatos y fuente de catálogo por lotes
con su caché (ADR-003).

Requisitos de la clase consumidora (atributos de instancia):
    logger:              logging.Logger
    db_type:             str
    database:            str
    conn_params:         dict[str, Any]
"""

from __future__ import annotations

import logging

from typing import Any

from ..metadata.catalog_registry import get_catalog_dialect
from ..metadata.snapshot_cache import SnapshotCache
from ._metadata_context import MetadataContextResolver


class DatabaseManagerSharedMixin:
    """Métodos compartidos extraídos de SyncDatabaseManager y AsyncDatabaseManager."""

    # Declarados para satisfacer mypy; las clases consumidoras los proporcionan.
    logger: logging.Logger
    db_type: str
    database: str
    conn_params: dict[str, Any]

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

    def clear_cache(
        self,
        context_database: str | None = None,
        table: str | None = None,
        routine: str | None = None,
        routine_type: str | None = None,
    ) -> None:
        """Descarta los metadatos leídos (snapshots del catálogo y DDL de tablas).

        Sin argumentos, todos. Con argumentos, los del schema del contexto (``context_database`` o el del manager):
        los metadatos se leen por schema, así que ``table``/``routine`` descartan también el resto del schema.
        ``routine_type`` se acepta por compatibilidad y no cambia nada.
        """
        del routine_type
        if context_database is None and table is None and routine is None:
            self._invalidate_catalog()
            return
        self._invalidate_catalog(str(context_database or self._get_query_context_database() or ""))

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

    def get_query_context_database(self) -> str:
        """Expone el contexto de metadatos (schema/database) para consumidores externos."""
        return self._get_query_context_database()

    # ------------------------------------------------------------------
    # Result parsing helpers
    # ------------------------------------------------------------------
