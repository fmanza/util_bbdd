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

## Arquitectura v0.6.2 - Estructura de 3 Niveles

Util_bbdd usa una **arquitectura jerárquica de 3 niveles** para máxima modularidad:

### Level 1: Abstracciones Internas
```
_core/               # Tipos básicos, excepciones, contratos
  ├── types.py       # Type aliases (RowOrNone, Rows, etc.)
  ├── exceptions.py  # Jerarquía de excepciones
  ├── contracts.py   # Protocols/interfaces
  └── constants.py   # Enums

_drivers/            # Gestión de drivers
  ├── validator.py   # Validación centralizada
  ├── capabilities.py# Capacidades por motor
  └── registry.py    # Registro de drivers
```

### Level 2: Capas de Acceso
```
connection/          # Pool, factory, configuración (1,305 líneas)
  ├── factory.py     # Connection factory
  ├── pool.py        # Pool management
  ├── config.py      # Connection configs
  ├── params.py      # Parameters management
  ├── protocols.py   # Interfaces
  ├── close.py       # Close utilities
  └── motors/        # Motor-specific implementations

query/               # Registry, resolver, executors (314 líneas base)
  ├── registry.py    # Query registry
  ├── resolver.py    # Query resolver
  └── executors/     # Executor implementations

metadata/            # Metadata processing pipeline (887 líneas)
  ├── cache.py       # Caching layer
  ├── contracts.py   # Interfaces
  ├── normalizer.py  # SQL normalization
  ├── builder.py     # Metadata builder
  ├── fetcher.py     # Data fetcher
  └── manager.py     # Orchestration

results/             # Result management (74 líneas)
  ├── types.py       # Result type definitions
  └── normalizer.py  # Result normalization
```

### Level 3: Especialización
```
bulk/                # Operaciones masivas (2,129 líneas)
  ├── crud.py        # Bulk insert/update/delete (999 líneas)
  ├── audit.py       # Audit trail (866 líneas)
  └── normalize.py   # SQL normalization (264 líneas)

analysis/            # Análisis de relaciones multinivel
  ├── base.py        # GraphDocument, traversal y niveles
  ├── graphviz.py    # Graphviz visualization
  ├── graphviz_ext.py# Graphviz multinivel con columnas y cardinalidad
  └── matplotlib_graph.py # Matplotlib visualization multinivel

managers/            # APIs de alto nivel (2,200+ líneas)
  ├── sync_mgr.py    # SyncDatabaseManager (1,000+ líneas)
  └── async_mgr.py   # AsyncDatabaseManager (700+ líneas)

doc/                 # Generadores documentales
  ├── template_engine.py
  ├── html_generator.py
  ├── excel_generator.py
  ├── word_generator.py
  └── templates/
      ├── layouts/
      ├── macros/
      └── pages/
```

**Beneficios:**
- ✅ Cada módulo < 500 líneas
- ✅ Responsabilidad única por archivo
- ✅ Fácil agregar nuevos motores (solo agregar archivo en `connection/motors/`)
- ✅ Compatibilidad mantenida en wrappers legacy seleccionados; el manager sync usa `SyncDatabaseManager`

## Novedades v0.6.2 en grafos y documentación

- Relaciones de n niveles mediante `max_depth`
- Dirección configurable del recorrido: `incoming`, `outgoing` o `both`
- Modos de visualización de columnas: `compact`, `relations`, `all`
- Cardinalidad representada por extremos en Graphviz
- HTML con pestañas por nivel y por sentido
- Word con resumen de niveles totales y no visibles
- Payloads compartidos para leyenda y resumen entre HTML y Word
- Exportación HTML offline con iconos SVG locales para paginación y acciones
- Diagrama HTML inline con zoom, paneo y controles de navegación offline

### Resumen de la release v0.6.2

La versión v0.6.2 cierra la evolución multinivel introducida en v0.6.0 y consolidada en v0.6.1, con foco en portabilidad offline, reutilización documental y cierre operativo de la experiencia HTML.

- Tipología visual de tablas en diagramas Graphviz y HTML:
  - `entity`: azul pastel
  - `association`: verde pastel
  - `hierarchy`: naranja pastel
- La tipología visual es heurística y se calcula desde `analysis/base.py`, de forma reutilizable por distintos renderers.
- La detección inicial de `association` usa varias FKs y, cuando aplica, PK compuesta basada en columnas relacionales.
- HTML y Word comparten una leyenda visual explícita con:
  - dirección (`Salida` / `Entrada`)
  - tipo de tabla
  - cardinalidad
  - tipo de relación soportado hoy (`FK`)
- El resumen de niveles, ayudas de navegación y textos de dirección se generan desde payloads comunes reutilizables.
- La política actual de vistas en diagramas enriquecidos sigue siendo `exclude`.
- Word y HTML pueden reutilizar una misma instancia de `GraphvizRelationshipGraphExt` durante la misma corrida multi-formato para evitar recomputación innecesaria.
- La salida HTML offline copia iconos SVG locales y mantiene operativos los botones de exportación y paginación sin dependencias externas.
- Los diagramas de detalle se embeben como SVG inline para garantizar paneo y zoom desde la propia página en navegadores offline.

### Semántica de tipología visual

La clasificación visual de tablas no pretende sustituir el modelo de datos ni imponer una taxonomía absoluta.

- `entity`: tabla de negocio general que no encaja en las heurísticas de asociación o jerarquía
- `association`: tabla puente detectada por varias claves foráneas y, en los casos soportados, PK compuesta basada en columnas FK
- `hierarchy`: tabla con autorreferencia que sugiere una relación padre-hijo dentro de la misma entidad

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
# v0.4.0 (still works)
from util_bbdd.bulk import bulk_crud, AuditManager

# v0.5.0 (recommended)
from util_bbdd.bulk import bulk_crud, AuditManager, normalize_records_for_sql
```

#### `analysis/` - Relationship Graph Analysis
- `analysis/base.py` - Base classes for graph analysis
- `analysis/graphviz.py` - Graphviz visualization
- `analysis/graphviz_ext.py` - Extended Graphviz with columns/types (598 lines)
- `analysis/matplotlib_graph.py` - Matplotlib/NetworkX visualization (278 lines)

```python
# v0.4.0 (still works)
from util_bbdd.analysis import GraphvizRelationshipGraph

# v0.5.0 (recommended - more options available)
from util_bbdd.analysis import (
    DatabaseRelationshipGraphBase,
    GraphvizRelationshipGraph,
    GraphvizRelationshipGraphExt,
    MatplotlibRelationshipGraph
)
```

### 📚 New Import Paths (v0.5.0)

| Component | v0.4.0 Import | v0.5.0 Import (Recommended) |
|-----------|---------------|------------------------------|
| SyncDatabaseManager | `util_bbdd.managers.sync_mgr` | `util_bbdd.managers` / `util_bbdd` |
| AsyncDatabaseManager | `util_bbdd.async_database_manager` | `util_bbdd.managers` |
| Bulk Operations | `util_bbdd.bulk_crud` | `util_bbdd.bulk` |
| Analysis Graphs | `util_bbdd.grafos` | `util_bbdd.analysis` |

**Note:** los paths legacy de `bulk` y `analysis` siguen disponibles, pero para el manager sync debes usar `SyncDatabaseManager`.

Para el núcleo de grafos de relaciones en v0.6.0:
- usa `util_bbdd.analysis.base` como ubicación canónica
- `util_bbdd.bulk.base` fue eliminado y ya no está disponible

### 📖 Documentation (v0.6.0+)

- [**docs/v0.6.0/MIGRATION_GUIDE_v0.6.0.md**](docs/v0.6.0/MIGRATION_GUIDE_v0.6.0.md) - Contrato vigente de v0.6.0 para grafos, documentación y cambios de estructura
- [**MIGRATION_GUIDE.md**](docs/MIGRATION_GUIDE.md) - Detailed migration guide from v0.4.0 → v0.6.0 (with examples)
- [**REFACTORING_SESSION_PROGRESS.md**](docs/REFACTORING_SESSION_PROGRESS.md) - Session progress metrics (13/19 PRs complete)
- [**docs/v0.5.6/jinja2_refactor.md**](docs/v0.5.6/jinja2_refactor.md) - Refactorización histórica de la capa Jinja2 standalone

### 🧪 Testing (v0.5.0)
- ✅ **525/525 tests passing** en la validación más reciente
- ⚠️ **v0.6.0 introduce breaking changes** en el subsistema de grafos/documentación y en paths internos retirados
- ✅ Test coverage ~39% (focused on critical paths)

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

**Current Version: v0.6.3** (Stable - capa de agentes de Copilot y flujo prompt-agente documentado)

Roadmap:
- `v0.1.0`: CRUD base + auditoría
- `v0.2.0`: Documentación BD automática mejorada
- `v0.3.0`: Soporte PostgreSQL mejorado
- `v0.4.0`: Consolidación de conexiones
- `v0.5.0` ✅: Refactorización arquitectónica (3-level hierarchy)
- `v0.6.0` ✅: Grafos multinivel, HTML tabulado y contrato documental nuevo
- `v0.6.1` ✅: Tipología visual, leyenda HTML ampliada y reutilización de análisis entre Word y HTML
- `v0.6.2` ✅: SVG inline offline, resumen/leyenda compartidos, iconos locales y ajuste de tooltips/exportación
- `v0.6.3` ✅ (actual): capa de agentes de Copilot, flujo recomendado y mapeo prompt-agente documentado
- `v1.0.0`: API estable, cobertura 85%+

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
