# Uso de Cache de Metadatos

Ejemplo que demuestra cómo usar `DatabaseMetadataCache` para almacenar metadatos en memoria y mejorar performance.

**Cubre:**

- Crear instancia de `DatabaseMetadataCache`
- Guardar y recuperar metadatos del cache
- Pre-cargar cache con múltiples tablas
- Usar cache en lógica de aplicación
- Invalidar cache cuando schema cambia
- Monitorear estadísticas del cache

---

## Motivación: Performance

**Sin cache (query cada vez):**
```
get_table_columns("public", "users")  → Query DB  (~50ms)
get_table_columns("public", "users")  → Query DB  (~50ms)  ❌ Redundante
get_table_columns("public", "users")  → Query DB  (~50ms)  ❌ Redundante
```

**Con cache (query 1ª vez, luego cache):**
```
get_table_columns("public", "users")  → Query DB  (~50ms)  [Cachear]
get_table_columns("public", "users")  → Del cache (~1ms)   ✅ 50x más rápido
get_table_columns("public", "users")  → Del cache (~1ms)   ✅ 50x más rápido
```

---

## Estructura del Cache

```python
from util_bbdd.metadata import DatabaseMetadataCache

cache = DatabaseMetadataCache()

# Cachés principales (por contexto/tabla)
cache.get_columns(("public", "users"))           # → list[dict]
cache.get_primary_keys(("public", "users"))      # → list[dict]
cache.get_foreign_keys(("public", "users"))      # → list[dict]
cache.get_indices(("public", "users"))           # → list[dict]
cache.get_unique_constraints(("public", "users")) # → list[dict]

# Cachés de DDL
cache.get_ddl(("public", "users"))        # → str (CREATE TABLE ...)
cache.get_view_ddl(("public", "my_view")) # → str (CREATE VIEW ...)
```

**Clave del cache:** `(schema: str, table/view: str)`

---

## Ejemplo Completo

```python
--8<-- "examples/metadata_cache_usage.py"
```

---

## Patrones Comunes

### Patrón 1: Get-or-Cache

```python
def get_table_metadata_cached(
    manager,
    cache: DatabaseMetadataCache,
    schema: str,
    table: str
) -> list[dict]:
    """Obtener columnas: del cache si existe, de BD si no."""

    key = (schema, table)

    # Intentar cache primero
    cached = cache.get_columns(key)
    if cached is not None:
        return cached

    # No en cache: obtener de BD y cachear
    columns = manager.get_table_columns(schema=schema, table=table)
    cache.set_columns(key, columns)
    return columns
```

### Patrón 2: Pre-carga en Startup

```python
async def preload_cache(manager, cache: DatabaseMetadataCache):
    """Pre-cargar cache con metadatos al iniciar aplicación."""

    print("Pre-cargando cache de metadatos...")

    tables = manager.get_tables()
    for table in tables:
        schema = table["table_schema"]
        name = table["table_name"]
        key = (schema, name)

        # Cargar todos los metadatos de tabla
        cols = manager.get_table_columns(schema=schema, table=name)
        pks = manager.get_table_primary_keys(schema=schema, table=name)
        fks = manager.get_table_foreign_keys(schema=schema, table=name)
        indices = manager.get_table_indices(schema=schema, table=name)
        ddl = manager.get_table_ddl(schema=schema, table=name)

        # Guardar en cache
        cache.set_columns(key, cols)
        cache.set_primary_keys(key, pks)
        cache.set_foreign_keys(key, fks)
        cache.set_indices(key, indices)
        cache.set_ddl(key, ddl)

    print(f"✅ Pre-carga completada para {len(tables)} tablas")
```

### Patrón 3: Invalidación Selectiva

```python
def update_table_and_invalidate(
    manager,
    cache: DatabaseMetadataCache,
    schema: str,
    table: str,
    ddl: str
):
    """Ejecutar DDL e invalidar cache para esa tabla."""

    # Ejecutar cambio
    manager.execute_custom(ddl)

    # Invalidar cache
    key = (schema, table)
    cache.set_columns(key, None)
    cache.set_primary_keys(key, None)
    cache.set_foreign_keys(key, None)
    cache.set_indices(key, None)
    cache.set_ddl(key, None)

    print(f"✅ Tabla {schema}.{table} actualizada, cache invalidado")
```

### Patrón 4: Validación Rápida de Columnas

```python
def validate_schema_columns(
    manager,
    cache: DatabaseMetadataCache,
    schema: str,
    table: str,
    required_columns: list[str]
) -> bool:
    """Validar que columnas existen (usa cache)."""

    # Obtener columnas (cache si existe, BD si no)
    key = (schema, table)
    cols = cache.get_columns(key)

    if cols is None:
        cols = manager.get_table_columns(schema=schema, table=table)
        cache.set_columns(key, cols)

    # Validar
    available = {col["column_name"].lower() for col in cols}
    required = {c.lower() for c in required_columns}

    missing = required - available
    if missing:
        print(f"❌ Columnas faltantes: {missing}")
        return False

    print(f"✅ Todas las columnas presentes")
    return True
```

---

## Casos de Uso

### 1. Aplicación Web con ORM

```python
# FastAPI + SQLAlchemy
cache = DatabaseMetadataCache()

@app.on_event("startup")
async def startup():
    """Pre-cargar cache al iniciar servidor."""
    await preload_cache(db_manager, cache)

@app.get("/tables")
async def list_tables():
    """Listar tablas disponibles (cache hit después de startup)."""
    tables = db_manager.get_tables()  # Podría cachear esto también

    for table in tables:
        schema = table["table_schema"]
        name = table["table_name"]
        key = (schema, name)

        # Usar cache para obtener columnas
        cols = cache.get_columns(key)
        table["columns_count"] = len(cols) if cols else 0

    return tables
```

### 2. Herramienta de Comparación de Schemas

```python
# Comparar dos BD usando cache local
cache_source = DatabaseMetadataCache()
cache_target = DatabaseMetadataCache()

# Pre-cargar ambos caches
for cache, manager in [(cache_source, source_mgr), (cache_target, target_mgr)]:
    await preload_cache(manager, cache)

# Comparación rápida: todo desde cache
for schema, table in [(s, t) for s, t in all_tables]:
    key = (schema, table)

    source_cols = cache_source.get_columns(key)
    target_cols = cache_target.get_columns(key)

    if source_cols != target_cols:
        print(f"Schema diferente en {schema}.{table}")
```

### 3. Validación de Datos en Batch

```python
# Procesando CSV, validar estructura contra BD
cache = DatabaseMetadataCache()

def process_csv_with_validation(csv_path, schema, table, manager, cache):
    """Procesar CSV validando que columnas coinciden con tabla."""

    # Obtener columnas de tabla (cache si existe)
    key = (schema, table)
    table_cols = cache.get_columns(key)

    if table_cols is None:
        table_cols = manager.get_table_columns(schema=schema, table=table)
        cache.set_columns(key, table_cols)

    expected_cols = {c["column_name"] for c in table_cols}

    # Validar CSV
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        csv_cols = set(reader.fieldnames)

        if csv_cols != expected_cols:
            raise ValueError(f"CSV columns mismatch. Expected: {expected_cols}, got: {csv_cols}")

    # OK, procesar
    print(f"✅ CSV válido para {schema}.{table}")
```

---

## Monitoreo y Debugging

### Ver qué hay en el cache

```python
def print_cache_stats(cache: DatabaseMetadataCache):
    """Mostrar estadísticas del cache."""

    if hasattr(cache, "_columns_cache"):
        print(f"Tablas con columns: {len(cache._columns_cache)}")

    if hasattr(cache, "_primary_keys_cache"):
        print(f"Tablas con PKs: {len(cache._primary_keys_cache)}")

    if hasattr(cache, "_foreign_keys_cache"):
        print(f"Tablas con FKs: {len(cache._foreign_keys_cache)}")

    if hasattr(cache, "_ddl_cache"):
        print(f"Tablas con DDL: {len(cache._ddl_cache)}")
```

### Limpiar todo el cache

```python
def clear_cache(cache: DatabaseMetadataCache):
    """Limpiar completamente el cache."""

    # Acceso directo a privados (usar con cuidado)
    cache._columns_cache.clear()
    cache._primary_keys_cache.clear()
    cache._foreign_keys_cache.clear()
    cache._indices_cache.clear()
    cache._unique_constraints_cache.clear()
    cache._ddl_cache.clear()
    cache._view_ddl_cache.clear()

    print("✅ Cache limpiado completamente")
```

---

## Buenas Prácticas

### ✅ DO:

- Pre-cargar cache al iniciar aplicación
- Compartir instancia de cache (singleton)
- Invalidar selectivamente cuando DDL cambia
- Monitorear tamaño de cache en memoria
- Usar timeout para refrescar cache periódicamente

### ❌ DON'T:

- No crear nuevas instancias de cache por request (waste de memoria)
- No asumir que cache está actualizado si schema cambió
- No usar cache si requieres metadatos siempre frescos
- No guardar cache en disco sin serialización
- No olvidar invalidar cuando tablas son creadas/eliminadas

---

!!! tip "Ver también"
    - [Guía Async](../ASYNC_GUIDE.md) — Usar cache con operaciones async
    - [API Reference](../API_REFERENCE.md) — DatabaseMetadataCache methods
    - [Excepciones](../EXCEPTIONS.md) — Manejo de errores
    - [Ejemplo: Comparación de Esquemas](schema_comparison.md) — Uso real de metadatos
