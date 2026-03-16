"""
Centralización de todas las cachés de metadatos de base de datos.
Separa responsabilidades entre metadatos BD puros vs análisis de relaciones.

Patrón: Composición Jerárquica
- DatabaseMetadataCache: Única fuente de verdad para metadatos BD (12 cachés)
- RelationshipMetadataCache: Análisis derivados (4 cachés) + referencia a DB cache
"""

import logging


class DatabaseMetadataCache:
    """Cachés de metadatos puros de base de datos.

    Responsabilidad única: Almacenar metadatos obtenidos directamente de BD
    (tablas, vistas, rutinas, columnas, índices, DDL, etc.)

    Esta es la **única fuente de verdad** para datos de BD.
    """

    def __init__(self):
        """Inicializa cachés de metadatos de base de datos."""
        self.logger: logging.Logger = logging.getLogger(__name__)

        # Cachés de listados principales (por contexto)
        self._tables_cache: dict[str, list] = {}
        self._views_cache: dict[str, list] = {}
        self._routines_cache: dict[str, list] = {}
        self._routine_metadata_context_cache: dict[str, list] = {}
        self._routine_parameters_context_cache: dict[str, list] = {}

        # Cachés de metadatos de tabla (context, tabla) -> datos
        self._primary_keys_cache: dict[tuple[str, str], list] = {}
        self._indices_cache: dict[tuple[str, str], list] = {}
        self._foreign_keys_cache: dict[tuple[str, str], list] = {}
        self._unique_constraints_cache: dict[tuple[str, str], list] = {}
        self._columns_cache: dict[tuple[str, str], list] = {}
        self._columns_charset_collation_cache: dict[tuple[str, str], list] = {}

        # Cachés de DDL
        self._ddl_cache: dict[tuple[str, str], str] = {}
        self._view_ddl_cache: dict[tuple[str, str], str] = {}

        # Cachés de rutinas (context, rutina, tipo_rutina) -> datos
        self._routine_parameters_cache: dict[tuple[str, str, str], list] = {}
        self._routine_ddl_cache: dict[tuple[str, str, str], str] = {}

        self.logger.debug("✅ DatabaseMetadataCache inicializado")

    def get_primary_keys(self, table_key: tuple[str, str]) -> list | None:
        """Obtiene PKs del caché de BD."""
        return self._primary_keys_cache.get(table_key)

    def set_primary_keys(self, table_key: tuple[str, str], pks: list) -> None:
        """Guarda PKs en caché de BD."""
        self._primary_keys_cache[table_key] = list(pks)

    def get_unique_constraints(self, table_key: tuple[str, str]) -> list | None:
        """Obtiene UCs del caché de BD."""
        return self._unique_constraints_cache.get(table_key)

    def set_unique_constraints(self, table_key: tuple[str, str], ucs: list) -> None:
        """Guarda UCs en caché de BD."""
        self._unique_constraints_cache[table_key] = list(ucs)

    def get_columns(self, table_key: tuple[str, str]) -> list | None:
        """Obtiene columnas del caché de BD."""
        return self._columns_cache.get(table_key)

    def set_columns(self, table_key: tuple[str, str], columns: list) -> None:
        """Guarda columnas en caché de BD."""
        self._columns_cache[table_key] = list(columns)

    def get_indices(self, table_key: tuple[str, str]) -> list | None:
        """Obtiene índices del caché de BD."""
        return self._indices_cache.get(table_key)

    def set_indices(self, table_key: tuple[str, str], indices: list) -> None:
        """Guarda índices en caché de BD."""
        self._indices_cache[table_key] = list(indices)

    def get_foreign_keys(self, table_key: tuple[str, str]) -> list | None:
        """Obtiene FKs del caché de BD."""
        return self._foreign_keys_cache.get(table_key)

    def set_foreign_keys(self, table_key: tuple[str, str], fks: list) -> None:
        """Guarda FKs en caché de BD."""
        self._foreign_keys_cache[table_key] = list(fks)

    def get_columns_charset_collation(self, table_key: tuple[str, str]) -> list | None:
        """Obtiene charset/collation de columnas del caché de BD."""
        return self._columns_charset_collation_cache.get(table_key)

    def set_columns_charset_collation(self, table_key: tuple[str, str], charset_collation: list) -> None:
        """Guarda charset/collation de columnas en caché de BD."""
        self._columns_charset_collation_cache[table_key] = list(charset_collation)

    def clear_all(self) -> None:
        """Limpia completamente todos los cachés de BD."""
        self._tables_cache.clear()
        self._views_cache.clear()
        self._routines_cache.clear()
        self._routine_metadata_context_cache.clear()
        self._routine_parameters_context_cache.clear()
        self._primary_keys_cache.clear()
        self._indices_cache.clear()
        self._foreign_keys_cache.clear()
        self._unique_constraints_cache.clear()
        self._columns_cache.clear()
        self._columns_charset_collation_cache.clear()
        self._ddl_cache.clear()
        self._view_ddl_cache.clear()
        self._routine_parameters_cache.clear()
        self._routine_ddl_cache.clear()
        self.logger.info("🧹 DatabaseMetadataCache limpiado completamente")

    def clear_by_table(self, context: str, table: str) -> None:
        """Invalida cachés para tabla específica."""
        table_key: tuple[str, str] = (context, table)
        self._primary_keys_cache.pop(table_key, None)
        self._indices_cache.pop(table_key, None)
        self._foreign_keys_cache.pop(table_key, None)
        self._unique_constraints_cache.pop(table_key, None)
        self._columns_cache.pop(table_key, None)
        self._columns_charset_collation_cache.pop(table_key, None)
        self._ddl_cache.pop(table_key, None)
        self._view_ddl_cache.pop(table_key, None)
        self.logger.debug(f"🧹 DatabaseMetadataCache invalidado para {table}")

    def get_cache_stats(self) -> dict[str, int]:
        """Retorna estadísticas de cachés de BD."""
        return {
            "tables": len(self._tables_cache),
            "views": len(self._views_cache),
            "routines": len(self._routines_cache),
            "routine_metadata_context": len(self._routine_metadata_context_cache),
            "routine_parameters_context": len(self._routine_parameters_context_cache),
            "primary_keys": len(self._primary_keys_cache),
            "indices": len(self._indices_cache),
            "foreign_keys": len(self._foreign_keys_cache),
            "unique_constraints": len(self._unique_constraints_cache),
            "columns": len(self._columns_cache),
            "columns_charset_collation": len(self._columns_charset_collation_cache),
            "ddl": len(self._ddl_cache),
            "view_ddl": len(self._view_ddl_cache),
            "routine_parameters": len(self._routine_parameters_cache),
            "routine_ddl": len(self._routine_ddl_cache),
            "total_entries": (
                len(self._tables_cache)
                + len(self._views_cache)
                + len(self._routines_cache)
                + len(self._routine_metadata_context_cache)
                + len(self._routine_parameters_context_cache)
                + len(self._primary_keys_cache)
                + len(self._indices_cache)
                + len(self._foreign_keys_cache)
                + len(self._unique_constraints_cache)
                + len(self._columns_cache)
                + len(self._columns_charset_collation_cache)
                + len(self._ddl_cache)
                + len(self._view_ddl_cache)
                + len(self._routine_parameters_cache)
                + len(self._routine_ddl_cache)
            ),
        }


class RelationshipMetadataCache:
    """Cachés de análisis de relaciones entre tablas.

    Responsabilidad única: Almacenar resultados de análisis de relaciones
    (cardinalidades, checks PK/UK) que se DERIVAN de DatabaseMetadataCache.

    No duplica datos: referencia la caché de BD como autoridad única mediante
    inyección de dependencia en constructor.
    """

    def __init__(self, db_cache: DatabaseMetadataCache | None = None):
        """Inicializa cachés de análisis de relaciones.

        Args:
            db_cache: Referencia a DatabaseMetadataCache (inyección de dependencia)
                     Si es None, se crea una nueva instancia (legacy compatibility)
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.db_cache: DatabaseMetadataCache = db_cache or DatabaseMetadataCache()

        # Cachés de análisis (NO duplican datos, solo resultados derivados)
        self._cardinality_cache: dict[tuple[str, str, str, str], str] = {}
        self._is_pk_cache: dict[tuple[str, str], bool] = {}
        self._is_uk_cache: dict[tuple[str, str], bool] = {}
        self._table_columns_typed_cache: dict[str, list[tuple[str, str]]] = {}

        self.logger.debug("✅ RelationshipMetadataCache inicializado")

    def get_primary_keys_list(self, table_key: tuple[str, str]) -> list | None:
        """Obtiene PKs desde caché de BD (ÚNICA FUENTE DE VERDAD).

        Esta es la única vía de acceso a PKs para asegurar coherencia.
        RelationshipMetadataCache NO duplica datos de BD, solo analiza.
        """
        return self.db_cache.get_primary_keys(table_key)

    def set_primary_keys_list(self, table_key: tuple[str, str], pks: list) -> None:
        """Guarda PKs en caché de BD centralizada."""
        self.db_cache.set_primary_keys(table_key, pks)

    def get_unique_constraints_list(self, table_key: tuple[str, str]) -> list | None:
        """Obtiene UCs desde caché de BD (ÚNICA FUENTE DE VERDAD)."""
        return self.db_cache.get_unique_constraints(table_key)

    def set_unique_constraints_list(self, table_key: tuple[str, str], ucs: list) -> None:
        """Guarda UCs en caché de BD centralizada."""
        self.db_cache.set_unique_constraints(table_key, ucs)

    def get_cardinality(self, source_col: str, target_col: str, source_table: str, target_table: str) -> str | None:
        """Obtiene cardinalidad del caché de análisis."""
        key: tuple[str, str, str, str] = (source_col, target_col, source_table, target_table)
        return self._cardinality_cache.get(key)

    def set_cardinality(
        self,
        source_col: str,
        target_col: str,
        source_table: str,
        target_table: str,
        cardinality: str,
    ) -> None:
        """Guarda cardinalidad en caché de análisis."""
        key: tuple[str, str, str, str] = (source_col, target_col, source_table, target_table)
        self._cardinality_cache[key] = cardinality

    def get_is_primary_key(self, table_name: str, column_name: str) -> bool | None:
        """Obtiene resultado de check PK del caché de análisis."""
        key: tuple[str, str] = (table_name, column_name)
        return self._is_pk_cache.get(key)

    def set_is_primary_key(self, table_name: str, column_name: str, is_pk: bool) -> None:
        """Guarda resultado de check PK en caché de análisis."""
        key: tuple[str, str] = (table_name, column_name)
        self._is_pk_cache[key] = is_pk

    def get_is_unique_column(self, table_name: str, column_name: str) -> bool | None:
        """Obtiene resultado de check UK del caché de análisis."""
        key: tuple[str, str] = (table_name, column_name)
        return self._is_uk_cache.get(key)

    def set_is_unique_column(self, table_name: str, column_name: str, is_uk: bool) -> None:
        """Guarda resultado de check UK en caché de análisis."""
        key: tuple[str, str] = (table_name, column_name)
        self._is_uk_cache[key] = is_uk

    def get_table_columns_typed(self, table_name: str) -> list[tuple[str, str]] | None:
        """Obtiene columnas tipadas de tabla del caché."""
        return self._table_columns_typed_cache.get(table_name)

    def set_table_columns_typed(self, table_name: str, columns: list[tuple[str, str]]) -> None:
        """Guarda columnas tipadas de tabla en caché."""
        self._table_columns_typed_cache[table_name] = list(columns)

    def clear_all(self) -> None:
        """Limpia cachés de análisis (NOT de BD)."""
        self._cardinality_cache.clear()
        self._is_pk_cache.clear()
        self._is_uk_cache.clear()
        self._table_columns_typed_cache.clear()
        self.logger.info("🧹 RelationshipMetadataCache limpiado completamente")

    def clear_by_table(self, table_name: str) -> None:
        """Invalida cachés de análisis para tabla específica."""
        # Limpiar cardinalidades que involucren esta tabla
        keys_to_remove: list[tuple[str, str, str, str]] = [
            key for key in self._cardinality_cache if key[2] == table_name or key[3] == table_name
        ]
        for key in keys_to_remove:
            self._cardinality_cache.pop(key, None)

        # Limpiar checks PK/UK de columnas de tabla
        pk_keys: list[tuple[str, str]] = [key for key in self._is_pk_cache if key[0] == table_name]
        for key in pk_keys:
            self._is_pk_cache.pop(key, None)

        uk_keys: list[tuple[str, str]] = [key for key in self._is_uk_cache if key[0] == table_name]
        for key in uk_keys:
            self._is_uk_cache.pop(key, None)

        # Limpiar columnas tipadas
        self._table_columns_typed_cache.pop(table_name, None)

        self.logger.debug(f"🧹 RelationshipMetadataCache invalidado para tabla: {table_name}")

    def get_cache_stats(self) -> dict[str, int]:
        """Retorna estadísticas de cachés de análisis."""
        return {
            "cardinality_entries": len(self._cardinality_cache),
            "pk_checks": len(self._is_pk_cache),
            "uk_checks": len(self._is_uk_cache),
            "table_columns": len(self._table_columns_typed_cache),
            "total_entries": (
                len(self._cardinality_cache)
                + len(self._is_pk_cache)
                + len(self._is_uk_cache)
                + len(self._table_columns_typed_cache)
            ),
        }
