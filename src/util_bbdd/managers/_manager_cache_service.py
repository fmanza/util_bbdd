"""Servicio centralizado de caché para managers."""

from __future__ import annotations

import logging

from typing import Any

from ..metadata.cache import DatabaseMetadataCache, RelationshipMetadataCache
from ._metadata_cache import CacheManager
from ._metadata_context import CacheKeyFactory


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
        self.db_cache: DatabaseMetadataCache = db_cache
        self.relationship_cache: RelationshipMetadataCache = relationship_cache
        self.logger: logging.Logger = logger

    def _cache_manager(self) -> CacheManager:
        return CacheManager(db_cache=self.db_cache, relationship_cache=self.relationship_cache, logger=self.logger)

    def clear_all(self) -> None:
        """Limpia completamente todas las cachés."""
        self._cache_manager().clear_all()

    def clear_table(self, context: str, table: str) -> None:
        """Limpia caché para una tabla/vista específica."""
        self._cache_manager().clear_table(context=context, table=table)

    def clear_routine(self, context: str, routine: str, routine_type: str | None = None) -> None:
        """Limpia caché para una rutina específica."""
        self._cache_manager().clear_routine(context=context, routine=routine, routine_type=routine_type)

    def clear_context(self, context: str) -> None:
        """Limpia caché para un contexto/schema específico."""
        self._cache_manager().clear_context(context=context)

    @staticmethod
    def clear_tuple_cache_by_context(cache: dict[tuple[Any, ...], Any], context: str) -> None:
        """Limpia caché tuple para un contexto específico."""
        keys_to_remove: list[tuple[Any, ...]] = [key for key in cache if key and str(key[0]) == context]
        for cache_key in keys_to_remove:
            cache.pop(cache_key, None)

    @staticmethod
    def get_context_key(context: str) -> str:
        """Genera clave de caché para contexto."""
        return CacheKeyFactory.context_key(context)

    @staticmethod
    def get_table_key(context_database: str, table_name: str) -> tuple[str, str]:
        """Genera clave de caché para tabla."""
        return CacheKeyFactory.table_key(context_database, table_name)

    @staticmethod
    def get_routine_key(context_database: str, routine_name: str, routine_type: str) -> tuple[str, str, str]:
        """Genera clave de caché para rutina."""
        return CacheKeyFactory.routine_key(context_database, routine_name, routine_type)


__all__: list[str] = ["CacheService"]
