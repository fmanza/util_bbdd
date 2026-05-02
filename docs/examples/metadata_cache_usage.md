# Uso de Cache de Metadatos

Ejemplo práctico para usar `DatabaseMetadataCache` y `RelationshipMetadataCache` con la API pública actual. El ejemplo evita motores externos: simula la carga inicial de metadatos y muestra cómo cachearlos, consultarlos, invalidarlos y revisar estadísticas.

## Objetivo funcional

- Reducir consultas repetidas de introspección sobre tablas conocidas.
- Reutilizar metadatos de columnas, claves primarias y claves foráneas durante una operación de documentación, comparación o validación.
- Invalidar el cache cuando una tabla cambia.

## API técnica usada

```python
from util_bbdd.metadata import DatabaseMetadataCache, RelationshipMetadataCache

cache = DatabaseMetadataCache()
table_key = ("main", "products")

cache.set_columns(table_key, [{"name": "id", "type": "INTEGER"}])
columns = cache.get_columns(table_key)

cache.set_primary_keys(table_key, ["id"])
primary_keys = cache.get_primary_keys(table_key)

cache.set_foreign_keys(table_key, [{"referred_table": "categories"}])
foreign_keys = cache.get_foreign_keys(table_key)

stats = cache.get_cache_stats()
cache.clear_by_table("main", "products")
cache.clear_all()
```

La clave del cache es una tupla `(contexto, tabla)`, por ejemplo `("main", "products")` en SQLite o `("public", "users")` en PostgreSQL.

## Ejemplo completo

```python
--8<-- "examples/metadata_cache_usage.py"
```

## Patrón get-or-cache

```python
from collections.abc import Callable
from typing import Any

from util_bbdd.metadata import DatabaseMetadataCache


def get_columns_cached(
    cache: DatabaseMetadataCache,
    table_key: tuple[str, str],
    loader: Callable[[], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    cached_columns = cache.get_columns(table_key)
    if cached_columns is not None:
        return cached_columns

    columns = loader()
    cache.set_columns(table_key, columns)
    return columns
```

## Invalidación

```python
cache.clear_by_table("main", "products")
```

Usa invalidación selectiva cuando una tabla se crea, modifica o elimina. Usa `clear_all()` cuando el contexto completo de metadatos deja de ser fiable.

## Estadísticas

```python
stats = cache.get_cache_stats()

print(stats["columns"])
print(stats["primary_keys"])
print(stats["foreign_keys"])
print(stats["indices"])
print(stats["unique_constraints"])
```

## Buenas prácticas

- Usa `get_columns`, `get_primary_keys`, `get_foreign_keys`, `get_indices` y `get_unique_constraints`; evita acceder a atributos privados.
- Usa `clear_by_table` y `clear_all` para invalidar cache.
- No documentes métodos de DDL en `DatabaseMetadataCache`: esta clase no expone `get_ddl`, `set_ddl`, `get_view_ddl` ni `set_view_ddl`.
- No asumas que el cache se actualiza solo después de cambios DDL.

!!! tip "Ver también"
    - [Guía Async](../ASYNC_GUIDE.md)
    - [API Reference](../API_REFERENCE.md)
    - [Ejemplo: Comparación de Esquemas](schema_comparison.md)
