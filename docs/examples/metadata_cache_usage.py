"""
Metadata Cache Usage - cachear metadatos sin consultar la BD repetidamente.

Este ejemplo usa la API publica de DatabaseMetadataCache. No depende de un
motor externo: el loader simula la lectura de metadatos que normalmente haria
SyncDatabaseManager.get_columns(), get_primary_keys() o get_foreign_keys().
"""

from collections.abc import Callable
from typing import Any

from util_bbdd.metadata import DatabaseMetadataCache, RelationshipMetadataCache

TableKey = tuple[str, str]


def load_columns_from_database() -> list[dict[str, Any]]:
    """Simula una consulta de metadatos a la base de datos."""
    print("Cache MISS: leyendo columnas desde la BD")
    return [
        {"name": "id", "type": "INTEGER", "nullable": False},
        {"name": "name", "type": "TEXT", "nullable": False},
        {"name": "price", "type": "REAL", "nullable": True},
    ]


def get_columns_cached(
    cache: DatabaseMetadataCache,
    table_key: TableKey,
    loader: Callable[[], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Devuelve columnas desde cache o las carga si aun no existen."""
    cached_columns = cache.get_columns(table_key)
    if cached_columns is not None:
        print("Cache HIT: columnas recuperadas desde memoria")
        return cached_columns

    columns = loader()
    cache.set_columns(table_key, columns)
    return columns


def demonstrate_metadata_cache_usage() -> None:
    """Demuestra lectura, escritura, estadisticas e invalidacion de cache."""
    cache = DatabaseMetadataCache()
    relationship_cache = RelationshipMetadataCache(db_cache=cache)
    table_key = ("main", "products")

    columns = get_columns_cached(cache, table_key, load_columns_from_database)
    print(f"Columnas cargadas: {[column['name'] for column in columns]}")

    columns = get_columns_cached(cache, table_key, load_columns_from_database)
    print(f"Columnas cacheadas: {[column['name'] for column in columns]}")

    cache.set_primary_keys(table_key, ["id"])
    cache.set_foreign_keys(
        table_key,
        [
            {
                "constrained_columns": ["category_id"],
                "referred_table": "categories",
                "referred_columns": ["id"],
            }
        ],
    )

    primary_keys = cache.get_primary_keys(table_key)
    foreign_keys = cache.get_foreign_keys(table_key)
    relationship_cache.set_is_primary_key("products", "id", True)
    print(f"Clave primaria: {primary_keys}")
    print(f"Claves foraneas: {foreign_keys}")
    print(f"products.id es PK: {relationship_cache.get_is_primary_key('products', 'id')}")

    stats = cache.get_cache_stats()
    print(f"Entradas de columnas: {stats['columns']}")
    print(f"Entradas de claves primarias: {stats['primary_keys']}")
    print(f"Entradas de claves foraneas: {stats['foreign_keys']}")

    cache.clear_by_table("main", "products")
    print(f"Columnas tras invalidar tabla: {cache.get_columns(table_key)}")

    cache.clear_all()
    print(f"Entradas tras limpiar cache: {cache.get_cache_stats()['columns']}")


if __name__ == "__main__":
    demonstrate_metadata_cache_usage()
