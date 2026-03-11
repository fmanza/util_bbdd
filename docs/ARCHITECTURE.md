# 🏗️ Arquitectura de util_bbdd v0.5.0

**Versión:** 0.5.0
**Fecha:** Marzo 2026
**Estado:** Refactorizado & Estabilizado

---

## 📐 Estructura Jerárquica (3 Niveles)

```
util_bbdd/
│
├─── LEVEL 1: ABSTRACCIONES & TIPOS (Foundation)
│    │
│    ├── _core/                          # Tipo abstracto de datos
│    │   ├── types.py                    # Type aliases (30 líneas)
│    │   ├── exceptions.py               # Jerarquía de excepciones (57 líneas)
│    │   ├── contracts.py                # Protocols e interfaces (26 líneas)
│    │   ├── constants.py                # Enums y valores constantes (43 líneas)
│    │   └── __init__.py                 # Exports públicos
│    │
│    └── _drivers/                       # Gestión de drivers
│        ├── validator.py                # Validación centralizada (~73 líneas)
│        ├── capabilities.py             # Capacidades por motor (43 líneas)
│        ├── registry.py                 # Registry de drivers
│        └── __init__.py
│
├─── LEVEL 2: SERVICIOS CORE (Services Layer)
│    │
│    ├── connection/                     # Pool, factory, configuración (1,305 líneas)
│    │   ├── factory.py                  # Connection factory
│    │   ├── pool.py                     # Pool management
│    │   ├── config.py                   # Connection configs
│    │   ├── params.py                   # Parameters management
│    │   ├── builder.py                  # Params builder
│    │   ├── protocols.py                # Interfaces async/sync
│    │   ├── close.py                    # Close utilities
│    │   ├── motors/                     # Motor-specific implementations
│    │   │   ├── mariadb.py
│    │   │   ├── postgresql.py
│    │   │   ├── oracle.py
│    │   │   ├── sqlite.py
│    │   │   ├── hsqldb.py
│    │   │   └── sqlserver.py
│    │   └── __init__.py
│    │
│    ├── query/                          # Registry, resolver, executors (314 líneas base)
│    │   ├── registry.py                 # Query registry
│    │   ├── resolver.py                 # Query resolver
│    │   ├── executors/
│    │   │   ├── base.py                 # Base executor
│    │   │   ├── sync_executor.py        # Sync implementation
│    │   │   ├── async_executor.py       # Async implementation
│    │   │   └── __init__.py
│    │   └── __init__.py
│    │
│    ├── metadata/                       # Metadata processing pipeline (887 líneas)
│    │   ├── cache.py                    # Caching layer
│    │   ├── contracts.py                # Interfaces
│    │   ├── normalizer.py               # SQL normalization
│    │   ├── builder.py                  # Metadata builder
│    │   ├── fetcher.py                  # Data fetcher
│    │   ├── manager.py                  # Orchestración
│    │   └── __init__.py
│    │
│    └── results/                        # Result management (74 líneas)
│        ├── types.py                    # Result type definitions
│        ├── normalizer.py               # Result normalization
│        └── __init__.py
│
├─── LEVEL 3: ESPECIALIZACIÓN (Specialized Modules)
│    │
│    ├── bulk/                           # 🆕 Operaciones bulk (2,129 líneas)
│    │   ├── crud.py                     # Bulk CRUD operations (999 líneas)
│    │   │   └── Classes: bulk_crud
│    │   │   └── Methods: bulk_insert_from_df, bulk_update_from_df, bulk_delete_from_df
│    │   ├── audit.py                    # Audit management (866 líneas)
│    │   │   └── Classes: AuditManager, AuditTransaction
│    │   │   └── Exceptions: AuditError, AuditConfigError, AuditFileError
│    │   ├── normalize.py                # SQL normalization (264 líneas)
│    │   │   └── Functions: normalize_records_for_sql, normalize_sql_literal
│    │   └── __init__.py
│    │
│    ├── analysis/                       # 🆕 Análisis de relaciones (1,200+ líneas)
│    │   ├── base.py                     # Base classes
│    │   │   └── Classes: DatabaseRelationshipGraphBase, TableRelation
│    │   ├── graphviz.py                 # Graphviz visualization
│    │   │   └── Classes: GraphvizRelationshipGraph
│    │   ├── graphviz_ext.py             # Extended Graphviz (598 líneas)
│    │   │   └── Classes: GraphvizRelationshipGraphExt (con columnas/tipos)
│    │   ├── matplotlib_graph.py         # Matplotlib visualization (278 líneas)
│    │   │   └── Classes: MatplotlibRelationshipGraph
│    │   └── __init__.py
│    │
│    └── managers/                       # 🆕 Database managers (2,200+ líneas)
│        ├── sync.py                     # DatabaseManager (1,000+ líneas)
│        │   └── Classes: DatabaseManager (conexiones síncronas)
│        ├── async_mgr.py                # AsyncDatabaseManager (700+ líneas)
│        │   └── Classes: AsyncDatabaseManager (conexiones async)
│        └── __init__.py
│
└─── LEVEL 0: COMPATIBILIDAD & WRAPPERS (Backward Compatibility)
     │
     ├── database_manager.py             # → managers.sync.DatabaseManager
     ├── async_database_manager.py       # → managers.async_mgr.AsyncDatabaseManager
     ├── managers.py                     # Convenience wrapper
     │
     ├── bulk_crud.py                    # → bulk.crud (root wrapper)
     ├── bulk_crud/                      # → bulk (directory wrapper)
     │   ├── crud.py                     # → bulk.crud
     │   ├── audit_manager.py            # → bulk.audit
     │   ├── normalizacion_sql.py        # → bulk.normalize
     │   └── __init__.py
     │
     └── grafos.py                       # → analysis (root wrapper)
         └── grafos/                     # → analysis (directory wrapper)
             ├── relationship_graph_base.py         # → analysis.base
             ├── graphviz_relationship_graph.py     # → analysis.graphviz
             ├── graphviz_relationship_graph_ext.py # → analysis.graphviz_ext
             ├── matplotlib_relationship_graph.py   # → analysis.matplotlib_graph
             └── __init__.py
```

---

## 🔄 Flujo de Operaciones

### Operación: Ejecutar Query

```
User Code
    ↓
DatabaseManager / AsyncDatabaseManager (managers/)
    ↓
    ├─→ connection/ (obtener conexión)
    ├─→ query/ (resolver + ejecutar)
    │   ├─→ registry (lookup)
    │   ├─→ resolver (parse)
    │   └─→ executors (sync/async)
    ├─→ metadata/ (obtener esquema si necesario)
    └─→ results/ (normalizar resultado)
    ↓
Result (normalizado)
```

### Operación: Bulk Insert

```
User: bulk_crud.bulk_insert_from_df()
    ↓
bulk/crud.py:bulk_crud.bulk_insert_from_df()
    ↓
    ├─→ bulk/normalize.py (normalize_records_for_sql)
    ├─→ metadata/ (obtener tabla meta)
    ├─→ connection/ (obtener conexión)
    └─→ executors/ (ejecutar batch)
    ↓
Result (rows inserted)
```

### Operación: Analizar Relaciones

```
User: analysis.DatabaseRelationshipGraphBase.analyze_table_relations()
    ↓
analysis/base.py
    ↓
    ├─→ metadata/ (obtener FKs)
    ├─→ analysis/graphviz.py o matplotlib_graph.py
    └─→ Visualización
    ↓
Graph Output
```

---

## 📦 Módulos Deep Dive

### Level 1: Abstracciones

#### `_core/types.py`
- Type aliases para standard library
- Definiciones de tipos reutilizables

#### `_core/exceptions.py`
- Jerarquía: `DatabaseException` (base)
  - `DatabaseConfigurationError`
  - `DatabaseConnectionError`
  - `DatabaseOperationError`
  - `QueryError`
  - `DatabaseValidationError`
  - etc.

#### `_core/contracts.py`
- `DatabaseConnection` (Protocol)
- `DatabasePool` (Protocol)
- `Executor` (Protocol)

#### `_drivers/validator.py`
- `DatabaseTypeValidator` - validar tipos
- `get_database_validator()` - factory
- `validate_db_type()` - quick check
- Motor-specific validators

---

### Level 2: Services

#### `connection/`
**Responsabilidad:** Gestionar conexiones y pools

- `factory.py` - `ConnectFactory.create_connection(db_type, params)`
- `pool.py` - `PoolFactory.create_pool(db_type, params)`
- `params.py` - `ConnectionParamsManager` - parse y validar parámetros
- `config.py` - `ConnectionConfig` - dataclass para config
- `protocols.py` - Interfaces `ConnectionPool`, `AsyncConnectionPool`
- `motors/` - Implementaciones específicas por motor

**Ejemplo:**
```python
from util_bbdd.connection import ConnectFactory

conn = await ConnectFactory.create_async_connection("mariadb", {
    "host": "localhost",
    "user": "root",
    "password": "secret",
    "database": "test"
})
```

#### `query/`
**Responsabilidad:** Gestionar y ejecutar queries

- `registry.py` - `DatabaseQueries` - cargar queries desde JSON
- `resolver.py` - `DatabaseQueryResolver` - resolver placeholders
- `executors/` - Ejecutar queries (sync/async)

**Ejemplo:**
```python
from util_bbdd.query import DatabaseQueries

queries = DatabaseQueries.load("queries.json")
query = queries.resolve("get_users", {"id": 1})
result = await executor.execute_custom(query)
```

#### `metadata/`
**Responsabilidad:** Cachear y normalizar metadata de BD

- `cache.py` - `DatabaseMetadataCache` - cachear schema info
- `normalizer.py` - Normalizar filas de metadata
- `manager.py` - Orquestar operaciones de metadata

**Ejemplo:**
```python
from util_bbdd.metadata import DatabaseMetadataCache

cache = DatabaseMetadataCache()
tables = cache.get_tables(connection)
columns = cache.get_columns(connection, "users")
```

#### `results/`
**Responsabilidad:** Normalizar resultados de queries

- `types.py` - `RowOrNone`, `Rows` - type aliases
- `normalizer.py` - `ResultNormalizer` - normalizar a tuples/dicts

---

### Level 3: Especialización

#### `bulk/crud.py` - Bulk Operations (999 líneas)
```python
bulk_crud_manager = bulk_crud(engine, logger=logger)
bulk_crud_manager.bulk_insert_from_df(df, "users", batch_size=1000)
bulk_crud_manager.bulk_update_from_df(df, "users", key_column="id")
bulk_crud_manager.bulk_delete_from_df(df, "users", key_column="id")
```

#### `bulk/audit.py` - Audit Trail (866 líneas)
```python
audit_manager = AuditManager(audit_file="audit.json")

with audit_manager.registrar_operacion("INSERT", "users") as audit_tx:
    # Realizar operación
    audit_tx.registrar_cambio("field", old_val, new_val)
```

#### `analysis/` - Relationship Graphs (1,200+ líneas)
```python
from analysis import DatabaseRelationshipGraphBase, GraphvizRelationshipGraph

analyzer = GraphvizRelationshipGraph(db_manager)
graph_data = analyzer.generate_graphviz_graph_paginated(
    tables=["users", "orders", "products"],
    max_tables_per_page=5
)
```

---

## 🔌 Inyección de Dependencias

Cada nivel depende del anterior:

```
Level 3: bulk/, analysis/, managers/
    ↓ (uses)
Level 2: connection/, query/, metadata/, results/
    ↓ (uses)
Level 1: _core/, _drivers/
    ↓ (uses)
External: SQLAlchemy, pandas, graphviz, matplotlib
```

**No hay ciclos de importación** ✅

---

## 🌐 Import Paths (Públicos)

```python
# Directa (nuevo path - recomendado)
from util_bbdd.managers import DatabaseManager, AsyncDatabaseManager
from util_bbdd.bulk import bulk_crud, AuditManager
from util_bbdd.analysis import GraphvizRelationshipGraph

# Raíz (convenience)
from util_bbdd import DatabaseManager, AsyncDatabaseManager

# Legacy (compatibilidad - aún funciona)
from util_bbdd.database_manager import DatabaseManager
from util_bbdd.async_database_manager import AsyncDatabaseManager
from util_bbdd.bulk_crud import bulk_crud
from util_bbdd.grafos import GraphvizRelationshipGraph
```

---

## 📊 Capas de Caché

1. **Connection Cache** - Pool de conexiones reutilizables
2. **Metadata Cache** - Schema de tablas/columnas cachado
3. **Relationship Cache** - FKs y relaciones cachadas
4. **Query Cache** - Queries compiladas y resueltas

---

## 🧪 Testing Strategy

- **Unit Tests:** Por módulo Level 1-2
- **Integration Tests:** End-to-end workflows
- **Contract Tests:** Protocolo compatibility
- **Coverage:** ~39% (focus en paths críticos)

---

## 🚀 Performance Considerations

1. **Conexiones:** Pool reutiliza conexiones (async)
2. **Queries:** Prepared statements + binding
3. **Metadata:** Caché con TTL configurable
4. **Bulk Ops:** Batch processing para eficiencia
5. **Async:** Full async/await support

---

## 🔐 Seguridad

- ✅ Parámetros vinculados (no SQL injection)
- ✅ Validación de tipos
- ✅ Excepciones específicas (no exposición de info interna)
- ✅ Pool timeout + connection management
- ✅ Sanitización de literals SQL

---

## 📈 Versionado

```
v0.4.0 → v0.5.0 (actual)
  ├─ Nueva estructura (3-level hierarchy)
  ├─ Level 3 modules (bulk, analysis, managers) NEW
  ├─ 100% backward compatible
  └─ Zero breaking changes
```

---

*Documento: ARCHITECTURE.md*
*Generado: Marzo 2026*
*Revisión: PR #16*
