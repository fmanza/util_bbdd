"""Gestión centralizada de cachés de metadata con logging consistente (patrón: Manager)."""

from __future__ import annotations

import logging

from typing import Any

from ..metadata import DatabaseMetadataCache, RelationshipMetadataCache
from ._metadata_context import CacheKeyFactory


class CacheManager:
    """Gestiona todas las cachés de metadata con logging consistente y Error handling.

    Centraliza la lógica de invalidación de cachés, proporcionando un punto único
    para auditoría, debugging y control de coherencia de caché.
    """

    def __init__(
        self,
        *,
        db_cache: DatabaseMetadataCache,
        relationship_cache: RelationshipMetadataCache,
        logger: logging.Logger,
    ):
        """Inicializa el manager de cachés.

        Args:
            db_cache: Caché de metadata de BD
            relationship_cache: Caché de relaciones
            logger: Logger para auditoría de operaciones de caché
        """
        self.db_cache: DatabaseMetadataCache = db_cache
        self.relationship_cache: RelationshipMetadataCache = relationship_cache
        self.logger: logging.Logger = logger

    def clear_all(self) -> None:
        """Limpia todas las cachés de metadata y relaciones.

        Raises:
            Exception: Si hay error limpiando cachés (logged)
        """
        self.logger.info("🧹 Iniciando limpieza completa de todas las cachés de metadatos")
        try:
            self.db_cache.clear_all()
            self.relationship_cache.clear_all()
            self.logger.info("✅ Todas las cachés de metadatos limpiadas completamente")
        except Exception as error:
            self.logger.error(f"❌ Error limpiando cachés: {error}", exc_info=True)
            raise

    def clear_table(self, *, context: str, table: str) -> None:
        """Limpia la caché asociada a una tabla o vista.

        Args:
            context: Contexto (schema/database)
            table: Nombre de tabla

        Raises:
            Exception: Si hay error limpiando caché de tabla (logged)
        """
        self.logger.debug(f"Limpiando caché de tabla: {table} ({context})")
        try:
            self.db_cache.clear_by_table(context, table)
            self.relationship_cache.clear_by_table(table, context=context)
            self.logger.info(f"✅ Caché invalidada para tabla/vista {table} ({context})")
        except Exception as error:
            self.logger.error(f"❌ Error limpiando caché de tabla {table}: {error}", exc_info=True)
            raise

    def clear_routine(
        self,
        *,
        context: str,
        routine: str,
        routine_type: str | None = None,
    ) -> None:
        """Limpia la caché asociada a una rutina concreta.

        Args:
            context: Contexto (schema/database)
            routine: Nombre de rutina
            routine_type: Tipo de rutina (PROCEDURE, FUNCTION, etc.) - opcional

        Raises:
            Exception: Si hay error limpiando caché de rutina (logged)
        """
        self.logger.debug(f"Limpiando caché de rutina: {routine} ({context}, type={routine_type})")
        try:
            self.db_cache._routine_metadata_context_cache.pop(context, None)
            self.db_cache._routine_parameters_context_cache.pop(context, None)

            if routine_type:
                routine_key: tuple[str, str, str] = CacheKeyFactory.routine_key(context, routine, routine_type)
                self.db_cache._routine_parameters_cache.pop(routine_key, None)
                self.db_cache._routine_ddl_cache.pop(routine_key, None)
                self.logger.debug(f"Removida clave específica: {routine_key}")
            else:
                # Limpiar todas las rutinas con mismo nombre en el contexto
                param_keys: list[tuple[str, str, str]] = [
                    key
                    for key in self.db_cache._routine_parameters_cache
                    if key and len(key) >= 2 and key[0] == context and key[1] == routine
                ]
                ddl_keys: list[tuple[str, str, str]] = [
                    key
                    for key in self.db_cache._routine_ddl_cache
                    if key and len(key) >= 2 and key[0] == context and key[1] == routine
                ]

                for cache_key in param_keys:
                    self.db_cache._routine_parameters_cache.pop(cache_key, None)
                for cache_key in ddl_keys:
                    self.db_cache._routine_ddl_cache.pop(cache_key, None)

                self.logger.debug(f"Removidas {len(param_keys) + len(ddl_keys)} claves de rutina genéricas")

            self.logger.info(f"✅ Caché invalidada para rutina {routine} ({context})")
        except Exception as error:
            self.logger.error(f"❌ Error limpiando caché de rutina {routine}: {error}", exc_info=True)
            raise

    def clear_context(self, *, context: str) -> None:
        """Limpia todas las entradas de caché asociadas a un contexto.

        Args:
            context: Contexto (schema/database) a limpiar

        Raises:
            Exception: Si hay error limpiando caché de contexto (logged)
        """
        self.logger.debug(f"Limpiando caché de contexto: {context}")
        try:
            # Limpiar cachés por contexto (simples)
            context_caches: tuple[dict[str, Any], ...] = (
                self.db_cache._tables_cache,
                self.db_cache._views_cache,
                self.db_cache._routines_cache,
                self.db_cache._routine_metadata_context_cache,
                self.db_cache._routine_parameters_context_cache,
            )
            for context_cache in context_caches:
                context_cache.pop(context, None)

            # Limpiar cachés por tupla (composición)
            tuple_caches: tuple[dict[tuple[Any, ...], Any], ...] = (
                self.db_cache._primary_keys_cache,
                self.db_cache._indices_cache,
                self.db_cache._foreign_keys_cache,
                self.db_cache._unique_constraints_cache,
                self.db_cache._columns_cache,
                self.db_cache._ddl_cache,
                self.db_cache._view_ddl_cache,
                self.db_cache._routine_parameters_cache,
                self.db_cache._routine_ddl_cache,
            )

            total_removed = 0
            for tuple_cache in tuple_caches:
                keys_to_remove: list[tuple[Any, ...]] = [key for key in tuple_cache if key and str(key[0]) == context]
                for cache_key in keys_to_remove:
                    tuple_cache.pop(cache_key, None)
                total_removed += len(keys_to_remove)

            self.logger.info(f"✅ Caché invalidada para contexto: {context} ({total_removed} tuplas removidas)")
        except Exception as error:
            self.logger.error(f"❌ Error limpiando caché de contexto {context}: {error}", exc_info=True)
            raise


__all__: list[str] = [
    "CacheManager",
]
