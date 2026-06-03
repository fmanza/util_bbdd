# Guía de Migración — util_bbdd v0.6.3

## 1. Objetivo

Migrar código de versiones anteriores a v0.6.3 actualizando imports, nombres de clase y contratos de API que han cambiado.

## 2. Requisitos Previos

- Versión previa a v0.6.3 instalada en el proyecto
- Identificar si se usaban las rutas legacy (`util_bbdd.database_manager`, `util_bbdd.bulk_crud`, `util_bbdd.grafos`) o `DatabaseDocumentation` como wrapper de consultas de metadatos
- Python 3.12+

## 3. Pasos

### Paso 1 — Actualizar util_bbdd

```bash
pip install --upgrade util_bbdd
```

### Paso 2 — Actualizar imports a los canónicos

| Legacy (antes de v0.6.3) | Canónico (v0.6.3+) |
|---|---|
| `from util_bbdd.database_manager import DatabaseManager` | `from util_bbdd import SyncDatabaseManager` |
| `from util_bbdd.async_database_manager import AsyncDatabaseManager` | `from util_bbdd import AsyncDatabaseManager` |
| `from util_bbdd.bulk_crud import bulk_crud` | `from util_bbdd.bulk import BulkCrud` |
| `from util_bbdd.grafos import GraphvizRelationshipGraph` | `from util_bbdd.analysis import GraphvizRelationshipGraphExt` |

```python
# v0.6.3+ canónico
from util_bbdd import SyncDatabaseManager, AsyncDatabaseManager
from util_bbdd.bulk import BulkCrud, AuditManager
from util_bbdd.analysis import GraphvizRelationshipGraphExt
```

### Paso 3 — Migrar configuración de grafos

```python
# Antes (v< 0.6.3)
grafo.generate(first_level_only=True)

# Ahora (v0.6.3+)
grafo = GraphvizRelationshipGraphExt(
    db_manager=manager,
    max_depth=1,          # equivale a first_level_only=True
    direction="both",
)
```

### Paso 4 — Migrar consultas de metadatos desde `DatabaseDocumentation`

`DatabaseDocumentation` ya no expone métodos de consulta de metadatos (`get_ddl()`, `get_columns()`, etc.). Para consultas ad hoc usar `SyncDatabaseManager` directamente:

```python
# Antes (API legacy eliminada)
doc = DatabaseDocumentation(...)
tablas = doc.database.get_tables()  # ERROR en v0.6.3+

# Ahora
mgr = SyncDatabaseManager("postgresql", conn_params)
tablas = mgr.get_tables()  # consultas directas al manager
```

### Paso 5 — Actualizar claves de `get_storage_inventory()`

```python
# Antes: devolvía 'secondary'
inv = manager.get_storage_inventory()
espacio = inv.get("secondary")  # ya no existe

# Ahora: claves explícitas
espacio_primario = inv.get("primary")
temp = inv.get("temp_tablespaces")
sqlite_info = inv.get("sqlite_file_summary")  # solo SQLite
```

## 4. Verificación

```bash
# Verificar que la versión actualizada es v0.6.3+
python -c "import util_bbdd; print(util_bbdd.__version__)"

# Verificar que los imports canónicos funcionan
python -c "from util_bbdd import SyncDatabaseManager, AsyncDatabaseManager; print('OK')"
python -c "from util_bbdd.analysis import GraphvizRelationshipGraphExt; print('OK')"
```

```bash
# Ejecutar los tests del proyecto para detectar regresiones
python -m pytest
```

## 5. Variantes y Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `ImportError: cannot import name 'DatabaseManager'` | Usando alias legacy eliminado | Cambiar a `SyncDatabaseManager` (ver Paso 2) |
| `AttributeError: 'DatabaseDocumentation' has no attribute 'get_columns'` | Usando API de metadatos eliminada de `DatabaseDocumentation` | Usar `SyncDatabaseManager.get_columns()` directamente |
| `KeyError: 'secondary'` en `get_storage_inventory()` | Clave eliminada | Usar `"primary"`, `"temp_tablespaces"` o `"sqlite_file_summary"` |
| Grafos con la misma profundidad anterior | `first_level_only=True` equivale a `max_depth=1` | Usar `max_depth=1` en el constructor de `GraphvizRelationshipGraphExt` |
