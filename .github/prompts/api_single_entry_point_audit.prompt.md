# Prompt: api_single_entry_point_audit

Auditoría de punto de entrada único y responsabilidad única (DRY + SRP).
Detecta duplicidades funcionales, puntos de entrada superpuestos y oportunidades de consolidación.
Modo lectura: no edita código.
**Agente recomendado:** Code Auditor con arquitectura + búsqueda de duplicidades.

---

## Inputs requeridos

- **Alcance**: módulos a revisar (p.ej. `src/util_bbdd/`, o específico como `src/util_bbdd/managers/` + `src/util_bbdd/metadata/`)
- **Foco**:
  - `API_ENTRY_POINTS` — Identifica todos los puntos de entrada públicos (clases/funciones en `__all__`, funciones públicas)
  - `DUPLICATED_FUNCTIONALITY` — Detecta funciones/métodos que hacen lo mismo con distinto nombre/ubicación
  - `SHARED_RESPONSIBILITIES` — Clases que comparten responsabilidades (no aplican SRP)
  - `FACADE_OPPORTUNITIES` — Lugares donde un Facade unificaría múltiples servicios
  - `INTERNAL_HELPERS` — Detecta helpers privados (`_*`) duplicados entre módulos
  - `FULL_AUDIT` — Todos los aspectos anteriores

Si no se especifica, ejecuta `FULL_AUDIT`.

---

## Devuelve en este orden

### PLAN

- **Alcance explícito**: módulos a auditar, versión de referencia (p.ej. `v0.30.0`)
- **Definiciones operativas**:
  - *Punto de entrada público*: símbolo en `__all__` o método de clase pública sin `_` prefix
  - *Duplicidad funcional*: dos símbolos distintos que ejecutan el mismo algoritmo o caso de uso
  - *Responsabilidad compartida*: clase con > 2 razones de cambio independientes
  - *Facade oportunidad*: 3+ servicios llamados juntos sin orquestador explícito
- **Archivos a analizar**: lista de rutas (`src/util_bbdd/__init__.py`, `src/util_bbdd/managers/`, etc.)

### AUDIT_PLAN

- **Riesgos de API**:
  - Usuario confundido por múltiples puntos de entrada
  - Cambios localizados en un módulo requieren cambios en > 1 ubicación
  - Contratos públicos que debieran ser privados
  - Métodos privados (`_*`) que se usan desde otros módulos
- **Riesgos de mantenimiento**:
  - Correcciones que requieren múltiples cambios (falta de DRY)
  - Migración de drivers/motores duplicada en N módulos
  - Lógica de validación = N veces
- **Riesgos de cobertura**: tests de casos de uso duplicados sin centralización

---

### AUDIT_CODE

#### Sección 1: API Pública (`__all__` + entrypoints)

Tabla de puntos de entrada públicos:

| Símbolo | Módulo | Categoría | Contrato | Notas |
|---------|--------|-----------|----------|-------|
| `SyncDatabaseManager` | `managers/sync_mgr` | Punto entrada CRUD (sync) | `BulkCrud` → `database_engine` | Orquesta bulk, dump, comparar |
| `AsyncDatabaseManager` | `managers/async_mgr` | Punto entrada CRUD (async) | `AsyncBulkCrud` → `engine` | Par async de SyncDatabaseManager |
| `SyncMetadataProvider` | `metadata/sync_provider` | Punto entrada metadatos (sync) | Genera SQL, parsea, introspección | Usado internamente por comparar; ¿exportado? |
| `AsyncMetadataProvider` | `metadata/async_provider` | Punto entrada metadatos (async) | Igual, pero async | Par async |
| `SchemaComparator` | `comparar/comparator` | Punto entrada comparación | `SchemaDiff` | Usa MetadataProvider internamente |
| `DumpOrchestrator` | `dump/orchestrator` | Punto entrada volcado | `DumpConfig` → `DumpResult` | Orquesta `BulkCrud` + escritura |
| `MigrationPlanner` | `migrate/planner` | Punto entrada migración | `MigrationPlan` → SQL | Usa metadatos de origen |
| `ConnectionFactory` | `factory/connection` | Factory de conexiones | `Engine` | Creación de `Engine` por `db_type` |
| `PoolFactory` | `factory/pool` | Factory de pools | `QueuePool` / `AsyncAdaptedQueuePool` | Creación de pools |
| `build_conn_params()` | `connection/builder` | Función helper | dict → dict | ¿Debería ser privada? |
| `AsyncBulkCrud` | `bulk/async_crud` | CRUD (async, interno) | Session → operaciones | ¿Exportada? Revisar `__all__` |
| `BulkCrud` | `bulk/sync_crud` | CRUD (sync, interno) | Engine → operaciones | Usado por managers, no exportado directamente |

**Duplicidades detectadas (preliminar)**:
- `SyncDatabaseManager` + `SyncMetadataProvider` — ambos hacen introspección (¿Manager delega a Provider? ¿Cómo?)
- `AsyncDatabaseManager` + `AsyncMetadataProvider` — idem async
- `ConnectionFactory` + `PoolFactory` — ¿pueden consolidarse en una única factory?
- `BulkCrud` + `DumpOrchestrator` — volcado orquesta `BulkCrud`; ¿hay helpers duplicados?

#### Sección 2: Duplicidades Funcionales

Búsqueda de patrones duplicados (misma lógica, distinto nombre/ubicación):

**2.1 Validación de configuración**
- `DumpConfig.__post_init__()` valida `chunk_size`, `commit_every_n_chunks`
- ¿`BulkCrud.__init__()` valida lo mismo? `chunk_size` desde `DumpConfig`?
- **Riesgo**: si cambia validación, hay que tocar 2 lugares
- **Acción**: unificar en un validador compartido (`_core/validation/config_validators.py`)

**2.2 Reflexión de metadatos por motor**
- `metadata/postgresql/provider.py` → `fetch_*_sql()`
- `metadata/mysql/provider.py` → `fetch_*_sql()`
- `metadata/oracle/provider.py` → `fetch_*_sql()`
- `metadata/sqlserver/provider.py` → `fetch_*_sql()`
- **Patrón**: cada motor implementa la misma interfaz
- **Duplicidad**: Algunos `fetch_*_sql()` comparten lógica (ej. FK comunes)
- **Acción**: extraer helpers comunes a `metadata/_support/`

**2.3 Soporte de transacciones y savepoints**
- `BulkCrud` → `bulk_session()` con savepoint + commit periódico
- `DumpOrchestrator` → ¿reinventa transacciones? Revisar `_bulk_options()`
- **Riesgo**: cambios en estrategia de commit requieren múltiples cambios
- **Acción**: encapsular en `_core/transaction/` (SessionScope, CommitCadence, etc.)

**2.4 Generación de SQL**
- `bulk/sql_gen.py` → `generar_sql()` — genera INSERT/UPDATE/DELETE
- `dump/sql_gen.py` — ¿existe? ¿reutiliza de bulk?
- `migrate/` → ¿genera DDL? ¿hay generators separados por tipo?
- **Riesgo**: cambios en SQL base requieren tocar N generadores
- **Acción**: revisar si `generar_sql` se reutiliza; centralizar dialectos

**2.5 Logging y auditoría**
- `BulkCrud` → `self.logger` (logging estándar)
- `audit_sink` en `BulkCrud` → auditoría centralizada (`v0.29.0`)
- `DumpOrchestrator` → `audit_sink` compartido
- `MigrationPlan.execute()` → `audit_sink` compartido
- ✅ **Ya centralizado en `util_bbdd.audit` desde v0.29.0** — pero revisar si hay logging duplicado antes de audit_sink

**2.6 Manejo de errores por motor**
- Cada motor tiene sus códigos de error (`1205` MySQL, `40001` SQL Server, etc.)
- ¿`connection/errors.py` centraliza? ¿cada servicio reinventa?
- **Búsqueda**: `except (ORA-`, `except OperationalError`, `except psycopg` en codebase
- **Acción**: unificar en `_core/errors/motor_errors.py`

**2.7 Manejo de constraints (deshabilitar/rehabilitar)**
- `BulkCrud` → `disable_constraints()` por motor
- `DumpOrchestrator` → ¿reutiliza de BulkCrud?
- **Riesgo**: lógica del constraint live en múltiples places
- **Acción**: extraer a `_core/ddl/constraint_manager.py`

#### Sección 3: Análisis de Responsabilidad (SRP)

Para cada clase/módulo, preguntar:
- *¿Cuántas razones tiene para cambiar?*
- *¿Acoplada a otros módulos (imports)?*
- *¿Se testetea independientemente?*

**3.1 SyncDatabaseManager**
- Razones de cambio:
  1. Interfaz CRUD (operaciones bulk)
  2. Interfaz de metadatos (introspección)
  3. Orquestación de comparación
  4. Orquestación de volcado
- **Veredicto**: ❌ Viola SRP (4 responsabilidades)
- **Remedio**: Refactor a Facade (Manager es OK) pero componentes son inyectados

**3.2 SchemaComparator**
- Razones de cambio:
  1. Algoritmo de comparación
  2. Renderizado de diff (SqlDiffReporter)
  3. Obtención de metadatos (MetadataProvider)
- **Veredicto**: 🟡 Bordea SRP (puede mejorar separación de concerns)
- **Remedio**: Inyectar `reporter` y `metadata_provider`

**3.3 DumpOrchestrator**
- Razones de cambio:
  1. Orquestación de lectura (lotes, particiones)
  2. Orquestación de escritura (CSV, Excel, Word, ZIP)
  3. Auditoría y reporte
  4. Manejo de errores (`on_error="isolate"`)
- **Veredicto**: ❌ Viola SRP (4 responsabilidades)
- **Remedio**: Separar lectura (DumpReader) y escritura (DumpWriter) + reportador

**3.4 BulkCrud**
- Razones de cambio:
  1. Inserción (INSERT, estrategias por motor)
  2. Actualización (UPDATE, estrategias)
  3. Eliminación (DELETE, estrategias)
  4. Manejo de transacciones y commits periódicos
  5. Auditoría y rechazo de filas
- **Veredicto**: ❌ Viola SRP (5 responsabilidades)
- **Remedio**: OK para primera versión, pero considerar separación en Bulk{Insert,Update,Delete}

**3.5 ConnectionFactory + PoolFactory**
- Ambos crean objetos de conexión/pool
- ¿Pueden ser una única `DatabaseConnectionFactory`?
- **Veredicto**: 🟡 Separación útil para testeo, pero alias podrían unificar API

#### Sección 4: Análisis de Facade y Orquestación

**4.1 Managers vs Providers**
- `SyncDatabaseManager` es un Facade que orquesta:
  - `BulkCrud` (CRUD)
  - `SyncMetadataProvider` (metadatos)
  - `SchemaComparator` (comparación) — ¿método en Manager? Revisar
  - `DumpOrchestrator` (volcado)
- **Pregunta**: ¿`SyncMetadataProvider` es punto de entrada público o interno?
- **Búsqueda**: `from util_bbdd import SyncMetadataProvider` en ejemplos/tests
- **Acción**: Si es interno, no exportar; si es público, documentar casos de uso

**4.2 Punto de entrada canónico**
- **Propuesta A**: Un único `DatabaseManager` (alias de `SyncDatabaseManager`)
  - Punto de entrada = `from util_bbdd import DatabaseManager`
  - Todo orquestado aquí (CRUD, metadatos, comparación, volcado)
  - ¿Cómo se accede a `SchemaComparator` por separado? Método: `manager.compare_schemas()`
- **Propuesta B**: Mantener múltiples, pero con guía clara en docs
  - `SyncDatabaseManager` → CRUD + volcado
  - `SchemaComparator` → comparación independiente
  - `MigrationPlanner` → migración independiente
  - `SyncMetadataProvider` → soporte interno (no exportar)
- **Riesgo**: Propuesta B causa confusión de usuario

#### Sección 5: Internal Helpers y Privados

Búsqueda de patrones `_*` usados cross-module:

| Privado | Módulo | Usuario | ¿Debería ser público? | Notas |
|---------|--------|---------|----------------------|-------|
| `_get_metadata_adapter()` | metadata | bulk, dump, comparar | ❌ No; es factory | OK privado |
| `_resolve_max_workers()` | bulk/_support | ParallelBulkLoader | ✅ Sí; lógica compartida | Considerar `_support/worker_config.py` |
| `_hoist_constraints_for_workers()` | bulk/_support | ParallelBulkLoader | ✅ Sí; lógica compartida | Idem |
| Otros en `_core/` | _core | Todo | ✅ Sí; son foundational | OK como está |

---

### Sección 6: Grafo de Dependencias y Acoplamiento

Matriz simplificada (importa de...):

```
SyncDatabaseManager   →  BulkCrud, SyncMetadataProvider, DumpOrchestrator, SchemaComparator
AsyncDatabaseManager  →  AsyncBulkCrud, AsyncMetadataProvider, DumpOrchestrator, SchemaComparator
SchemaComparator      →  SyncMetadataProvider, SqlDiffReporter
DumpOrchestrator      →  BulkCrud, SyncMetadataProvider, DumpWriter
BulkCrud              →  ConnectionFactory, SQL generators, Audit
ConnectionFactory     →  _core/dialects
PoolFactory           →  ConnectionFactory (?)
```

**Ciclos detectados**: ¿Hay ciclos de importación? Buscar `from X import Y; from Y import X`

**Acoplamiento alto**: Si `SyncDatabaseManager` importa 5+ módulos, considerar Dependency Injection

---

### Sección 7: Propuesta de Consolidación

#### 7.1 Opción A: Minimal (bajo impacto)

- Extraer validadores comunes → `_core/validation/`
- Extraer manejo de constraints → `_core/ddl/constraint_manager.py`
- Extraer helpers de motor → `_core/dialects/error_handlers.py`
- **Cambios API**: Ninguno (todo privado)
- **Esfuerzo**: 2-4h
- **Riesgo**: Bajo

#### 7.2 Opción B: Moderate (cambios de API)

- Unificar `ConnectionFactory` + `PoolFactory` → `DatabaseFactory`
- Alias `DatabaseManager` → `SyncDatabaseManager` (deprecar nombre largo)
- Hacer privado `SyncMetadataProvider` (¿usado externamente?)
- Hacer privado `BulkCrud` (¿usado externamente?)
- **Cambios API**: Alias + posible deprecation
- **Esfuerzo**: 4-8h
- **Riesgo**: Moderado (requiere migration guide)

#### 7.3 Opción C: Radical (refactor de arquitectura)

- Separar `BulkCrud` → `BulkInsert`, `BulkUpdate`, `BulkDelete`
- Separar `DumpOrchestrator` → `DumpReader`, `DumpWriter`, `DumpReporter`
- Unificar factories en `DatabaseFactory`
- Nuevo módulo `orchestration/` con flujos de alto nivel
- **Cambios API**: Mayores
- **Esfuerzo**: 20-40h
- **Riesgo**: Alto (muchos tests a actualizar)

**Recomendación**: Evaluar Opción A inmediatamente; Opción B con PR específico; Opción C para `v1.0.0`

---

### Sección 8: Hallazgos Críticos y NO-GOs

| Hallazgo | Severidad | Acción |
|----------|-----------|--------|
| `_resolve_max_workers()` usado desde ParallelBulkLoader | Media | Mover a módulo compartido con alias atrás |
| Validadores de `chunk_size`/`commit_every_n_chunks` en 2 lugares | Media | Unificar en `_core/validation/` |
| Error handling de motor sin centralización | Media | Crear `_core/errors/motor_errors.py` |
| Posible ciclo de importación (verificar) | Alta | Romper con inyección de dependencias |
| `SyncMetadataProvider` ¿público o privado? | Media | Decidir y actualizar `__all__` |

---

### Veredicto Final

- **HALLAZGOS CRÍTICOS**: (# encontrados)
- **HALLAZGOS MAYORES**: (# encontrados)
- **HALLAZGOS MENORES**: (# encontrados)
- **SRP VIOLATIONS**: (# encontrados y ubicación)
- **DUPLICIDADES CONFIRMADAS**: (# encontrados y módulos afectados)
- **PUNTO DE ENTRADA RECOMENDADO**:
  - Opción preferida (A/B/C)
  - Razón: claridad, mantenimiento, API stability
- **VEREDICTO FINAL**:
  - `APROBADO` — No hay bloqueos, proceder con Opción A
  - `APROBADO CON CONDICIONES` — Proceder con Opción A; Opción B tras PR separado
  - `RECHAZADO` — Ciclos de importación u otro bloqueador; resolver antes

---

### VERSION

Opcional: si se autorizan cambios:
- Commits sugeridos (`fix: consolidate validators`, `refactor: extract constraint manager`, etc.)
- Migración de usuarios (si es ruptura de API)
- Tests a añadir (coverage de helpers centralizados)
- Documentación a actualizar (`docs/architecture.md`, ejemplos, etc.)

---

## Reglas de ejecución

1. **Lectura exhaustiva de `__init__.py` y `__all__`**: identificar qué es público
2. **Búsqueda con `grep` o `semantic_search`**:
   - Patrones de duplicidad (`def generar_sql`, `def build_conn`, etc.)
   - Imports cruzados (`from X import Y` apariciones)
   - Privados usados externamente (`from module import _private`)
3. **Análisis de responsabilidad**: pasar cada clase/módulo por el checklist SOLID
4. **Grafo de dependencias**: identificar acoplamiento y ciclos
5. **Secciones 1-7**: rellenar tabla/matriz con evidencias concretas (archivo:línea)
6. **Propuestas accionables**: NO teoría; ej. "extraer a `_core/validation/config.py` líneas 45-67"
7. **Veredicto sin ambigüedad**: NO "probablemente" ni "tal vez"; datos concretos

---

## Referencia: Arquitectura esperada

```
foundation (_core/)
    ├─ contracts & protocols (ABC, Protocol)
    ├─ types & constants
    ├─ exceptions
    ├─ validation/ (centralizado v0.30.0+)
    ├─ dialects/ (motor-specific helpers)
    ├─ logging/ & audit/ (centralizado v0.29.0+)
    ├─ ddl/ (constraints, migrate DDL)
    └─ export_safety/ (sanitización)

services (core-layer)
    ├─ connection/ (pools, builders, advisors)
    ├─ factory/ (factories)
    ├─ metadata/ (introspección, providers por motor)
    ├─ bulk/ (CRUD operaciones, estrategias por motor)
    ├─ dump/ (volcado, lectura/escritura, reportes)
    ├─ comparar/ (comparación, diff)
    ├─ migrate/ (migración DDL)
    └─ managers/ (Facade, orquestación)

public_api (__init__.py)
    └─ Puntos de entrada únicos:
        ├─ SyncDatabaseManager (alias: DatabaseManager)
        ├─ AsyncDatabaseManager
        ├─ SchemaComparator
        ├─ MigrationPlanner
        ├─ DumpOrchestrator
        ├─ Factories
        └─ Excepciones, tipos, helpers públicos
```

---

*Versión de prompt: 1.0 | Aplica desde: util_bbdd v0.30.0*
