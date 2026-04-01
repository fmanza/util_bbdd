# 📚 Guía de Migración - util_bbdd v0.6.3

**Para usuarios que migren hacia v0.6.3**

---

## ⚠️ IMPORTANTE: Cambios de Compatibilidad

⚠️ **BREAKING CHANGE:** el subsistema de grafos y documentación usa un contrato nuevo para configuración de relaciones. `first_level_only` deja de ser el eje principal de configuración y pasa a expresarse mediante `grafo.max_depth`.

⚠️ **BREAKING CHANGE:** los diagramas HTML ya no se presentan como una lista plana de SVG. Ahora se agrupan por sentido (`Salida` y `Entrada`) y por nivel.

⚠️ **BREAKING CHANGE:** la profundidad visible del grafo se controla mediante `grafo.max_depth`.

⚠️ **CAMBIO RELEVANTE:** el nombre público sync recomendado y exportado es `SyncDatabaseManager`. El alias `DatabaseManager` ya no se publica.

⚠️ **CAMBIO RELEVANTE:** `get_storage_inventory()` ya no devuelve `secondary`.
El contrato actual usa claves explícitas por capacidad:
- `primary`
- `temp_tablespaces` cuando aplica
- `sqlite_file_summary` en SQLite

⚠️ **CAMBIO RELEVANTE:** las plantillas HTML antiguas en `src/util_bbdd/doc/data` se sustituyen por una estructura Jinja2 modular en `src/util_bbdd/doc/templates`.

⚠️ **BREAKING CHANGE:** `DatabaseDocumentation` deja de exponer accesos auxiliares legacy a metadatos y DDL como `database`, `get_ddl()`, `get_columns()` o `get_storage_inventory_report()`.
La clase queda limitada a orquestar la generación documental.
Si necesitas consultar metadatos desde código de aplicación, usa `SyncDatabaseManager` directamente.

⚠️ **REFERENCIA RECOMENDADA:** para una configuración completa y comentada del bloque `imprimir`, revisa [docs/examples/imprimir_config_full_example.toml](docs/examples/imprimir_config_full_example.toml).

Pero veamos la nueva estructura recomendada para nuevo código.

---

## 🆕 Novedades acumuladas en v0.6.3

v0.6.3 consolida la superficie documental y operativa del repositorio y elimina la API auxiliar legacy de `DatabaseDocumentation`:

- HTML usa SVG inline para asegurar paneo y zoom fuera de VS Code.
- Word y HTML comparten payloads de resumen y leyenda para mantener semántica consistente.
- La salida offline copia iconos SVG locales para paginación y exportación.
- El contrato `imprimir_config` dispone de referencia completa y comentada en [docs/examples/imprimir_config_full_example.toml](docs/examples/imprimir_config_full_example.toml).
- El repositorio incorpora agentes especializados de Copilot y documenta el flujo recomendado entre instrucciones, prompts y agentes.
- `DatabaseDocumentation` queda como fachada de generación; las consultas ad hoc de metadatos deben hacerse contra `SyncDatabaseManager`.

Si ya migraste a la familia v0.6.x, el salto a v0.6.3 sigue siendo menor salvo si estabas usando `DatabaseDocumentation` como wrapper de consultas de metadatos.

---

## Estado de compatibilidad viva

La Fase 4 de documentación viva arranca fijando una regla simple: para código nuevo, usa imports canónicos; para integración heredada, mantén las rutas legacy solo mientras completes la migración.

### Imports canónicos recomendados

```python
from util_bbdd import SyncDatabaseManager, AsyncDatabaseManager
from util_bbdd.bulk import bulk_crud, AuditManager
from util_bbdd.analysis import GraphvizRelationshipGraphExt
```

### Rutas legacy aún soportadas

- `util_bbdd.database_manager`
- `util_bbdd.async_database_manager`
- `util_bbdd.bulk_crud`
- `util_bbdd.grafos`
- `util_bbdd.database_type_validator`

### Criterio operativo

- Mantén rutas legacy solo para compatibilidad backward en proyectos ya desplegados.
- Evita abrir código nuevo sobre wrappers históricos si existe una superficie canónica equivalente.
- Considera el README como referencia breve y esta guía como fuente de migración detallada.
- El refactor interno reciente de documentación, managers, queries, bulk y validadores no cambia la API pública recomendada; aclara qué capa debe usarse en nuevo código.

---

## 📖 Tabla Comparativa: v0.4.0 vs v0.6.0

### SyncDatabaseManager

#### v0.4.0
```python
from util_bbdd.database_manager import DatabaseManager

manager = DatabaseManager(
    db_type="mariadb",
    conn_params={"host": "localhost", "database": "test"}
)
```

#### v0.6.0+ (canónico recomendado)
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="mariadb",
    conn_params={"host": "localhost", "database": "test"}
)
```

**Diferencia:** cambia el import y el nombre de clase.

---

### AsyncDatabaseManager

#### v0.4.0 (aún funciona)
```python
from util_bbdd.async_database_manager import AsyncDatabaseManager

manager = AsyncDatabaseManager(
    db_type="postgresql",
    conn_params={"host": "localhost", "database": "test"}
)
await manager.init()
```

#### v0.5.0+ (canónico recomendado)
```python
from util_bbdd import AsyncDatabaseManager

manager = AsyncDatabaseManager(
    db_type="postgresql",
    conn_params={"host": "localhost", "database": "test"}
)
await manager.init()
```

**Sin cambios funcionales**, solo import path.

---

### Bulk Operations

#### v0.4.0 (aún funciona)
```python
from util_bbdd.bulk_crud import bulk_crud, AuditManager

# Bulk CRUD
manager = bulk_crud(engine, logger=logger)
manager.bulk_insert_from_df(df, "users")

# Audit
audit = AuditManager(audit_file="audit.json")
```

#### v0.5.0 (recomendado - más clara y modular)
```python
from util_bbdd.bulk import bulk_crud, AuditManager, normalize_records_for_sql

# Bulk CRUD (same API)
manager = bulk_crud(engine, logger=logger)
manager.bulk_insert_from_df(df, "users")

# Audit (same API)
audit = AuditManager(audit_file="audit.json")

# Nueva modularidad: normalización explícita si necesario
normalized = normalize_records_for_sql(records)
```

**Ventajas v0.5.0:**
- Módulo `bulk` es más claro
- Funciones normalizadas expuestas
- Mejor organización interna

---

### Analysis & Graphs

#### v0.4.0 (aún funciona)
```python
from util_bbdd.analysis import DatabaseRelationshipGraphBase, GraphvizRelationshipGraph

graph = GraphvizRelationshipGraph(db_manager)
graph_data = graph.generate_graphviz_graph_paginated(...)
```

#### v0.6.0 (requerido para la nueva funcionalidad multinivel)
```python
from util_bbdd.analysis import (
    DatabaseRelationshipGraphBase,
    GraphDocument,
    LevelDirection,
    GraphvizRelationshipGraphExt,
    MatplotlibRelationshipGraph
)

graph_ext = GraphvizRelationshipGraphExt(db_manager)
graph_data = graph_ext.generate_graphviz_graph_paginated_ext(
    table_name="users",
    output_dir="./graphs",
    max_depth=3,
    direction="both",
    max_subnodes=10,
)

document = graph_ext.build_graph_document(
    table_name="users",
    max_depth=3,
    direction=LevelDirection.BOTH,
)
```

**Cambios clave v0.6.0:**
- `GraphDocument` pasa a ser el modelo intermedio del análisis
- el recorrido soporta entrada, salida o ambas direcciones
- la visualización de columnas se configura por modo y no por booleano simple
- HTML y Word consumen la nueva semántica de niveles

---

## 🔄 Path Migration Checklist

Si estás refactorizando código legacy para v0.6.0:

### 1. Imports de SyncDatabaseManager

- [ ] `from util_bbdd.database_manager import DatabaseManager` → `from util_bbdd import SyncDatabaseManager`
- [ ] Usa `util_bbdd.managers` solo si necesitas mantener una importación intermedia explícita

**Antes:**
```python
from util_bbdd.database_manager import DatabaseManager
```

**Después:**
```python
from util_bbdd import SyncDatabaseManager
```

### 2. Imports de AsyncDatabaseManager

- [ ] `from util_bbdd.async_database_manager import AsyncDatabaseManager` → `from util_bbdd import AsyncDatabaseManager`
- [ ] Usa `util_bbdd.managers` solo si necesitas mantener una importación intermedia explícita

**Antes:**
```python
from util_bbdd.async_database_manager import AsyncDatabaseManager
```

**Después:**
```python
from util_bbdd import AsyncDatabaseManager
```

### 3. Imports de Bulk

- [ ] `from util_bbdd.bulk_crud import` → `from util_bbdd.bulk import`

**Antes:**
```python
from util_bbdd.bulk_crud import bulk_crud, AuditManager
from util_bbdd.bulk_crud.normalizacion_sql import normalize_records_for_sql
```

**Después:**
```python
from util_bbdd.bulk import bulk_crud, AuditManager, normalize_records_for_sql
```

### 4. Imports del núcleo de analysis

- [ ] `from util_bbdd.bulk.base import ...` → `from util_bbdd.analysis.base import ...`
- [ ] No usar `util_bbdd.bulk.base`: la ruta fue eliminada en v0.6.0

**Antes:**
```python
from util_bbdd.bulk.base import DatabaseRelationshipGraphBase, GraphDocument, LevelDirection
```

**Después:**
```python
from util_bbdd.analysis.base import DatabaseRelationshipGraphBase, GraphDocument, LevelDirection
```

### 4. Imports de Analysis

- [ ] `from util_bbdd.grafos import` → `from util_bbdd.analysis import`

**Antes:**
```python
from util_bbdd.grafos import GraphvizRelationshipGraph
```

**Después:**
```python
from util_bbdd.analysis import GraphvizRelationshipGraph
# Más opciones disponibles:
from util_bbdd.analysis import (
    DatabaseRelationshipGraphBase,
    GraphvizRelationshipGraph,
    GraphvizRelationshipGraphExt,
    MatplotlibRelationshipGraph
)
```

### 5. Contrato de almacenamiento

- [ ] Si tu código usaba `result["secondary"]`, migra a claves explícitas

**Antes:**
```python
storage = manager.get_storage_inventory()
secondary_rows = storage["secondary"]
```

**Después:**
```python
storage = manager.get_storage_inventory()
primary_rows = storage["primary"]
temp_rows = storage.get("temp_tablespaces", [])
sqlite_summary = storage.get("sqlite_file_summary", [])
```

**Nota:** `ficheros_fisicos_adicional` desaparece del catálogo SQL. En SQLite, ese contenido pasa a `sqlite_file_summary` y se documenta como ampliación de `Ficheros físicos`.

### 6. Personalizaciones HTML

- [ ] Si personalizabas plantillas HTML antiguas, migra a la nueva estructura

**Antes:**
```text
src/util_bbdd/doc/data/html_documentation_template.j2
src/util_bbdd/doc/data/html_index_template.j2
src/util_bbdd/doc/data/html_collection_template.j2
```

**Ahora:**
```text
src/util_bbdd/doc/templates/layouts/base_page.j2
src/util_bbdd/doc/templates/macros/common.j2
src/util_bbdd/doc/templates/pages/detail.html.j2
src/util_bbdd/doc/templates/pages/index.html.j2
src/util_bbdd/doc/templates/pages/collection.html.j2
```

---

## 🎯 Ejemplos de Migración

### Ejemplo 1: Script Simple Connection

**v0.4.0:**
```python
from util_bbdd.database_manager import DatabaseManager

manager = DatabaseManager(
    db_type="mariadb",
    conn_params={
        "host": "localhost",
        "user": "root",
        "password": "secret",
        "database": "mydb"
    }
)

result = manager.execute_query("SELECT * FROM users")
```

**v0.5.6+ (nuevo import y nombre):**
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="mariadb",
    conn_params={
        "host": "localhost",
        "user": "root",
        "password": "secret",
        "database": "mydb"
    }
)

result = manager.execute_query("SELECT * FROM users")  # Sin cambios
```

---

### Ejemplo 2: Async Manager

**v0.4.0:**
```python
from util_bbdd.async_database_manager import AsyncDatabaseManager

async def main():
    manager = AsyncDatabaseManager(
        db_type="postgresql",
        conn_params={"host": "localhost", "database": "test"}
    )
    await manager.init()

    result = await manager.execute_query("SELECT * FROM users")
    print(result)

    await manager.close()

asyncio.run(main())
```

**v0.5.0 (mismo código, mejor import):**
```python
from util_bbdd import AsyncDatabaseManager  # Más simple

async def main():
    manager = AsyncDatabaseManager(
        db_type="postgresql",
        conn_params={"host": "localhost", "database": "test"}
    )
    await manager.init()  # Sin cambios

    result = await manager.execute_query("SELECT * FROM users")
    print(result)

    await manager.close()

asyncio.run(main())
```

---

### Ejemplo 3: Bulk Operations

**v0.4.0:**
```python
from util_bbdd.database_manager import DatabaseManager
from util_bbdd.bulk_crud import bulk_crud
import pandas as pd

manager = DatabaseManager(db_type="mariadb", conn_params={...})
engine = manager.get_sqlalchemy_engine()

df = pd.read_csv("data.csv")

bulk_op = bulk_crud(engine, logger=logger)
bulk_op.bulk_insert_from_df(df, "users", batch_size=1000)
```

**v0.5.6+ (nuevo import y nombre):**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.bulk import bulk_crud  # Mejor path
import pandas as pd

manager = SyncDatabaseManager(db_type="mariadb", conn_params={...})
engine = manager.get_sqlalchemy_engine()  # Sin cambios

df = pd.read_csv("data.csv")

bulk_op = bulk_crud(engine, logger=logger)
bulk_op.bulk_insert_from_df(df, "users", batch_size=1000)  # Sin cambios
```

---

### Ejemplo 4: Analysis & Graphs

**v0.4.0:**
```python
from util_bbdd.database_manager import DatabaseManager
from util_bbdd.grafos import GraphvizRelationshipGraph

manager = DatabaseManager(db_type="mariadb", conn_params={...})

graph = GraphvizRelationshipGraph(manager)
tables = ["users", "orders", "products"]
graph_html = graph.generate_graphviz_graph_paginated(tables=tables)
```

**v0.5.6+ (nuevo import y nombre):**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.analysis import (
    GraphvizRelationshipGraph,
    GraphvizRelationshipGraphExt
)

manager = SyncDatabaseManager(db_type="mariadb", conn_params={...})

# Opción 1: Básico (mismo que v0.4.0)
graph = GraphvizRelationshipGraph(manager)
tables = ["users", "orders", "products"]
graph_html = graph.generate_graphviz_graph_paginated(tables=tables)

# Opción 2: Extendido (nueva en v0.5.0)
graph_ext = GraphvizRelationshipGraphExt(manager)
graph_paths = graph_ext.generate_graphviz_graph_paginated_ext(
    table_name="users",
    output_dir="./graphs",
    max_depth=3,
    direction="both",
    column_mode="relations",
    max_subnodes=10,
)
```

---

## ⚙️ Ajustes Internos (No Afectan APIs)

Estos cambios son internos y **NO afectan** tu código:

- ✅ Módulos reorganizados internamente (mejor estructura)
- ✅ Imports en `__init__.py` centralizados
- ✅ Los wrappers legacy siguen existiendo donde no afectan al manager async
- ✅ Excepciones siguen siendo las mismas
- ✅ Métodos públicos idénticos

---

## 🚨 Deprecations y compatibilidad viva

Estas rutas deben migrarse ya si todavía existen en tu código:

```python
# Legacy soportado en v0.6.3, pero fuera de la ruta recomendada para código nuevo:
from util_bbdd.bulk_crud import ...  # Usa: from util_bbdd.bulk import ...
from util_bbdd.grafos import ...     # Usa: from util_bbdd.analysis import ...
from util_bbdd.database_manager import DatabaseManager  # Usa: from util_bbdd import SyncDatabaseManager
```

En v0.6.3 estas rutas siguen soportadas para no romper integraciones existentes, pero README y ejemplos nuevos deben partir de la superficie canónica.

---

## 🔍 Verificar tu Código

### Script de Verificación

```bash
# Buscar imports antiguos
rg "from util_bbdd\.bulk_crud"
rg "from util_bbdd\.grafos"
rg "from util_bbdd\.database_manager"
rg "from util_bbdd\.async_database_manager"

# Luego reemplaza con:
# from util_bbdd.bulk import ...
# from util_bbdd.analysis import ...
# from util_bbdd.managers import ... (o from util_bbdd import ...)
# from util_bbdd import SyncDatabaseManager
```

---

## ✅ Validación Post-Migración

Después de migrar, ejecuta:

```bash
python -m pytest tests/ -v

# Verifica:
# - El suite pasa en tu estado actual
# - No import errors
# - Funcionalidad idéntica
```

---

## 🤝 Soporte & Questions

Si encuentras problemas después de migrar:

1. Verifica que usas los imports correctos
2. Revisa que no hay typos en paths
3. Si aún falla, revisa primero imports y nombres de clase sync

---

## 📝 Resumen

| Aspecto | Legacy | Canónico actual | Acción recomendada |
|--------|--------|------------------|--------------------|
| **SyncDatabaseManager** | `database_manager.py` | `from util_bbdd import SyncDatabaseManager` | migrar import y nombre |
| **AsyncDatabaseManager** | `async_database_manager.py` | `from util_bbdd import AsyncDatabaseManager` | migrar import |
| **Bulk Ops** | `bulk_crud/` | `from util_bbdd.bulk import bulk_crud` | migrar import |
| **Analysis** | `grafos/` | `from util_bbdd.analysis import GraphvizRelationshipGraph` | migrar import |
| **HTML Templates** | `doc/data/*.j2` | `doc/templates/...` | migrar personalizaciones |
| **Breaking Changes** | contrato previo | cambios vigentes desde v0.6.0 | revisar bloque de grafos/documentación |
| **Storage Inventory** | `primary` + `secondary` | claves explícitas por capacidad | actualizar consumo de `get_storage_inventory()` |
| **Compatibilidad viva** | wrappers legacy | superficie canónica documentada | abrir código nuevo solo sobre la ruta canónica |

---

*Documento: MIGRATION_GUIDE.md*
*Para: Usuarios migrando código legacy hacia la superficie pública vigente*
*Generado: Marzo 2026*
*Status: READY* ✅
