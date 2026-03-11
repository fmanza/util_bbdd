# 📚 Guía de Migración - util_bbdd v0.5.0

**Para usuarios que migren desde v0.4.0 → v0.5.0**

---

## ⚠️ IMPORTANTE: Cambios de Compatibilidad

✅ **BUENA NOTICIA:** v0.5.0 es **100% hacia atrás compatible**. Todo el código v0.4.0 sigue funcionando sin cambios.

Pero veamos la nueva estructura recomendada para nuevo código.

---

## 📖 Tabla Comparativa: v0.4.0 vs v0.5.0

### DatabaseManager

#### v0.4.0 (aún funciona)
```python
from util_bbdd.database_manager import DatabaseManager

manager = DatabaseManager(
    db_type="mariadb",
    conn_params={"host": "localhost", "database": "test"}
)
```

#### v0.5.0 (recomendado - mismo resultado)
```python
from util_bbdd.managers import DatabaseManager
# o más simple:
from util_bbdd import DatabaseManager

manager = DatabaseManager(
    db_type="mariadb",
    conn_params={"host": "localhost", "database": "test"}
)
```

**Diferencia:** Ruta más limpia y clara.

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

#### v0.5.0 (recomendado)
```python
from util_bbdd.managers import AsyncDatabaseManager
# o más simple:
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

#### v0.5.0 (recomendado - más clara)
```python
from util_bbdd.analysis import (
    DatabaseRelationshipGraphBase,
    GraphvizRelationshipGraph,
    GraphvizRelationshipGraphExt,
    MatplotlibRelationshipGraph
)

# Graphviz
graph = GraphvizRelationshipGraph(db_manager)
graph_data = graph.generate_graphviz_graph_paginated(...)

# O versión extendida con columnas
graph_ext = GraphvizRelationshipGraphExt(db_manager)
graph_data = graph_ext.generate_graphviz_graph_paginated(
    show_columns=True,
    orthogonal_edges=True
)

# O Matplotlib
graph_mpl = MatplotlibRelationshipGraph(db_manager)
graph_data = graph_mpl.generate_matplotlib_graph_paginated(...)
```

**Ventajas v0.5.0:**
- Módulo `analysis` es más descriptivo
- Múltiples implementaciones accesibles
- Mejor namespace

---

## 🔄 Path Migration Checklist

Si estás refactorizando código legacy para v0.5.0 estilo:

### 1. Imports de DatabaseManager

- [ ] `from util_bbdd.database_manager import` → `from util_bbdd.managers import`
- [ ] O más simple: `from util_bbdd import DatabaseManager`

**Antes:**
```python
from util_bbdd.database_manager import DatabaseManager
```

**Después:**
```python
from util_bbdd.managers import DatabaseManager
# O:
from util_bbdd import DatabaseManager
```

### 2. Imports de AsyncDatabaseManager

- [ ] `from util_bbdd.async_database_manager import` → `from util_bbdd.managers import`
- [ ] O: `from util_bbdd import AsyncDatabaseManager`

**Antes:**
```python
from util_bbdd.async_database_manager import AsyncDatabaseManager
```

**Después:**
```python
from util_bbdd.managers import AsyncDatabaseManager
# O:
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

**v0.5.0 (mismo código, mejor path):**
```python
from util_bbdd import DatabaseManager  # Más simple

manager = DatabaseManager(
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

**v0.5.0 (mismo código, mejor paths):**
```python
from util_bbdd import DatabaseManager
from util_bbdd.bulk import bulk_crud  # Mejor path
import pandas as pd

manager = DatabaseManager(db_type="mariadb", conn_params={...})
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

**v0.5.0 (mejor path y más opciones):**
```python
from util_bbdd import DatabaseManager
from util_bbdd.analysis import (
    GraphvizRelationshipGraph,
    GraphvizRelationshipGraphExt
)

manager = DatabaseManager(db_type="mariadb", conn_params={...})

# Opción 1: Básico (mismo que v0.4.0)
graph = GraphvizRelationshipGraph(manager)
tables = ["users", "orders", "products"]
graph_html = graph.generate_graphviz_graph_paginated(tables=tables)

# Opción 2: Extendido (nueva en v0.5.0)
graph_ext = GraphvizRelationshipGraphExt(manager)
graph_html = graph_ext.generate_graphviz_graph_paginated(
    tables=tables,
    show_columns=True,  # Mostrar columnas
    orthogonal_edges=True  # Edges ortogonales
)
```

---

## ⚙️ Ajustes Internos (No Afectan APIs)

Estos cambios son internos y **NO afectan** tu código:

- ✅ Módulos reorganizados internamente (mejor estructura)
- ✅ Imports en `__init__.py` centralizados
- ✅ Wrappers de compatibilidad mantienen ruta antigua
- ✅ Excepciones siguen siendo las mismas
- ✅ Métodos públicos idénticos

---

## 🚨 Deprecations (Will Remove Later)

Estas rutas seguirán funcionando en v0.5.0 pero serán deprecadas en v0.6.0+:

```python
# Deprecado - seguirá funcionando en v0.5.0 pero no lo uses en nuevo código:
from util_bbdd.bulk_crud import ...  # Usa: from util_bbdd.bulk import ...
from util_bbdd.grafos import ...     # Usa: from util_bbdd.analysis import ...
```

Para v0.6.0 esperamos que migres a los nuevos paths.

---

## 🔍 Verificar tu Código

### Script de Verificación

```bash
# Buscar imports antiguos
grep -r "from util_bbdd.bulk_crud" .
grep -r "from util_bbdd.grafos" .
grep -r "from util_bbdd.database_manager" .
grep -r "from util_bbdd.async_database_manager" .

# Luego reemplaza con:
# from util_bbdd.bulk import ...
# from util_bbdd.analysis import ...
# from util_bbdd.managers import ... (o from util_bbdd import ...)
```

---

## ✅ Validación Post-Migración

Después de migrar, ejecuta:

```bash
python -m pytest tests/ -v

# Verifica:
# - Tests passing: 443/443 ✅
# - No import errors
# - Funcionalidad idéntica
```

---

## 🤝 Soporte & Questions

Si encuentras problemas después de migrar:

1. Verifica que usas los imports correctos
2. Revisa que no hay typos en paths
3. Si aún falla, el código legacy debería funcionar igual (revert y report issue)

---

## 📝 Resumen

| Aspecto | v0.4.0 | v0.5.0 | Migración |
|--------|--------|--------|-----------|
| **DatabaseManager** | `database_manager.py` | `managers/sync.py` | `from util_bbdd import DatabaseManager` |
| **AsyncDatabaseManager** | `async_database_manager.py` | `managers/async_mgr.py` | `from util_bbdd import AsyncDatabaseManager` |
| **Bulk Ops** | `bulk_crud/` | `bulk/` | `from util_bbdd.bulk import bulk_crud` |
| **Analysis** | `grafos/` | `analysis/` | `from util_bbdd.analysis import GraphvizRelationshipGraph` |
| **Breaking Changes** | N/A | **NONE** ✅ | Todo legacy code funciona |
| **Deprecations** | N/A | bulk_crud/, grafos/ paths | Usar nuevos paths para nuevo código |

---

*Documento: MIGRATION_GUIDE.md*
*Para: Usuarios migrando v0.4.0 → v0.5.0*
*Generado: Marzo 2026*
*Status: READY* ✅
