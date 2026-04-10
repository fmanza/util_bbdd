# 🏗️ Arquitectura de util_bbdd

**Versión:** 0.6.7
**Última Actualización:** Abril 2026
**Estado:** Estable | Completamente Refactorizado
**Motores Soportados:** MariaDB • PostgreSQL • Oracle • SQLite • HSQLDB • SQL Server

---

## 📋 Tabla de Contenidos

1. [Visión General](#visión-general)
2. [Principios de Diseño](#principios-de-diseño)
3. [Estructura Modular](#estructura-modular)
4. [APIs Públicas](#apis-públicas)
5. [Flujos de Operación](#flujos-de-operación)
6. [Capas de Abstracción](#capas-de-abstracción)
7. [Decisiones Arquitectónicas](#decisiones-arquitectónicas)
8. [Performance & Caché](#performance--caché)
9. [Extensión & Contribución](#extensión--contribución)

---

## 🎯 Visión General

**util_bbdd** es una librería que proporciona abstracción unificada para operaciones con múltiples motores de base de datos, enfatizando:

- **Migraciones explícitas**: v0.6.0 introdujo cambios controlados en el subsistema de grafos y documentación; v0.6.1 consolidó semántica visual y v0.6.2 cierra la capa documental con payloads compartidos y portabilidad offline
- **Jerarquía de 3 niveles**: Foundation → Services → Specialization
- **API moderna**: Managers sync/async con soporte nativo para async/await
- **Type-safe**: Full type hints con validación en tiempo de desarrollo
- **Modular**: Cada componente tiene responsabilidad única y clara
- **Grafos multinivel**: análisis por profundidad y sentido con modelo intermedio reutilizable

### Dependencias Principales

```
[SQL Drivers]
  ↓
SQLAlchemy (engine abstraction)
  ↓
util_bbdd (domain logic)
  └─→ pandas (for bulk ops)
  └─→ graphviz/matplotlib (for visualization)
```

---

## 🧭 Principios de Diseño

### 1. **Single Responsibility**
Cada módulo resuelve exactamente un problema:
- `connection/` → gestión de pools y conexiones
- `metadata/` → lectura y cache de esquema
- `query/` → registro y ejecución de queries
- `results/` → normalización de respuestas

### 2. **Dependency Injection**
Los managers inyectan sus dependencias, no las crean internamente:
```python
managers = SyncDatabaseManager(
    db_type="mariadb",
    conn_params={...},
    cache_metadata=True
)
```

### 3. **Protocol-based Design**
Interfaces (_core/contracts.py) definen contratos sin acoplar a implementaciones.

### 4. **No Ciclos de Importación**
Estructura clara: Level 1 → Level 2 → Level 3 (nunca al revés)

### 5. **Migración controlada**
El repositorio mantiene compatibilidad selectiva en algunos wrappers históricos, pero desde v0.6.0 la retrocompatibilidad ya no se trata como regla absoluta en el subsistema de grafos y documentación.

---

## 🏢 Estructura Modular

### Hay una estructura jerárquica de 3 niveles:

```
📦 util_bbdd (root exports públicas)
│
├─── LEVEL 1: ABSTRACCIONES (Foundation Layer)
│    └─ Define tipos, excepciones y contratos
│
│    _core/                          ⭐ Core abstractions
│    ├── types.py                    # Type aliases específicas de util_bbdd
│    ├── exceptions.py               # DatabaseException y jerarquía completa (única fuente de verdad)
│    ├── contracts.py                # Protocols base (ConnectionProvider, etc.)
│    └── constants.py                # Enums compartidos
│
│    _drivers/                       🔌 Level 1 support (no importar desde Level 2+)
│    ├── validator.py                # DatabaseTypeValidator: valida motores desde database_types.json
│    ├── driver_validator.py         # DriverValidator: detecta disponibilidad de drivers Python
│    └── _config_loader.py           # Carga y tipado del JSON de configuración de motores
│
│    core/                           📊 Motor capabilities
│    └── capabilities.py             # Detecta async support, features por motor
│
├─── LEVEL 2: SERVICIOS (Services Layer)
│    └─ Operaciones core reutilizables entre managers
│
│    connection/                     🔌 Gestión de conexiones (1,305 LOC)
│    ├── factory.py                  # ConnectFactory.create_connection/async
│    ├── builder.py                  # build_conn_params() por motor
│    ├── protocols.py                # ConnectionPoolProtocol
│    ├── close.py                    # parse_close_timeout(), run_close_operation_*
│    ├── motors/                     # Adaptadores por motor
│    │   ├── mariadb.py
│    │   ├── postgresql.py
│    │   ├── oracle.py
│    │   ├── sqlite.py
│    │   ├── hsqldb.py
│    │   └── sqlserver.py
│    └── params.py, config.py, pool.py
│
│    query/                          ❓ Registro y ejecución
│    ├── registry.py                 # QueryRegistry: carga y acceso a definiciones JSON
│    ├── resolver.py                 # QueryResolver: resuelve placeholders en queries
│    └── queries.py                  # DatabaseQueries: wrapper de conveniencia multi-motor
│
│    executors/                      ⚡ Ejecución de queries
│    ├── base.py                     # QueryExecutorBase (abstract)
│    ├── sync_query_executor.py      # Ejecución sincrónica
│    └── async_query_executor.py     # Ejecución asincrónica
│
│    metadata/                       🔍 Lectura y cache de schema (887 LOC)
│    ├── cache.py                    # DatabaseMetadataCache + RelationshipMetadataCache
│    ├── normalizer.py               # Normaliza respuestas de metadata
│    ├── builder.py                  # DDLBuilder - construye queries DDL
│    ├── fetcher.py                  # MetadataFetcher - obtiene schema
│    ├── manager.py                  # MetadataManager - orquesta operaciones
│    ├── contracts.py                # Interfaces y tipos
│    ├── mariadb/                    # Helpers específicos de MariaDB
│    │   ├── adapters.py
│    │   ├── helpers.py
│    │   └── types.py
│    └── providers/                  # Providers (Sync/Async)
│
│    results/                        📋 Normalización de resultados (74 LOC)
│    ├── types.py                    # RowOrNone, Rows, etc.
│    └── normalizer.py               # ResultNormalizer
│
│    factory/                        🏭 SQLAlchemy engines
│    ├── pool_factory.py
│    ├── sqlalchemy_engine_factory.py
│    └── async_sqlalchemy_engine_factory.py
│
│    validators/                     ✓ Validadores adicionales
│    └── (implementations)
│
├─── LEVEL 3: ESPECIALIZACIÓN (Specialization Layer)
│    └─ Funcionalidad de dominio construida sobre Level 2
│
│    managers/                       🎛️ Managers principal (2,200+ LOC)
│    ├── sync_mgr.py                 # SyncDatabaseManager (1,000+ LOC)
│    │   └── Interfaz principal para operaciones sync
│    └── async_mgr.py                # AsyncDatabaseManager (700+ LOC)
│        └── Interfaz principal para operaciones async
│
│    bulk/                           📦 Bulk operations (2,129 LOC)
│    ├── crud.py                     # Bulk INSERT/UPDATE/DELETE desde DataFrames
│    ├── audit.py                    # AuditManager para tracking de cambios
│    └── normalize.py                # Normalización de registros para SQL
│
│    analysis/                       📊 Análisis de relaciones multinivel
│    ├── base.py                     # GraphDocument, niveles, traversal y dirección
│    ├── graphviz.py                 # Visualización con Graphviz
│    ├── graphviz_ext.py             # Graphviz multinivel con columnas/cardinalidad
│    └── matplotlib_graph.py         # Visualización Matplotlib alineada al modelo multinivel
│
│    comparar/                       🔍 Comparación de esquemas
│    ├── comparator.py               # SchemaComparator.compare(source, target) → SchemaDiff
│    ├── contracts.py                # Tipos y contratos de comparación
│    └── models.py                   # SchemaDiff (frozen dataclasses)
│
│    [Otros módulos]
│    ├── async_utils.py              # Helpers (maybe_await, etc.)
│    ├── models.py                   # Modelos de dominio
│    ├── data/                       # Data fixtures para tests
│    └── doc/                        # HTML/Excel/Word doc generation (Jinja2)
│
└─── COMPATIBILIDAD (Legacy Wrappers - Raíz)
    └─ Solo se conservan wrappers que no tienen equivalente directo en el paquete:

     database_manager.py             → Deprecated (usa SyncDatabaseManager)
     async_database_manager.py       → managers.async_mgr
     bulk_crud.py                    → bulk.crud
     grafos.py                       → analysis/
```

---

## � APIs Públicas

### Importes Recomendados (desde raíz)

```python
# Managers principales (RECOMENDADO)
from util_bbdd import SyncDatabaseManager, AsyncDatabaseManager

# Providers de metadata
from util_bbdd import DatabaseMetadataCache, RelationshipMetadataCache
from util_bbdd import SyncMetadataProvider, AsyncMetadataProvider

# Helpers
from util_bbdd import ConnectionFactory, PoolFactory, build_conn_params

# Async utilities
from util_bbdd import maybe_await
```

### APIs por Módulo (Directas)

#### `managers/` - Interfaces Principales

```python
# Sync (recomendado para la mayoría de casos)
from util_bbdd.managers import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="mariadb",
    conn_params={"host": "localhost", "user": "root", ...},
    cache_metadata=True
)

# Operaciones básicas
rows = manager.execute("SELECT * FROM users WHERE id = ?", [1])
manager.execute("INSERT INTO users (name) VALUES (?)", ["John"])

# Async (cuando sea necesario)
from util_bbdd.managers import AsyncDatabaseManager

async_manager = AsyncDatabaseManager(...)
rows = await async_manager.execute_async("SELECT ...")
```

#### `connection/` - Creación de Conexiones

```python
from util_bbdd.connection import ConnectionFactory, build_conn_params

# Construir parámetros normalizados
params = build_conn_params(
    "mariadb",
    host="localhost",
    user="root",
    password="secret",
    database="test"
)

# Crear conexión única
conn = ConnectionFactory.create_connection("mariadb", params)

# Crear conexión async
async_conn = await ConnectionFactory.create_async_connection("mariadb", params)
```

#### `bulk/` - Operaciones Masivas

```python
from util_bbdd.bulk import bulk_crud, AuditManager
import pandas as pd

# Bulk CRUD desde DataFrame
mgr = bulk_crud(db_manager.engine)
df = pd.read_csv("data.csv")

# Inserts masivos
mgr.bulk_insert_from_df(df, "users", batch_size=1000)

# Updates masivos
mgr.bulk_update_from_df(df, "users", key_column="id")

# Audit trail
audit = AuditManager("audit.json")
with audit.registrar_operacion("INSERT", "users") as tx:
    # Operación aquí
    tx.registrar_cambio("name", "old", "new")
```

#### `analysis/` - Análisis de Relaciones

```python
from util_bbdd.analysis import GraphvizRelationshipGraphExt, MatplotlibRelationshipGraph

# Grafo multinivel con Graphviz
graph = GraphvizRelationshipGraphExt(
    db_manager,
    max_depth=3,
    direction="both",
    column_mode="relations",
)
graph_data = graph.generate_graphviz_graph_paginated_ext(
    table_name="users",
    output_dir="./graphs",
    max_subnodes=10,
)

# Grafo multinivel con Matplotlib
mgraph = MatplotlibRelationshipGraph(db_manager, max_depth=2, direction="incoming")
figure_paths = mgraph.generate_matplotlib_graph_paginated("users", output_dir="./graphs")
```

#### `metadata/` - Lectura de Schema

```python
from util_bbdd.metadata import DatabaseMetadataCache, MetadataManager

# Cache de metadatos
cache = DatabaseMetadataCache()
tables = cache.get_tables(connection)
columns = cache.get_columns(connection, "users")

# Manager (nivel superior)
metadata_mgr = MetadataManager(db_manager)
pk = metadata_mgr.get_primary_keys(connection, "users")
fks = metadata_mgr.get_foreign_keys(connection, "users")
```

#### `query/` - Registro y Ejecución de Queries

```python
from util_bbdd.query import DatabaseQueries, DatabaseQueryResolver

# Cargar queries desde JSON
queries = DatabaseQueries.load("queries.json")

# Resolver placeholders
resolver = DatabaseQueryResolver(queries)
resolved_query = resolver.resolve("get_user_by_id", {"user_id": 5})

# Ejecutar (a través de manager)
result = manager.execute(resolved_query)
```

### Tipos Públicos

```python
# Excepciones — directamente desde el paquete raíz (canónico desde v0.6.7)
from util_bbdd import (
    DatabaseException,
    ConnectionError, PoolConnectionError, PoolTimeoutError, PoolExhaustedError,
    ValidationError, InvalidDatabaseType,
    DriverError,
    DatabaseOperationError, DatabaseConfigurationError,
    QueryError, QueryNotFoundError, QueryValidationError,
    QueryParameterError, QueryTimeoutError, QueryExecutionError,
)

# Desde results
from util_bbdd.results import RowOrNone, Rows
# RowOrNone = dict[str, Any] | None
# Rows = list[dict[str, Any]]

# Comparación de esquemas
from util_bbdd import SchemaComparator, SchemaDiff
```

---

## 🔄 Flujos de Operación

### Flujo 1: Ejecutar Query Simple

```
Usuario llama manager.execute("SELECT ...")
                ↓
         SyncDatabaseManager
                ↓
    ┌── Obtener conexión (connection.factory)
    ├── Ejecutar query (executors.sync_query_executor)
    ├── Normalizar resultado (results.normalizer)
    └── Retornar resultado
```

### Flujo 2: Bulk Insert desde DataFrame

```
Usuario: bulk_crud.bulk_insert_from_df(df, "users")
                ↓
         bulk/crud.py
                ↓
    ┌── Normalizar registros (bulk/normalize.py)
    ├── Obtener metadata tabla (metadata/fetcher)
    ├── Construir INSERT statements (SQLAlchemy)
    ├── Ejecutar en batches (connection/pool)
    └── Registrar en audit si activado
```

### Flujo 3: Analizar Relaciones de BD

```
Usuario: graph.build_graph_document() / graph.generate_graphviz_graph_paginated_ext()
                ↓
            analysis/base.py + graphviz_ext.py
                ↓
        ├── Obtener FKs/relaciones (metadata + cache)
        ├── Construir GraphDocument por niveles y dirección
        ├── Aplicar política de columnas y cardinalidad
        ├── Renderizar por formato (Graphviz/HTML/Word/Matplotlib)
    └── Retornar/guardar imagen
```

### Flujo 4: Obtener Metadatos Cacheados

```
Usuario: metadata_mgr.get_columns(conn, "users")
                ↓
      MetadataManager
                ↓
    ├─ ¿Está en cache?
    │  ├─ SÍ → Retornar
    │  └─ NO → Siguiente paso
    ├── Construir DDL query (metadata.builder)
    ├── Ejecutar query (metadata.fetcher)
    ├── Normalizar respuesta (metadata.normalizer)
    ├── Guardar en cache
    └── Retornar resultado normalizado
```

---

## 🧅 Capas de Abstracción

### Nivel 1: Foundation (Abstracciones Puras)

**Responsabilidad:** Definir contratos y tipos compartidos sin implementación.

```python
# contracts.py - Que debe cumplir cada ConnectionProvider
class ConnectionProvider(Protocol):
    def get_connection(self) -> Any: ...

# exceptions.py - Jerarquía clara de errores
DatabaseException
├── ConnectionError
├── QueryError
├── MetadataError
├── ValidationError
└── DriverError
```

**Ventajas:**
- Zero business logic
- Cambios no afectan implementaciones
- Fácil testing

### Nivel 2: Services (Implementaciones Reutilizables)

**Responsabilidad:** Implementar operaciones core una sola vez.

```python
# connection.factory.ConnectionFactory
# ↓ Usado por:
# - SyncDatabaseManager
# - AsyncDatabaseManager
# - Tests

# metadata.cache.DatabaseMetadataCache
# ↓ Usado por:
# - SyncMetadataProvider
# - AsyncMetadataProvider
# - MetadataManager
```

**Ventajas:**
- DRY - No Repeat Yourself
- Cambios centralizados
- Fácil evolución

### Nivel 3: Specialization (Funcionalidad de Dominio)

**Responsabilidad:** Combinar Level 1+2 para resolver problemas del usuario.

```python
# managers.SyncDatabaseManager
# = Connection + Query + Metadata + Results
# + capa de coordinación superior

# bulk.crud.bulk_crud
# = Manager + DataFrame + Normalizador
# + lógica de batching

# analysis.base.DatabaseRelationshipGraphBase
# = Manager + Metadata
# + algoritmo de analysis
```

---

## ⚙️ Decisiones Arquitectónicas

### D1: ¿Por qué 3 niveles en lugar de 1 o 2?

**Beneficio:** Separación de concerns clara
- Foundation: API stable, cambios raros
- Services: Compartir lógica sin acoplamiento
- Specialization: Fácil agregar nuevas features

**Trade-off:** Más archivos, pero cada uno con responsabilidad clara.

### D2: ¿Por qué migración controlada en lugar de retrocompatibilidad total?

**Razón:** v0.6.0 necesitó simplificar el contrato de grafos para soportar profundidad, dirección y políticas de columnas sin perpetuar deuda técnica, y v0.6.1 aprovecha ese contrato estable para extender semántica visual y reutilización documental.

```python
# El código legacy puede seguir existiendo en rutas históricas,
# pero el flujo recomendado del subsistema de grafos es el contrato consolidado en v0.6.x.
```

**Mecanismo:** mantener compatibilidad solo donde el coste sea razonable y documentar migraciones cuando el cambio estructural lo requiera.

### D3: ¿Por qué managers son Layer 3, no Layer 2?

**Razón:** SyncDatabaseManager depende de TODAS las capas

```
SyncDatabaseManager
    ├── connection (Layer 2)
    ├── query (Layer 2)
    ├── metadata (Layer 2)
    ├── results (Layer 2)
    ├── executors (Layer 2)
    └── factory (Layer 2)
```

Si fuera Layer 2, crearía dependencia circular con otros servicios.

### D4: ¿Por qué no hay ORM (como Pydantic)?

**Razón:** util_bbdd es "bare SQL" a propósito

- Usuarios pueden layerear ORM encima
- SQLAlchemy ya es bastante completo
- Mantiene librería lean

### D5: Async vs Sync Managers

**Diseño:** AsyncDatabaseManager ES la interfaz moderna

```python
# ✅ Recomendado para código nuevo
manager = AsyncDatabaseManager(...)
await manager.execute_async(...)

# ✅ Retrocompatible (sigue siendo recomendado)
manager = SyncDatabaseManager(...)
manager.execute(...)

# ❌ Combinación NO soportada
await manager.execute_async(...)  # ← No, este manager es sync
```

---

## 📊 Performance & Caché

### Estrategia de Caché

```
Nivel de Cache        TTL        Actualización
─────────────────────────────────────────────────
Connection Pool       ∞          Manual (close)
Metadata Schema      5 min      Automática
Query Compiled       ∞          Manual (clear)
Relationship Index   5 min      Automática
```

### Ejemplos de Tuning

```python
# Ampliar cache de metadata
manager = SyncDatabaseManager(
    db_type="mariadb",
    conn_params={...},
    cache_metadata=True,
    metadata_cache_ttl=600  # 10 minutos
)

# Ejecutar bulk sin overhead de metadata
mgr.bulk_crud.bulk_insert_from_df(
    df,
    table_name="users",
    batch_size=5000,           # Batches mayores
    fetch_metadata=False       # Saltarse metadata
)

# Preparar conexión reutilizable
conn = manager._pool.connection()
for i in range(1000):
    result = manager.execute("SELECT ...", conn=conn)
conn.close()
```

### Medición

```python
import time

start = time.time()
result = manager.execute("SELECT ...")
elapsed = time.time() - start

# Logs internos incluyen timings
# Ver manager.logger.debug(...)
```

---

## 🔧 Extensión & Contribución

### Agregar Nuevo Motor de BD

**Pasos:**

1. **Adaptador de Conexión** → `connection/motors/mynewdb.py`
   ```python
   class MyNewDBConnectionAdapter:
       @staticmethod
       def create_connection(params: dict) -> Connection: ...
       @staticmethod
       async def create_async_connection(params: dict) -> Connection: ...
   ```

2. **Registrar en Factory** → `connection/factory.py`
   ```python
   ConnectionFactory.register("mynewdb", MyNewDBConnectionAdapter)
   ```

3. **Capabilities** → `core/capabilities.py`
   ```python
   MOTOR_CAPABILITIES["mynewdb"] = {
       "supports_async": True,
       "supports_bulk": True,
       ...
   }
   ```

4. **Tests** → `tests/test_mynewdb_*.py`

5. **Documentación** → README.md + ARCHITECTURE.md

### Agregar Nuevo Feature a un Manager

1. Agregar método a `SyncDatabaseManager`
2. Espejo async a `AsyncDatabaseManager`
3. Asegurar retrocompatibilidad
4. Tests + documentación

### Reportar Issues

- Incluir: BD, versión, stack trace completo
- Reproducible en test aislado
- No datos sensibles

---

## 📚 Referencias

- [CHANGELOG.md](../CHANGELOG.md) - Historial de versiones
- [README.md](../README.md) - Guía de usuario
- [REFACTORING_SESSION_PROGRESS.md](./REFACTORING_SESSION_PROGRESS.md) - Progreso v0.5.0+
- [pytest.ini](../pytest.ini) - Configuración de tests
- [Requirements](../requirements.txt) - Dependencias

---

*Documento actualizado: Abril 2026 - alineado a v0.6.7*
*Mantenedor: util_bbdd contributors*
*Licencia: [Ver LICENSE](../LICENSE)*
