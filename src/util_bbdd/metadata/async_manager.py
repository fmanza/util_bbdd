"""Gestor centralizado de operaciones de metadatos (variante asíncrona).

Responsabilidad: Coordinar y orquestar operaciones de metadatos
utilizando Builder, Cache y Normalizer sobre un `AsyncMetadataProvider` real
(p.ej. `AsyncDatabaseManager`). Espejo async de `MetadataManager`.
"""

import logging

from typing import Any

from .builder import DDLBuilder
from .cache import DatabaseMetadataCache, RelationshipMetadataCache
from .contracts import AsyncMetadataProvider, Rows
from .normalizer import (
    NormalizedColumnRow,
    NormalizedTableRow,
    normalize_column_rows,
    normalize_table_rows,
)


class AsyncMetadataManager:
    """Gestor centralizado de operaciones de metadatos, variante asíncrona.

    Orquesta las operaciones entre:
    - Builder: Construcción DDL
    - metadata_provider: Obtención de metadatos (p.ej. `AsyncDatabaseManager`)
    - Cache: Cacheo de resultados
    - Normalizer: Normalización de respuestas

    Responsabilidad única: Coordinar acceso a metadatos con cache y normalización.
    """

    def __init__(
        self,
        metadata_provider: AsyncMetadataProvider,
        db_cache: DatabaseMetadataCache | None = None,
        relationship_cache: RelationshipMetadataCache | None = None,
        db_type: str = "mariadb",
    ):
        """Inicializa gestor de metadatos.

        Args:
            metadata_provider: Proveedor de metadatos (ej: AsyncDatabaseManager)
            db_cache: Cache de metadatos (crea default si None)
            relationship_cache: Cache de relaciones (crea default si None)
            db_type: Tipo de BD (mariadb, postgresql, oracle, etc.)
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.metadata_provider: AsyncMetadataProvider = metadata_provider
        self.db_type: str = db_type.lower()

        # Cache
        self.db_cache: DatabaseMetadataCache = db_cache or DatabaseMetadataCache()
        self.relationship_cache: RelationshipMetadataCache = relationship_cache or RelationshipMetadataCache(
            self.db_cache
        )

        # Constructor DDL
        self.builder = DDLBuilder(db_type=db_type)

        self.logger.debug(f"✅ AsyncMetadataManager inicializado para {db_type}")

    # ========================================================================
    # Operaciones de Alto Nivel
    # ========================================================================

    async def get_tables(self, use_cache: bool = True) -> Rows:
        """Obtiene lista de tablas con cache opcional.

        Args:
            use_cache: Si True, usa cache; si False, consulta BD

        Returns:
            Lista de tablas
        """
        cache_key = "tables"

        if use_cache:
            cached = self.db_cache._tables_cache.get(cache_key)
            if cached is not None:
                self.logger.debug("📦 Tablas obtenidas desde cache")
                return cached

        # Obtener del provider
        tables = await self.metadata_provider.get_tables()

        # Cachear
        self.db_cache._tables_cache[cache_key] = tables
        self.logger.debug(f"💾 {len(tables)} tablas cacheadas")

        return tables

    async def get_columns(self, table_name: str, use_cache: bool = True) -> Rows:
        """Obtiene columnas de tabla.

        Args:
            table_name: Nombre de tabla
            use_cache: Si True, usa cache

        Returns:
            Lista de columnas
        """
        table_key = ("default", table_name)

        if use_cache:
            cached = self.db_cache.get_columns(table_key)
            if cached is not None:
                return cached

        # Obtener del provider
        columns = await self.metadata_provider.get_columns(table_name)

        # Cachear
        self.db_cache.set_columns(table_key, columns)

        return columns

    async def get_primary_keys(self, table_name: str, use_cache: bool = True) -> Rows:
        """Obtiene claves primarias de tabla.

        Args:
            table_name: Nombre de tabla
            use_cache: Si True, usa cache

        Returns:
            Lista de PKs
        """
        table_key = ("default", table_name)

        if use_cache:
            cached = self.db_cache.get_primary_keys(table_key)
            if cached is not None:
                return cached

        # Obtener del provider
        pks = await self.metadata_provider.get_primary_keys(table_name)

        # Cachear
        self.db_cache.set_primary_keys(table_key, pks)

        return pks

    async def get_indices(self, table_name: str, use_cache: bool = True) -> Rows:
        """Obtiene índices de tabla.

        Args:
            table_name: Nombre de tabla
            use_cache: Si True, usa cache

        Returns:
            Lista de índices
        """
        table_key = ("default", table_name)

        if use_cache:
            cached = self.db_cache.get_indices(table_key)
            if cached is not None:
                return cached

        indices = await self.metadata_provider.get_indices(table_name)
        self.db_cache.set_indices(table_key, indices)

        return indices

    async def get_foreign_keys(self, table_name: str, use_cache: bool = True) -> Rows:
        """Obtiene claves foráneas de tabla.

        Args:
            table_name: Nombre de tabla
            use_cache: Si True, usa cache

        Returns:
            Lista de FKs
        """
        table_key = ("default", table_name)

        if use_cache:
            cached = self.db_cache.get_foreign_keys(table_key)
            if cached is not None:
                return cached

        fks = await self.metadata_provider.get_foreign_keys(table_name)
        self.db_cache.set_foreign_keys(table_key, fks)

        return fks

    async def get_unique_constraints(self, table_name: str, use_cache: bool = True) -> Rows:
        """Obtiene constraints únicos de tabla.

        Args:
            table_name: Nombre de tabla
            use_cache: Si True, usa cache

        Returns:
            Lista de UCs
        """
        table_key = ("default", table_name)

        if use_cache:
            cached = self.db_cache.get_unique_constraints(table_key)
            if cached is not None:
                return cached

        ucs = await self.metadata_provider.get_unique_constraints(table_name)
        self.db_cache.set_unique_constraints(table_key, ucs)

        return ucs

    # ========================================================================
    # Operaciones Normalizadas
    # ========================================================================

    async def get_tables_normalized(self) -> list[NormalizedTableRow]:
        """Obtiene tablas normalizadas.

        Returns:
            Lista de tablas normalizadas
        """
        tables = await self.get_tables()
        return normalize_table_rows(tables)

    async def get_columns_normalized(self, table_name: str) -> list[NormalizedColumnRow]:
        """Obtiene columnas normalizadas.

        Args:
            table_name: Nombre de tabla

        Returns:
            Lista de columnas normalizadas
        """
        columns: Rows = await self.get_columns(table_name)
        return normalize_column_rows(columns)

    # ========================================================================
    # Operaciones de DDL
    # ========================================================================

    async def get_ddl(self, table_name: str, use_cache: bool = True) -> str:
        """Obtiene DDL de tabla.

        Args:
            table_name: Nombre de tabla
            use_cache: Si True, usa cache

        Returns:
            Sentencia DDL CREATE TABLE
        """
        table_key = ("default", table_name)

        if use_cache:
            cached_ddl = self.db_cache._ddl_cache.get(table_key)
            if cached_ddl:
                return cached_ddl

        # Construir desde metadatos
        columns: Rows = await self.get_columns(table_name)
        pks_rows: Rows = await self.get_primary_keys(table_name)

        # Extraer nombres de PK
        pk_names: list[str] = []
        if pks_rows:
            pk_names = [row[0] for row in pks_rows if row]

        # Construir DDL
        ddl: str = self.builder.build_create_table_from_columns(
            table_name,
            columns,
            primary_keys=pk_names or None,
        )

        # Cachear
        if ddl:
            self.db_cache._ddl_cache[table_key] = ddl

        return ddl

    # ========================================================================
    # Vistas y Routinas
    # ========================================================================

    async def get_views(self) -> Rows:
        """Obtiene lista de vistas."""
        return await self.metadata_provider.get_views()

    async def get_routines(self) -> Rows:
        """Obtiene lista de rutinas."""
        return await self.metadata_provider.get_routines()

    # ========================================================================
    # Gestión de Cache
    # ========================================================================

    def clear_cache(self, table_name: str | None = None) -> None:
        """Limpia cache de metadatos.

        Args:
            table_name: Si se proporciona, solo limpia cache de esa tabla
        """
        if table_name:
            self.db_cache.clear_by_table("default", table_name)
            self.relationship_cache.clear_by_table(table_name)
            self.logger.info(f"🧹 Cache limpiado para tabla: {table_name}")
        else:
            self.db_cache.clear_all()
            self.relationship_cache.clear_all()
            self.logger.info("🧹 Todo cache limpiado")

    def get_cache_stats(self) -> dict[str, Any]:
        """Retorna estadísticas de cache.

        Returns:
            Dict con estadísticas
        """
        return {
            "db_cache": self.db_cache.get_cache_stats(),
            "relationship_cache": self.relationship_cache.get_cache_stats(),
        }
