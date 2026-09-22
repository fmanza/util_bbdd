"""Gestión centralizada de cachés de metadata con logging consistente (patrón: Manager)."""

from __future__ import annotations

import logging

from ..metadata import DatabaseMetadataCache, RelationshipMetadataCache


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
            # MGR-03 (AUDIT_CODE 2026-09-22): delega en la API pública de
            # DatabaseMetadataCache en vez de acceder a sus atributos privados
            # por nombre hardcodeado.
            self.db_cache.clear_by_routine(context, routine, routine_type)
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
            # MGR-03 (AUDIT_CODE 2026-09-22): delega en la API pública de
            # DatabaseMetadataCache en vez de acceder a sus atributos privados
            # por nombre hardcodeado.
            total_removed = self.db_cache.clear_by_context(context)
            self.logger.info(f"✅ Caché invalidada para contexto: {context} ({total_removed} tuplas removidas)")
        except Exception as error:
            self.logger.error(f"❌ Error limpiando caché de contexto {context}: {error}", exc_info=True)
            raise


__all__: list[str] = [
    "CacheManager",
]
