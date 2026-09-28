# Ejemplo: Caché de Metadatos

## 1. Contexto del Ejemplo

Muestra cómo usar `DatabaseMetadataCache` y `RelationshipMetadataCache` para cachear metadatos de esquema, reducir consultas repetidas a la BD y gestionar la invalidación cuando una tabla cambia.

Resuelve el caso de procesos de introspección intensivos (generación de documentación, comparación de esquemas) donde las mismas tablas se consultan múltiples veces en la misma sesión.

## 2. Implementación de Referencia

```python
--8<-- "examples/metadata_cache_usage.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **Clave de tabla `(context, nombre)`**: identifica unívocamente una tabla en un contexto de BD. En SQLite es `("main", "tabla")`; en PostgreSQL `("public", "tabla")`; en Oracle `("HR", "tabla")`.
- **Patrón get-or-cache**: el patrón recomendado es intentar `cache.get_*()` primero (retorna `None` en cache miss), y solo si es `None` consultar la BD y llamar `cache.set_*()`.
- **Invalidación selectiva vs total**: `clear_by_table(context, tabla)` invalida solo una tabla; `clear_all()` invalida todo el caché. Usar la invalidación más acotada posible.
- **Caché compartida**: si `db_cache` se pasa a varios `MetadataManager`, los resultados de uno son visibles al otro en el mismo proceso. Comportamiento intencional para pipelines multi-tabla.

```python
# Patrón get-or-cache
from util_bbdd.metadata import DatabaseMetadataCache

cache = DatabaseMetadataCache()
key = ("main", "productos")

columns = cache.get_columns(key)  # None en primer acceso
if columns is None:
    columns = fetch_columns_from_db("productos")  # consulta real
    cache.set_columns(key, columns)
# Segunda llamada: desde caché, sin ir a BD
columns_cached = cache.get_columns(key)
```

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/metadata_cache_usage.py

# Ejecución (simula metadatos sin BD real; no requiere servidor externo)
python docs/examples/metadata_cache_usage.py
```

El ejemplo imprime estadísticas del caché (`get_cache_stats()`) para verificar cuántas entradas están almacenadas.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Extracción de Metadatos](../functional/metadata_extraction.md) — objetivo de negocio del sistema de caché
- **Referencia técnica**: [Gestor de Metadatos](../api/metadata_manager.md) — API de `DatabaseMetadataCache` y `MetadataManager`
- **Ejemplos relacionados**: [Conectar e Introspeccionar Base de Datos](example_connect_introspect.md) — uso del manager sin caché explícita
