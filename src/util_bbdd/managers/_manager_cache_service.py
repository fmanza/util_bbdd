"""Servicio centralizado de caché para managers."""

from __future__ import annotations

import logging

from typing import Any

from ..metadata.cache import DatabaseMetadataCache, RelationshipMetadataCache
from ._manager_metadata import (
    cache_context_key,
    cache_routine_key,
    cache_table_key,
    clear_all_caches,
    clear_context_cache,
    clear_routine_cache,
    clear_table_cache,
    clear_tuple_cache_by_context,
)


class CacheService:
    """Gestiona cachés de metadatos y relaciones para managers."""

    def __init__(
        self,
        db_cache: DatabaseMetadataCache,
        relationship_cache: RelationshipMetadataCache,
        logger: logging.Logger,
    ) -> None:
        """
        Inicializa el servicio de caché.

        Args:
            db_cache: Caché de metadatos de base de datos.
            relationship_cache: Caché de relaciones.
            logger: Logger para mensajes de debug/info.
        """
        self.db_cache = db_cache
        self.relationship_cache = relationship_cache
        self.logger = logger

    def clear_all(self) -> None:
        """Limpia completamente todas las cachés."""
        clear_all_caches(
            db_cache=self.db_cache,
            relationship_cache=self.relationship_cache,
            logger=self.logger,
        )

    def clear_table(self, context: str, table: str) -> None:
        """Limpia caché para una tabla/vista específica."""
        clear_table_cache(
            db_cache=self.db_cache,
            relationship_cache=self.relationship_cache,
            logger=self.logger,
            context=context,
            table=table,
        )

    def clear_routine(self, context: str, routine: str, routine_type: str | None = None) -> None:
        """Limpia caché para una rutina específica."""
        clear_routine_cache(
            db_cache=self.db_cache,
            logger=self.logger,
            context=context,
            routine=routine,
            routine_type=routine_type,
        )

    def clear_context(self, context: str) -> None:
        """Limpia caché para un contexto/schema específico."""
        clear_context_cache(db_cache=self.db_cache, logger=self.logger, context=context)

    @staticmethod
    def clear_tuple_cache_by_context(cache: dict[tuple[Any, ...], Any], context: str) -> None:
        """Limpia caché tuple para un contexto específico."""
        clear_tuple_cache_by_context(cache, context)

    @staticmethod
    def get_context_key(context: str) -> str:
        """Genera clave de caché para contexto."""
        return cache_context_key(context)

    @staticmethod
    def get_table_key(context_database: str, table_name: str) -> tuple[str, str]:
        """Genera clave de caché para tabla."""
        return cache_table_key(context_database, table_name)

    @staticmethod
    def get_routine_key(context_database: str, routine_name: str, routine_type: str) -> tuple[str, str, str]:
        """Genera clave de caché para rutina."""
        return cache_routine_key(context_database, routine_name, routine_type)


__all__ = ["CacheService"]
