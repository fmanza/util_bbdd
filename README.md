# util_bbdd

Librería Python especializada en **operaciones de base de datos** para MariaDB, Oracle, PostgreSQL, SQLite, SQL Server y HSQLDB (sync).

**Version:** 0.6.3 | **Status:** ✅ Estable

**Compatibilidad Python:** 3.12+

Incluye:
- ✅ **CRUD en lote** desde DataFrames (insert/update/delete masivo)
- ✅ **Auditoría automática** en CSV con timestamps
- ✅ **Gestión de conexiones** con pool singleton
- ✅ **Gestión async** de conexiones/pools (por motor compatible)
- ✅ **Análisis de relaciones** - Generar grafos de relaciones
- ✅ **Documentación de BD** generada automáticamente
- ✅ **Plantillas HTML Jinja2 modulares** con páginas globales `Ver todo`
- ✅ **Validación de tipos** por dialecto SQL
- ✅ **Arquitectura 3-level** jerárquica y modular (NEW in v0.5.0)

## Flujo de trabajo con Copilot

El repositorio define una capa combinada de instrucciones, prompts y agentes para trabajar con cambios funcionales, hotfixes, auditorías y cierres.

- La política base está en [.github/copilot-instructions.md](.github/copilot-instructions.md).
- La jerarquía de decisión y los agentes disponibles están en [.github/README.md](.github/README.md).
- El ejemplo completo de uso está en [docs/examples/github_usage_complete_example.md](docs/examples/github_usage_complete_example.md).

Cadena recomendada para tareas complejas:

```text
Workflow Director -> Plan Architect -> Feature Implementer o Hotfix Responder -> Code Auditor -> Version Closer
```

Mapa rápido:

| Necesidad | Prompt habitual | Agente recomendado |
|---|---|---|
| Nueva funcionalidad | `new_feature` | `Plan Architect` y luego `Feature Implementer` |
| Hotfix acotado | `hotfix` | `Hotfix Responder` |
| Refactor sin cambio funcional | `refactor` | `Plan Architect` y luego `Feature Implementer` |
| Auditoría técnica | `audit_code` | `Code Auditor` |
| Revisión de seguridad | `security_review` | `Security Reviewer` |
| Cierre de versión o sesión | `version_closure` | `Version Closer` |

## Soporte Async por Motor

| Motor      | Conexión Async | Pool Async | Driver principal |
|------------|----------------|------------|------------------|
| PostgreSQL | ✅             | ✅         | `asyncpg`        |
| SQLite     | ✅             | ✅         | `aiosqlite`      |
| MariaDB    | ✅             | ✅         | `aiomysql`       |
| Oracle     | ✅             | ✅         | `oracledb`       |
| SQL Server | ✅             | ✅         | `aioodbc`        |
| HSQLDB     | ❌             | ❌         | N/A              |

Nota: `hsqldb` no dispone de implementación async en `util_bbdd`. Las factorías async lanzan error explícito para ese motor.

---

## ⚡ Quick Start (5 minutos)

### Instalación

```bash
pip install util_bbdd
```

### PostgreSQL — Sync

```python
from util_bbdd import SyncDatabaseManager

# Conectar a la BD
manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
        "database": "mydb"
    }
)

# Listar tablas
tables = manager.get_tables()
print("Tablas:", [table[0] for table in tables])

# Obtener columnas de una tabla
columns = manager.get_columns("users")
print("Columnas:", columns)

# Ejecutar query personalizadas
result = manager.execute_custom_many("SELECT * FROM users LIMIT 5")
print("Usuarios:", result)

# Cerrar conexión
manager.close()
```

### PostgreSQL — Async

```python
import asyncio
from util_bbdd import AsyncDatabaseManager

async def main():
    # Conectar a la BD
    manager = AsyncDatabaseManager(
        db_type="postgresql",
        conn_params={
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "secret",
            "database": "mydb"
        }
    )

    # Inicializar el manager
    await manager.init()

    # Listar tablas
    tables = await manager.get_tables()
    print("Tablas:", [table[0] for table in tables])

    # Cerrar conexión
    await manager.close()

asyncio.run(main())
```

### SQLite — Sin configuración

```python
from util_bbdd import SyncDatabaseManager

# Usar BD en memoria para testing
manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
)

# Crear tabla de prueba
manager.execute_custom_many(
    "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)"
)

tables = manager.get_tables()
print("Tablas:", tables)

manager.close()
```

### MariaDB / MySQL

```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="mariadb",  # o "mysql"
    conn_params={
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "secret",
        "database": "mydb"
    }
)

tables = manager.get_tables()
print("Tablas:", [table[0] for table in tables])

manager.close()
```

### Oracle

```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="oracle",
    conn_params={
        "host": "localhost",
        "port": 1521,
        "user": "admin",
        "password": "secret",
        "sid": "ORCL"  # o "service_name": "xepdb1"
    }
)

tables = manager.get_tables()
print("Tablas:", [table[0] for table in tables])

manager.close()
```

#### 📌 Ver más

- [Guía de instalación completa](docs/INSTALLATION.md)
- [Guía de excepciones](docs/EXCEPTIONS.md)
- [SchemaComparator — Comparación de esquemas](docs/COMPARATOR.md)

---

## Arquitectura v0.6.7 - Estructura de 3 Niveles (Estable)

Util_bbdd usa una **arquitectura jerárquica de 3 niveles** para máxima modularidad, extensibilidad y separación de responsabilidades:

### Level 1: Abstracciones Internas (Foundation Layer)

Define tipos, excepciones y contratos. **Regla:** No importar desde Level 2 ni 3.

```
_core/               # Tipos y contratos fundamentales
  ├── types.py       # Type aliases (RowOrNone, Rows, etc.)
  ├── exceptions.py  # Jerarquía unificada de excepciones (DatabaseException raíz)
  ├── contracts.py   # Protocols/interfaces (ConnectionProvider, etc.)
  └── constants.py   # Enums compartidos

_drivers/            # Gestión de drivers y capabilities (no desde Level 2+)
  ├── validator.py   # DatabaseTypeValidator: valida motores desde database_types.json
  ├── driver_validator.py # DriverValidator: detecta disponibilidad de drivers Python
  ├── capabilities.py # Detecta soporte async y features por motor
  └── _config_loader.py # Carga y tipado del JSON de configuración

core/
  └── capabilities.py # Motor capabilities (async support, features)
```

**Beneficio:** Punto único de verdad para excepciones y contratos; facilita evolución sin quebrantar interfaces.

### Level 2: Capas de Acceso (Services Layer)

Operaciones core reutilizables entre managers. **Regla:** Solo importar desde Level 1; nunca desde Level 3.

```
connection/          # Pool, factory, configuración (≈1,305 LOC)
  ├── factory.py     # ConnectFactory.create_connection/async
  ├── builder.py     # build_conn_params() por motor
  ├── protocols.py   # ConnectionPoolProtocol
  ├── close.py       # Cierre de conexiones y cleanup
  ├── motors/        # Adaptadores por motor (mariadb, postgresql, oracle, etc.)
  ├── pool.py        # Pool management
  ├── params.py      # Parameters normalization
  └── config.py      # Connection configuration

query/               # Registry y ejecución (≈314 LOC base)
  ├── registry.py    # QueryRegistry: carga y acceso a definiciones JSON
  ├── resolver.py    # QueryResolver: resuelve placeholders en queries
  ├── queries.py     # DatabaseQueries: wrapper de conveniencia
  └── executors/     # Executor implementations
      ├── base.py    # QueryExecutorBase (abstract)
      ├── sync_query_executor.py
      └── async_query_executor.py

metadata/            # Lectura y cache de schema (≈887 LOC)
  ├── cache.py       # DatabaseMetadataCache + RelationshipMetadataCache
  ├── normalizer.py  # Normaliza respuestas de metadata
  ├── builder.py     # DDLBuilder - construye queries DDL
  ├── fetcher.py     # MetadataFetcher - obtiene schema
  ├── manager.py     # MetadataManager - orquesta operaciones
  ├── contracts.py   # Interfaces y tipos de metadata
  ├── mariadb/       # Helpers específicos de MariaDB
  └── providers/     # Sync/AsyncMetadataProvider

results/             # Normalización de resultados (≈74 LOC)
  ├── types.py       # RowOrNone, Rows, tipos de resultado
  └── normalizer.py  # ResultNormalizer

factory/             # SQLAlchemy engines
  ├── pool_factory.py
  ├── sqlalchemy_engine_factory.py
  └── async_sqlalchemy_engine_factory.py

validators/          # Validadores adicionales por negocio
  └── (implementations)
```

**Beneficio:** Cada módulo < 500 LOC, responsabilidad única, fácil testear en aislamiento.

### Level 3: Especialización (Domain Logic Layer)

Funcionalidad de dominio construida sobre Level 2. **Regla:** Puede importar de Level 1 y 2, nunca al revés.

```
managers/            # APIs públicas de alto nivel (≈2,200+ LOC)
  ├── sync_mgr.py    # SyncDatabaseManager (1,000+ LOC)
  │   └── Interfaz principal para operaciones sync
  └── async_mgr.py   # AsyncDatabaseManager (700+ LOC)
      └── Interfaz principal para operaciones async

bulk/                # Operaciones masivas (≈2,129 LOC)
  ├── crud.py        # Bulk INSERT/UPDATE/DELETE desde DataFrames (999 LOC)
  ├── audit.py       # AuditManager para tracking de cambios (866 LOC)
  └── normalize.py   # Normalización de registros para SQL (264 LOC)

analysis/            # Análisis de relaciones multinivel (≈1,500+ LOC)
  ├── base.py        # GraphDocument, niveles, traversal, dirección, tipología visual
  ├── graphviz.py    # Visualización con Graphviz base
  ├── graphviz_ext.py# Graphviz multinivel con columnas, cardinalidad, leyenda
  └── matplotlib_graph.py # Matplotlib alineado al modelo multinivel

comparar/            # Comparación de esquemas (NEW in v0.6.7)
  ├── comparator.py  # SchemaComparator.compare(source, target) → SchemaDiff
  ├── contracts.py   # Tipos y contratos de comparación
  └── models.py      # SchemaDiff (frozen dataclasses), resultados tipados

doc/                 # Generadores documentales
  ├── template_engine.py # Motor Jinja2 personalizado
  ├── html_generator.py # HTML generado + offline SVG
  ├── excel_generator.py # Excel desde pandas
  ├── word_generator.py # Word desde python-docx
  └── templates/     # Plantillas Jinja2 modulares
      ├── layouts/   # Estilos base (HTML/CSS)
      ├── macros/    # Bloques reutilizables
      └── pages/     # Páginas completas y módulos

[Otros]
├── async_utils.py   # Helpers (maybe_await, etc.)
├── models.py        # Modelos de dominio compartidos
└── data/            # Data fixtures para tests
```

**Beneficio:** Dominio enfocado, sin acoplamiento a infraestructura; fácil agregar nuevos formatos/motores sin editar Level 2.

### Regla de Imports (Flujo Prohibido ↔ Permitido)

```
✅ PERMITIDO (jerarquía descendente)
   Level 1 imports ← ninguno (capa base)
   Level 2 imports ← Level 1
   Level 3 imports ← Level 1, Level 2

❌ PROHIBIDO (círculos o ascensión)
   Level 2 imports from Level 3
   Level 1 imports from Level 2 o 3
   Ciclos internos entre Level 3
```

### Compatibilidad Viva (v0.6.7)

La ruta recomendada para código nuevo usa **imports canónicos** desde la raíz del paquete. Rutas legacy se mantienen solo como transición.

| Componente | Import Canónico (Recomendado) | Ruta Legacy (Deprecated) |
|---|---|---|
| Manager sync | `from util_bbdd import SyncDatabaseManager` | `from util_bbdd.database_manager import DatabaseManager` |
| Manager async | `from util_bbdd import AsyncDatabaseManager` | `from util_bbdd.async_database_manager import AsyncDatabaseManager` |
| Bulk operations | `from util_bbdd.bulk import bulk_crud, AuditManager` | `from util_bbdd.bulk_crud import bulk_crud, AuditManager` |
| Analysis graphs | `from util_bbdd.analysis import GraphvizRelationshipGraphExt` | `from util_bbdd.grafos import GraphvizRelationshipGraphExt` |
| Comparator | `from util_bbdd import SchemaComparator, SchemaDiff` | N/A (nuevo en v0.6.7) |
| Driver validator | `from util_bbdd._drivers.validator import DatabaseTypeValidator` | `from util_bbdd.database_type_validator import DatabaseTypeValidator` |

**Notas de compatibilidad activa:**

- El código nuevo debe preferir la superficie canónica expuesta desde `util_bbdd`, `util_bbdd.managers`, `util_bbdd.bulk` y `util_bbdd.analysis`.
- Las rutas legacy se mantienen para no romper integraciones existentes, pero ya no son la referencia principal en ejemplos ni en migraciones.
- `get_storage_inventory()` usa el contrato actual por capacidades: `primary`, `temp_tablespaces` y `sqlite_file_summary` cuando aplica.
- La guía de detalle para migrar imports y contratos está en [docs/MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md).

## ✨ Novedades v0.6.7 (Estable Vigente)

### Comparación de Esquemas (NEW)
- `SchemaComparator.compare(source, target)` → `SchemaDiff` tipado
- Detección de cambios: tablas, columnas, claves, índices, vistas
- Soporte multi-motor: diferencias de sintaxis DDL normalizadas
- Extensible: `_ROUTINE_FETCHERS` y `_DDL_STRIP_RULES` por motor (OCP)

### Capa de Agentes y Flujo Estructurado
- Instrucciones especializadas para Copilot Chat y Claude Code
- Flujo `PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION`
- 10 agentes disponibles (Plan Architect, Feature Implementer, Code Auditor, etc.)
- Mapeo documentado entre plataformas (Claude Code ↔ Copilot Chat)

### Mejoras en Arquitectura
- Jerarquía de imports explícita: Level 1 → 2 → 3 (nunca reversa)
- Excepciones tipadas desde raíz con `from util_bbdd import DatabaseException, ConnectionError, ...`
- Compatibilidad viva: rutas legacy solo como transición hacia imports canónicos

---

## 📚 Resumen de Evolución (v0.6.0 → v0.6.7)

### v0.6.2 - Cierre Documental Offline
- Relaciones de n niveles mediante `max_depth`
- Dirección configurable: `incoming`, `outgoing` o `both`
- Modos de visualización: `compact`, `relations`, `all`
- Cardinalidad en Graphviz (extremos)
- HTML con pestañas por nivel/sentido
- Payloads compartidos entre HTML y Word
- SVG inline con zoom/paneo offline

### v0.6.3 - Agentes de Copilot
- Capa de agentes y flujo prompt-agente documentado
- Instrucciones por archivo (.instructions.md)
- Mapeo Copilot Chat → Claude Code

### v0.6.4 → v0.6.6 - Consolidación
- Capa de managers estabilizada
- Testeo multinivel
- Documentación evolucionada

### v0.6.7 - Estable Vigente
- Comparador de esquemas integrado (SchemaDiff)
- Imports canónicos desde raíz
- Instrucción.md por área especializada
- Esta estructura (3 niveles) como standard de evolución

---

### Tipología Visual de Tablas (v0.6.2+, vigente en v0.6.7)

La clasificación visual de tablas en diagramas NO sustituye el modelo de datos real, sino que ofrece ayuda visual heurística:

- `entity`: tabla de negocio general (color azul pastel)
- `association`: tabla puente detectada por múltiples FKs (color verde pastel)
- `hierarchy`: tabla autorreferencial con relación padre-hijo (color naranja pastel)

Si un esquema contiene tablas híbridas o patrones muy específicos por motor, la tipología debe interpretarse como ayuda visual y no como clasificación canónica.

### Configuración recomendada del bloque grafo

```toml
[imprimir_config.imprimir.grafo]
enabled = true
show_columns = true
max_depth = 3
direction = "both"
images_paginated = true
max_subnodes = 10

[imprimir_config.imprimir.grafo.summary]
enabled = true

[imprimir_config.imprimir.grafo.columns]
mode = "relations"
max_items = 8
show_data_types = false

[imprimir_config.imprimir.grafo.cardinality]
style = "end_markers"
show_constraint_name = false
```

`show_columns` sigue siendo el interruptor global para el detalle tabular del grafo:

- `true`: se muestran columnas segun `grafo.columns.mode`
- `false`: los nodos se renderizan sin columnas aunque el bloque `grafo.columns` exista

### Ejemplo completo de imprimir_config

Existe un ejemplo completo, autocomentado y alineado con el contrato actual en:

- [docs/examples/imprimir_config_full_example.toml](docs/examples/imprimir_config_full_example.toml)

Ese fichero documenta todas las secciones soportadas hoy por `imprimir`:

- tablas
- vistas
- rutinas
- almacenamiento
- columnas_charset
- info_database
- grafo
- opciones generales de Word y HTML

### Ejemplo de uso de diagramas multinivel

```python
from util_bbdd.analysis import GraphvizRelationshipGraphExt

graph = GraphvizRelationshipGraphExt(
  db_manager=dm,
  max_depth=3,
  direction="both",
  column_mode="relations",
  max_columns=8,
  show_data_types=False,
)

graph.generate_graphviz_graph_paginated_ext(
  table_name="users",
  output_dir="./graphs",
  format="svg",
  max_subnodes=10,
)
```

---

## Instalación

Requiere **Python 3.12 o superior**.

### Desde PyPI (futuro)
```bash
pip install util_bbdd
```

### Desde fuente (desarrollo)
```bash
git clone https://github.com/fmanza/util_bbdd.git
cd util_bbdd
py -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
pip install -e ".[dev]"
```

## Uso Rápido

### Inserción masiva desde DataFrame

```python
from util_bbdd.bulk import bulk_crud
import pandas as pd
from sqlalchemy import create_engine

# Crear engine
engine = create_engine("mysql+pymysql://user:password@localhost/database")

# Crear DataFrame con datos
df = pd.DataFrame({
    'id': [1, 2, 3],
    'name': ['Alice', 'Bob', 'Charlie'],
    'email': ['alice@ex.com', 'bob@ex.com', 'charlie@ex.com']
})

# Inicializar CRUD con auditoría
crud = bulk_crud_audit(
    engine=engine,
    table_name='users',
    audit_csv_path='audit.csv'
)

# Insertar en lote
crud.bulk_insert_from_df(df)
print("✅ Inserción completada")

# Ver auditoría
df_audit = pd.read_csv('audit.csv')
print(df_audit)
```

### Pool de Conexiones

```python
from util_bbdd.connection import PoolFactory

# Crear pool singleton
pool = PoolFactory.create(
    database_type='mysql',
    host='localhost',
    user='root',
    password='secret',
    database='mydb'
)

engine = pool.get_engine()
print(f"✅ Conexión establecida: {pool}")
```

## API Unificada: SyncDatabaseManager (v0.2.0+)

### Uso Síncrono

```python
from util_bbdd import SyncDatabaseManager

# Inicializar gestor de BD
dm = SyncDatabaseManager(
    db_type='mariadb',
    conn_params={
        'host': 'localhost',
        'user': 'root',
        'password': 'secret',
        'database': 'mydb'
    }
)

# Introspection: Listar tablas
tables = dm.get_tables()
print(f"📊 Tablas: {tables}")

# Introspection: Columnas de tabla
columns = dm.get_columns('users')
print(f"📋 Columnas: {columns}")

# Ejecutar query registrada (many / one)
result = dm.execute_query_many('obtener_tablas', database='mydb')
first_row = dm.execute_query_one('database_version')
print(f"🔍 Resultado: {result} | Primera fila: {first_row}")

# Ejecutar SQL custom (many / one)
result = dm.execute_custom_many('SELECT * FROM users LIMIT 10')
ping = dm.execute_custom_one('SELECT 1')
print(f"✅ Consulta ejecutada: {len(result)} filas")

# Cierra conexión
dm.close()
```

### Uso Asíncrono (v0.2.0+)

```python
import asyncio
from util_bbdd.managers import AsyncDatabaseManager

async def main():
    # Inicializar gestor async
    adm = AsyncDatabaseManager(
        db_type='postgresql',
        conn_params={
            'host': 'localhost',
            'user': 'postgres',
            'password': 'secret',
            'database': 'mydb'
        }
    )

    # Inicialización lazy
    await adm.init()

    # Misma API que sync, pero con await
    tables = await adm.get_tables()
    print(f"📊 Tablas: {tables}")

    columns = await adm.get_columns('users')
    print(f"📋 Columnas: {columns}")

    # Ejecutar query registrada (many / one)
    result = await adm.execute_query_many('obtener_tablas', database='mydb')
    first_row = await adm.execute_query_one('database_version')
    print(f"🔍 Resultado: {result} | Primera fila: {first_row}")

    await adm.close()

# Ejecutar
asyncio.run(main())
```

### Excepciones Unificadas (v0.2.0+)

| Excepción | Cuándo | Uso |
|-----------|--------|-----|
| `QueryNotFoundError` | Query no existe | `.handle_missing_query()` |
| `QueryValidationError` | Parámetros inválidos | `.validate_params()` |
| `QueryParameterError` | Parámetro específico inválido | `.check_param()` |
| `QueryTimeoutError` | Timeout en ejecución | `.retry_with_timeout()` |
| `DatabaseConnectionError` | Fallo de conexión | `.reconnect()` |
| `DatabasePoolError` | Pool exhausto/timeout | `.wait_for_pool()` |
| `DatabaseOperationError` | Error en operación SQL | `.handle_sql_error()` |

**Migración desde v0.1.x:**
```python
# v0.1.x (deprecated)
try:
    query = dq.get_query('nonexistent')
except KeyError:
    print("Query not found")

# v0.2.0+ (nuevo)
from util_bbdd.database_exceptions import QueryNotFoundError

try:
    query = dq.get_query('nonexistent')
except QueryNotFoundError as e:
    print(f"Query not found: {e}")
```

### Motores Soportados

| Motor      | Sync | Async | Validadores Avanzados | Versión +0.2 |
|------------|------|-------|----------------------|-------------|
| MariaDB    | ✅   | ✅    | ✅ Charset, Database | ✅         |
| Oracle     | ✅   | ✅    | ✅ Schema (max 30ch) | ✅         |
| PostgreSQL | ✅   | ✅    | ✅ Schema, Database  | ✅         |
| HSQLDB     | ✅   | ❌    | ✅ Table Names       | ✅         |
| SQL Server | ✅   | ✅    | ✅ Schema, Database  | ✅         |
| SQLite     | ✅   | ✅    | ✅ Minimal Params    | ✅         |

## Changes in v0.2.0

### ⚠️ Breaking Changes
- `DatabaseQueryError` alias removed
- `DatabaseQueries._load_queries()` → Now internal (delegated to QueryRegistry)
- Exception hierarchy unified under `DatabaseError` base class
- Public execution API now split and strict:
  - Removed: `execute_query(..., fetch_one=...)`
  - Removed: `execute_custom_query(..., fetch_one=...)`
  - Use: `execute_query_many/execute_query_one`
  - Use: `execute_custom_many/execute_custom_one`

### ✅ New Features
- `SyncDatabaseManager.execute_query_many(query_name, **params)` - Execute by query name (many)
- `SyncDatabaseManager.execute_query_one(query_name, **params)` - Execute by query name (one)
- `AsyncDatabaseManager` - Full parity with sync version
  - `get_tables()`, `get_views()`, `get_columns()`, `get_routines()`
  - `execute_query_many() / execute_query_one()` support
- `get_storage_inventory()` usa claves explícitas por capacidad:
  - `primary`
  - `temp_tablespaces` cuando aplica
  - `sqlite_file_summary` en SQLite
- HTML `Ver todo` incorpora exportación filtrada:
  - `CSV` / `TSV` en UTF-8
  - `XLSX` real
  - `PDF` vía impresión
- Advanced validators per database motor
- Query Registry + Resolver architecture
- Improved error messages with `raise ... from err` pattern
- Comprehensive logging at DEBUG level

---

## 🆕 What's New in v0.5.0

**Major Refactoring:** Arquitectura 3-level jerárquica + consolidación de módulos

### ✅ What Changed (Internal)
- ✅ **Reorganización arquitectónica** (Level 1, 2, 3)
- ✅ **3 nuevos módulos especializados**: `bulk/`, `analysis/`, `managers/`
- ✅ **~8,500 líneas** refactorizadas y consolidadas
- ✅ Compatibilidad mantenida en wrappers legacy seleccionados

### 🆕 New Modules (v0.5.0+)

#### `managers/` - Consolidated DB Managers
- `managers.sync_mgr.SyncDatabaseManager` (1,000+ lines)
- `managers.async_mgr.AsyncDatabaseManager` (700+ lines)
- **Same API as before**, better code organization

```python
# v0.6.0+ (recommended)
from util_bbdd.managers import SyncDatabaseManager
# Or even simpler:
from util_bbdd import SyncDatabaseManager
```

#### `bulk/` - Bulk Operations Module
- `bulk/crud.py` - Bulk insert/update/delete from DataFrames (999 lines)
- `bulk/audit.py` - Audit trail with transactions (866 lines)
- `bulk/normalize.py` - SQL normalization utilities (264 lines)

```python
# ruta canónica actual
from util_bbdd.bulk import bulk_crud, AuditManager

# ruta canónica ampliada
from util_bbdd.bulk import bulk_crud, AuditManager, normalize_records_for_sql
```

#### `analysis/` - Relationship Graph Analysis
- `analysis/base.py` - Base classes for graph analysis
- `analysis/graphviz.py` - Graphviz visualization
- `analysis/graphviz_ext.py` - Extended Graphviz with columns/types (598 lines)
- `analysis/matplotlib_graph.py` - Matplotlib/NetworkX visualization (278 lines)

```python
# ruta canónica estable
from util_bbdd.analysis import GraphvizRelationshipGraph

# ruta canónica ampliada
from util_bbdd.analysis import (
    DatabaseRelationshipGraphBase,
    GraphvizRelationshipGraph,
    GraphvizRelationshipGraphExt,
    MatplotlibRelationshipGraph
)
```

### 📚 Imports canónicos y compatibilidad legacy

| Componente | Import canónico | Ruta legacy aún soportada |
|-----------|-----------------|---------------------------|
| SyncDatabaseManager | `from util_bbdd import SyncDatabaseManager` | `from util_bbdd.database_manager import DatabaseManager` |
| AsyncDatabaseManager | `from util_bbdd import AsyncDatabaseManager` | `from util_bbdd.async_database_manager import AsyncDatabaseManager` |
| Bulk Operations | `from util_bbdd.bulk import bulk_crud, AuditManager` | `from util_bbdd.bulk_crud import bulk_crud, AuditManager` |
| Analysis Graphs | `from util_bbdd.analysis import GraphvizRelationshipGraphExt` | `from util_bbdd.grafos import GraphvizRelationshipGraphExt` |

**Nota:** para código nuevo, usa siempre la superficie canónica. Las rutas legacy quedan solo como compatibilidad transitoria.

Para el núcleo de grafos de relaciones en v0.6.0:
- usa `util_bbdd.analysis.base` como ubicación canónica
- `util_bbdd.bulk.base` fue eliminado y ya no está disponible

### 📖 Documentation (v0.6.0+)

- [**docs/v0.6.0/MIGRATION_GUIDE_v0.6.0.md**](docs/v0.6.0/MIGRATION_GUIDE_v0.6.0.md) - Contrato vigente de v0.6.0 para grafos, documentación y cambios de estructura
- [**MIGRATION_GUIDE.md**](docs/MIGRATION_GUIDE.md) - Guía viva de migración y compatibilidad para la superficie pública actual
- [**REFACTORING_SESSION_PROGRESS.md**](docs/REFACTORING_SESSION_PROGRESS.md) - Bitácora histórica con actualización operativa de cierre de Fase 3 y arranque de Fase 4 viva
- [**docs/v0.5.6/jinja2_refactor.md**](docs/v0.5.6/jinja2_refactor.md) - Refactorización histórica de la capa Jinja2 standalone

### 🧪 Testing
- Usa las tareas del workspace para validar el estado real actual: `test`, `lint`, `type-check` y `build`.
- `v0.6.0` introduce breaking changes en grafos/documentación y en paths internos retirados; la compatibilidad legacy documentada en `v0.6.3` no revierte esos cambios funcionales.
- La cobertura histórica sigue centrada en paths críticos; toma `pytest` y `htmlcov/` como fuente de verdad del estado vigente.

### 🔄 Deprecation Policy
- v0.5.0: Legacy paths (`bulk_crud/`, `grafos/`) work but discouraged for new code
- v0.6.0: `util_bbdd.bulk.base` eliminado; migra a `util_bbdd.analysis.base`
- v1.0.0: New paths only

---

## Changes in v0.2.0

(See above for v0.5.0 changes)

## Tests

```bash
# Ejecutar tests
pytest tests/ -v --cov=src/util_bbdd

# Con HTML report
pytest tests/ --cov=src/util_bbdd --cov-report=html
# Abrira: htmlcov/index.html
```

## Dependencias

| Paquete     | Uso                           | Versión   |
|-------------|-------------------------------|-----------|
| SQLAlchemy  | ORM y construcción SQL        | >=2.0     |
| pandas      | DataFrames para CRUD          | >=2.3     |
| oracledb    | Driver Oracle                 | >=3.4     |
| openpyxl    | Exportación Excel (auditoría) | >=3.1     |
| python-docx | Generación de Word (docs BD)  | >=1.2     |

## Versionado

Usamos [Semantic Versioning](https://semver.org/):
- `0.x.y` (alpha/beta): APIs experimentales, cambios frecuentes
- `1.0.0` (stable): API estable, cambios siguiendo SemVer

**Current Version: v0.6.7** (Stable - Arquitectura 3 niveles consolidada, Comparador integrado, Agentes de Copilot)

Roadmap completado:
- `v0.1.0` ✅: CRUD base + auditoría
- `v0.2.0` ✅: Documentación BD automática mejorada
- `v0.3.0` ✅: Soporte PostgreSQL mejorado
- `v0.4.0` ✅: Consolidación de conexiones
- `v0.5.0` ✅: Refactorización arquitectónica (3-level hierarchy)
- `v0.6.0` ✅: Grafos multinivel, HTML tabulado, contrato documental nuevo
- `v0.6.1` ✅: Tipología visual, leyenda HTML ampliada, reutilización de análisis entre Word y HTML
- `v0.6.2` ✅: SVG inline offline, resumen/leyenda compartidos, iconos locales
- `v0.6.3` ✅: Capa de agentes Copilot, flujo prompt-agente documentado, instrucciones especializadas
- `v0.6.4` ✅: Consolidación de testeo, stabilización de managers
- `v0.6.5` ✅: Mejoras en documentación de archivos de instrucción, mapeo Claude Code ↔ Copilot
- `v0.6.6` ✅: Estabilización de integración, release notes internas
- `v0.6.7` ✅ (vigente): Comparador de esquemas, imports canónicos desde raíz, esta estructura como standard
- `v1.0.0` (futuro): API estable, cobertura 85%+

## Licencia

MIT - Ver [LICENSE](LICENSE)

## Contribuciones

1. Fork el repo
2. Crea rama: `git checkout -b feat/nueva-funcionalidad`
3. Commit: `git commit -am 'Agregada nueva funcionalidad'`
4. Push: `git push origin feat/nueva-funcionalidad`
5. Pull Request

## Soporte

- 📧 Email: developer@example.com
- 🐛 Issues: https://github.com/fmanza/util_bbdd/issues
- 📚 Docs: https://github.com/fmanza/util_bbdd/tree/main/docs
