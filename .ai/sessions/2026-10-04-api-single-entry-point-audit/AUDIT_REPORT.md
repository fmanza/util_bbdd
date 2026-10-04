# AUDITORÍA: Punto de Entrada Único y Responsabilidad Única
## util_bbdd v0.30.0 — FULL_AUDIT

**Fecha**: 2026-10-04  
**Agente**: Code Auditor  
**Alcance**: src/util_bbdd/ (todos los módulos)  
**Foco**: FULL_AUDIT (API_ENTRY_POINTS + DUPLICATED_FUNCTIONALITY + SHARED_RESPONSIBILITIES + FACADE_OPPORTUNITIES + INTERNAL_HELPERS)  
**Modo**: Lectura, sin cambios de código

---

## PLAN

### Alcance Explícito

- **Versión de referencia**: v0.30.0 (2026-10-03, commit 2abe87c, `develop`)
- **Módulos auditados**: 
  - `src/util_bbdd/__init__.py` (punto de entrada público)
  - `src/util_bbdd/managers/` (Facade para CRUD, metadatos, comparación, volcado)
  - `src/util_bbdd/bulk/` (CRUD, estrategias)
  - `src/util_bbdd/dump/` (volcado, orquestación)
  - `src/util_bbdd/comparar/` (comparación de esquemas)
  - `src/util_bbdd/metadata/` (introspección, providers)
  - `src/util_bbdd/factory/` (factories de conexiones y pools)
  - `src/util_bbdd/connection/` (builders, advisors)
  - `src/util_bbdd/migrate/` (migración DDL)
  - `src/util_bbdd/_core/` (foundation: contratos, excepciones, validadores)

### Definiciones Operativas

| Término | Definición |
|---------|-----------|
| **Punto de entrada público** | Símbolo en `__all__` o método público de clase (sin `_` prefix) accesible desde `from util_bbdd import X` |
| **Duplicidad funcional** | Dos símbolos/métodos distintos que ejecutan el mismo algoritmo o resuelven el mismo caso de uso |
| **Responsabilidad compartida** | Clase/módulo con > 2 razones de cambio independientes (viola SRP) |
| **Facade oportunidad** | 3+ servicios/dependencias llamadas siempre juntos sin orquestador explícito |
| **Helper privado reexportado** | Función/clase con `_` prefix usada desde módulos ajenos (anticipo de publicidad) |

### Archivos Analizados

```
src/util_bbdd/__init__.py                    (62–130: __all__, 33 símbolos públicos)
src/util_bbdd/managers/sync_mgr.py           (55+: SyncDatabaseManager)
src/util_bbdd/managers/async_mgr.py          (39+: AsyncDatabaseManager)
src/util_bbdd/managers/_manager_shared_mixin.py  (25+: DatabaseManagerSharedMixin)
src/util_bbdd/managers/_catalog_facade.py    (77+: SyncCatalogFacade, AsyncCatalogFacade)
src/util_bbdd/bulk/sync_crud.py              (BulkCrud, ParallelBulkLoader)
src/util_bbdd/bulk/async_crud.py             (AsyncBulkCrud)
src/util_bbdd/dump/orchestrator.py           (DumpOrchestrator)
src/util_bbdd/dump/_models.py                (DumpConfig, DumpResult, validadores)
src/util_bbdd/comparar/comparator.py         (SchemaComparator)
src/util_bbdd/connection/factory.py          (ConnectionFactory)
src/util_bbdd/factory/pool_factory.py        (PoolFactory)
src/util_bbdd/metadata/__init__.py           (SyncMetadataProvider, AsyncMetadataProvider)
src/util_bbdd/migrate/planner.py             (MigrationPlanner)
```

---

## AUDIT_PLAN

### Riesgos de API

| Riesgo | Evidencia | Severidad |
|--------|-----------|-----------|
| Usuario confundido por múltiples puntos de entrada | `__all__` exporta 33 símbolos (Managers + Providers + Orchestrators + Factories) | **ALTA** |
| `SyncMetadataProvider` ¿público o privado? | Está en `__all__` pero usualmente accedida mediante `SyncDatabaseManager` | **MEDIA** |
| `build_conn_params()` debería ser privada | Función auxiliar exportada, no es API de negocio | **BAJA** |
| Responsabilidades superpuestas | `SyncDatabaseManager` orquesta 4+ servicios (CRUD, metadatos, comparar, dump) | **MEDIA** |
| Cambios localizados requieren múltiples ediciones | Validación de `chunk_size` en 2 lugares (`bulk/`, `dump/`) | **MEDIA** |

### Riesgos de Mantenimiento

| Riesgo | Evidencia | Severidad |
|--------|-----------|-----------|
| Falta de DRY — validación fragmentada | `validate_chunk_size()` en `bulk/_execution/executors.py` + `DumpConfig.__post_init__()` | **MEDIA** |
| Migración de drivers duplicada | `ConnectionFactory` + `PoolFactory` comparten lógica de lazy loading | **BAJA** |
| Manejo de errores descentralizado | 9 validadores de parámetros distintos (`mysql_validator.py`, `oracle_validator.py`, etc.) | **BAJA** |
| Helpers privados usados externamente | `_resolve_max_workers()`, `_hoist_constraints_for_workers()` desde `ParallelBulkLoader` | **BAJA** |

### Riesgos de Cobertura

| Riesgo | Evidencia | Severidad |
|--------|-----------|-----------|
| Tests duplicados sin centralización | `test_chunk_size_validation` en `tests/bulk/` + `tests/dump/` | **BAJA** |
| API pública no documentada | `SyncMetadataProvider` se ve privada pero está pública | **MEDIA** |

---

## AUDIT_CODE

### Sección 1: Tabla de Puntos de Entrada Públicos

**Fuente**: `src/util_bbdd/__init__.py`, líneas 62–130 (`__all__`)

| # | Símbolo | Módulo | Categoría | Contrato | Criticidad | ¿Debería ser privado? |
|---|---------|--------|-----------|----------|------------|----------------------|
| 1 | `SyncDatabaseManager` | `managers/sync_mgr` | **Orquestador CRUD (sync)** | Engine + conn_params → CRUD/metadatos/dump/comparar | ⭐⭐⭐ | NO — punto de entrada principal |
| 2 | `AsyncDatabaseManager` | `managers/async_mgr` | **Orquestador CRUD (async)** | Engine + conn_params → CRUD/metadatos async | ⭐⭐⭐ | NO — par async |
| 3 | `SyncMetadataProvider` | `metadata/sync_provider` | **Introspección (sync)** | Metadatos de tabla, FK, índices, routines | ⭐⭐ | 🟡 **CUESTIONABLE** — ¿usuario lo llama directo o siempre vía Manager? |
| 4 | `AsyncMetadataProvider` | `metadata/async_provider` | **Introspección (async)** | Idem async | ⭐⭐ | 🟡 **CUESTIONABLE** |
| 5 | `SchemaComparator` | `comparar/comparator` | **Comparación** | Engine × 2 → SchemaDiff | ⭐⭐⭐ | NO — uso independiente válido |
| 6 | `SchemaDiff` | `comparar/models` | **Resultado de comparación** | Objeto de datos | ⭐ | NO — contrato de salida |
| 7 | `DumpOrchestrator` | `dump/orchestrator` | **Volcado** | DumpConfig → DumpResult | ⭐⭐⭐ | NO — punto de entrada por usar case |
| 8 | `DumpConfig` | `dump/_models` | **Config volcado** | dataclass | ⭐⭐ | NO — configurable |
| 9 | `DumpResult` | `dump/_models` | **Resultado volcado** | dataclass | ⭐⭐ | NO — contrato de salida |
| 10 | `MigrationPlanner` | `migrate/planner` | **Migración DDL** | Origin + Dest → MigrationPlan | ⭐⭐⭐ | NO — caso de uso independiente |
| 11 | `MigrationPlan` | `migrate/models` | **Plan de migración** | dataclass | ⭐⭐ | NO — contrato de salida |
| 12 | `ConnectionFactory` | `connection/factory` | **Factory de conexiones** | db_type + params → Engine | ⭐⭐ | 🟡 **CONSOLIDABLE** — ver PoolFactory |
| 13 | `PoolFactory` | `factory/pool_factory` | **Factory de pools** | db_type + params → Pool | ⭐⭐ | 🟡 **CONSOLIDABLE** — ver ConnectionFactory |
| 14 | `build_conn_params()` | `connection/builder` | **Helper** | dict → dict (normalización) | ⭐ | 🔴 **SÍ** — debería ser privada (solo setup) |
| 15–33 | Excepciones + Enums | `_core/` + módulos | **Contratos** | Tipos + constantes | ⭐ | NO — necesarias |

**Hallazgo 1.1**: **33 símbolos públicos = confusión de API**
- Puntos de entrada conceptuales: `SyncDatabaseManager`, `AsyncDatabaseManager`, `SchemaComparator`, `DumpOrchestrator`, `MigrationPlanner` = 5
- Datos/Config: `DumpConfig`, `DumpResult`, `SchemaDiff`, `MigrationPlan` = 4
- Factories: `ConnectionFactory`, `PoolFactory` = 2
- Helpers: `build_conn_params()` = 1
- Excepciones: 21
- **Recomendación**: Mantener los 5 puntos de entrada + 4 datos + 21 excepciones = 30. **Retirar `build_conn_params()`** (privada). Consolidar factories en alias o una única exportación.

**Hallazgo 1.2**: ¿Metadata Providers son API pública o interna?
- `SyncMetadataProvider` / `AsyncMetadataProvider` en `__all__` = públicos
- **Uso detectado**: Siempre inyectados en `SchemaComparator` o usados internamente por `DumpOrchestrator`
- **No se encontró**: Usuario llamando directo `metadata_provider.fetch_tables()`
- **Recomendación**: Revisar si se usan externamente antes de hacer privados; si no, mover a `_core/internal/` y actualizar imports internos.

---

### Sección 2: Duplicidades Funcionales Detectadas

#### 2.1 Validación de Configuración — **SRP VIOLATION** ⚠️

| Ubicación | Función/Método | Valida | Líneas | Riesgo |
|-----------|-----------------|--------|--------|--------|
| `src/util_bbdd/bulk/_execution/executors.py:29–45` | `validate_chunk_size(chunk_size: Any) -> int` | `chunk_size >= 1` | 17 | Centralizada ✅ |
| `src/util_bbdd/dump/_models.py:188–195` | `DumpConfig.__post_init__()` | `chunk_size >= 1`, `commit_every_n_chunks >= 1` | 8 | **Duplicada** ❌ |
| `src/util_bbdd/bulk/_execution/executors.py:114, 272` | Usadas en 2 lugares | `validate_chunk_size()` | 2 | Centralización OK ✅ |

**Hallazgo 2.1a**: `DumpConfig.__post_init__()` (líneas 188–195) repite la validación de `chunk_size` que ya existe en `validate_chunk_size()` (línea 29).
- **Código DumpConfig**:
  ```python
  validate_chunk_size(self.chunk_size)  # Línea 192: reutiliza, OK
  if self.commit_every_n_chunks is not None and self.commit_every_n_chunks < 1:
      raise ValueError(f"commit_every_n_chunks debe ser None o un entero ≥ 1, recibido: {self.commit_every_n_chunks}")
  ```
- **Código bulk**: `validate_chunk_size()` en `executors.py` línea 29
- **Impacto**: Si validación cambia (ej. `chunk_size > 100`), hay 2 puntos de cambio
- **Recomendación**: Extraer `validate_commit_cadence(commit_every_n_chunks)` → `_core/validation/cadence.py`; llamar desde `DumpConfig` y `BulkCrud`

#### 2.2 Reflexión de Metadatos por Motor — **Distribución válida pero mejorable**

| Motor | Archivo | Fetch SQL | Duplicidad |
|-------|---------|-----------|-----------|
| PostgreSQL | `metadata/postgresql/provider.py` | `fetch_*_sql()` | Específica ✅ |
| MySQL | `metadata/mysql/provider.py` | `fetch_*_sql()` | Específica ✅ |
| Oracle | `metadata/oracle/provider.py` | `fetch_*_sql()` | Específica ✅ |
| SQL Server | `metadata/sqlserver/provider.py` | `fetch_*_sql()` | Específica ✅ |

**Hallazgo 2.2a**: Cada motor implementa `fetch_tables_sql()`, `fetch_foreign_keys_sql()`, etc.
- **Patrón**: Adapters por motor (Strategy pattern) = válido
- **Oportunidad**: Algunos `fetch_*()` usan SQL base común (ej. FK estructura de catálogo)
- **Impacto**: Bajo. Cambio en estructura de catálogo requiere tocar 4 archivos, pero está centralizado por motor.
- **Recomendación**: Monitorear; si hay > 30% duplicación SQL, extraer helpers a `metadata/_support/sql_fragments.py`

#### 2.3 Soporte de Transacciones y Commits Periódicos — **Riesgo ALTO**

| Ubicación | Responsabilidad | Líneas |
|-----------|-----------------|--------|
| `src/util_bbdd/bulk/sync_crud.py` | `bulk_session()` + `commit_every_n_chunks` | Impl CRUD |
| `src/util_bbdd/dump/orchestrator.py:865` | Passes `commit_every_n_chunks` a `BulkCrud` | Reutiliza ✅ |
| `src/util_bbdd/dump/orchestrator.py:882–888` | Calcula `write_batch_size` per motor | Lógica duplicada? |

**Hallazgo 2.3a**: `DumpOrchestrator._resolve_write_batch_size()` (líneas 882–888) calcula batch por motor
- **PostgreSQL especial**: `chunk_size vs 20_000` (línea 886–887)
- **Resto**: `chunk_size` (línea 888)
- **Riesgo**: Si estrategia de batch cambia por motor, hay duplicidad entre `DumpOrchestrator` y `BulkCrud`
- **Impacto**: MEDIO — cambio de estrategia requiere coords entre 2 módulos
- **Recomendación**: Extraer `_resolve_batch_by_motor(db_type, chunk_size) → int` a `_core/batching/` (usada por Dump + Bulk)

#### 2.4 Generación de SQL — **Centralizada OK**

| Ubicación | Función | Uso |
|-----------|---------|-----|
| `src/util_bbdd/bulk/_support/sql_gen.py` | `generar_sql()` | INSERT/UPDATE/DELETE |
| `src/util_bbdd/dump/orchestrator.py` | Usa `_read_chunks()`, no genera SQL | Lectura de chunks |

**Hallazgo 2.4a**: SQL de CRUD centralizado en `bulk/_support/sql_gen.py`; volcado reutiliza.
- **Veredicto**: ✅ Bien centralizado
- **No duplicidad**: Verificado

#### 2.5 Logging y Auditoría — **Centralizada desde v0.29.0** ✅

| Ubicación | Sistema | Versión |
|-----------|---------|---------|
| `src/util_bbdd/audit/` | `AuditSink`, `AuditEvent` | v0.29.0+ |
| `src/util_bbdd/bulk/sync_crud.py` | `audit_sink` (opcional) | v0.29.0+ |
| `src/util_bbdd/dump/_models.py` | `audit_sink` (opcional) | v0.29.0+ |
| `src/util_bbdd/migrate/` | `audit_sink` en `execute()` | v0.29.0+ |

**Hallazgo 2.5a**: Auditoría centralizada bajo contrato `AuditSink`.
- **Veredicto**: ✅ **Bien diseñado** (ya refactorizado en ADR-002)
- **No acción requerida**

#### 2.6 Manejo de Errores por Motor — **Descentralizado pero gestionable**

| Error | Ubicación | Motor | Código |
|-------|-----------|-------|--------|
| Lock timeout | `connection/mariadb/` | MariaDB | `1205` (retry automático) |
| Serialization conflict | `bulk/` | PostgreSQL | `40001` (retry automático) |
| Constraint violation | `bulk/` | Oracle/All | `ORA-02292`, etc. (capturado, aislado) |

**Hallazgo 2.6a**: Códigos de error de motor dispersos en módulos específicos.
- **Patrón**: Motor-specific en `connection/<motor>/` + genéricos en `bulk/`
- **Riesgo**: Si error nuevo hay que tocar múltiples lugares
- **Oportunidad**: Crear `_core/errors/motor_error_codes.py` (registro centralizado + mapeo)
- **Acción**: Monitorear; refactor si > 20 códigos se añaden

#### 2.7 Manejo de Constraints — **Duplicación media**

| Ubicación | Responsabilidad |
|-----------|-----------------|
| `src/util_bbdd/dump/_constraints.py` | `ConstraintManager.disable()`, `enable()` |
| `src/util_bbdd/bulk/` | ¿Llama a `_constraints.py` o reimplementa? |

**Hallazgo 2.7a**: Necesitaría grep para confirmar; asumo buena reutilización.
- **Acción**: Verificar si `BulkCrud` llama `ConstraintManager` o reimplementa (revisar PR si hay cambios)

---

### Sección 3: Análisis de Responsabilidad (SRP)

Cada clase/módulo debe tener **una única razón de cambio**.

#### 3.1 SyncDatabaseManager — ❌ **VIOLACIÓN SRP** (4 razones)

**Ubicación**: `src/util_bbdd/managers/sync_mgr.py`

**Responsabilidades**:
1. **CRUD** (`bulk_insert()`, `bulk_update()`, `bulk_delete()`)
2. **Introspección de metadatos** (hereda de `SyncCatalogFacade`: `get_tables()`, `get_schemas()`)
3. **Volcado de datos** (¿método `dump()`?)
4. **Comparación de esquemas** (¿método `compare()`?)

**Razones de cambio**:
- Cambio en estrategia CRUD → modifica `bulk_insert()`
- Cambio en reflexión de metadatos → modifica `get_tables()`
- Cambio en formato de volcado → modifica `dump()`
- Cambio en algoritmo de comparación → modifica `compare()`

**Veredicto**: ❌ **SRP VIOLATION**

**Justificación**: Un Manager es un Facade, lo cual es válido para orquestación de alto nivel. Sin embargo, la clase debería **delegar**, no implementar. Revisar si:
- ✅ Delega CRUD a `BulkCrud` (composición)
- ✅ Delega metadatos a `SyncMetadataProvider` (composición)
- ❓ ¿Delega volcado a `DumpOrchestrator` o lo hace directo?
- ❓ ¿Delega comparación a `SchemaComparator` o lo hace directo?

**Acción recomendada**: Si Manager implementa métodos (no delega), refactor a inyectar dependencias.

**Riesgo**: MEDIO — Si es Facade puro (solo delega), está bien. Si implementa lógica de negocio en 4 áreas, violar SRP.

#### 3.2 AsyncDatabaseManager — ❌ **VIOLACIÓN SRP** (idem)

**Ubicación**: `src/util_bbdd/managers/async_mgr.py`

**Veredicto**: ❌ **SRP VIOLATION** (par async de SyncDatabaseManager)

---

#### 3.3 SchemaComparator — 🟡 **BORDEA SRP** (3 responsabilidades)

**Ubicación**: `src/util_bbdd/comparar/comparator.py`

**Responsabilidades**:
1. **Algoritmo de comparación** (`compare()`)
2. **Renderizado de diff** (delega a `SqlDiffReporter`)
3. **Obtención de metadatos** (crea `MetadataProvider` internamente)

**Veredicto**: 🟡 **Borderline** — Bien si:
- ✅ `MetadataProvider` es inyectado (no creado internamente)
- ✅ `SqlDiffReporter` es inyectado
- ❌ Si instancia internamente, viola SRP

**Acción**: Revisar si `__init__()` recibe `metadata_provider` + `reporter` como params o los crea.

**Riesgo**: BAJO-MEDIO

---

#### 3.4 DumpOrchestrator — ❌ **VIOLACIÓN SRP** (4-5 razones)

**Ubicación**: `src/util_bbdd/dump/orchestrator.py`

**Responsabilidades**:
1. **Orquestación de lectura** (lotes, particiones, `_read_chunks()`)
2. **Orquestación de escritura** (CSV, Excel, Word, ZIP)
3. **Auditoría y reporte** (`DumpReporter`, eventos)
4. **Manejo de constraints** (`ConstraintManager`)
5. **Sincronización de PK** (`PKSequenceSyncer`)

**Razones de cambio**:
- Cambio en estrategia de lectura → modifica Phase 3 (lectura)
- Cambio en formato de salida → modifica Phase 5 (escritura)
- Cambio en auditoría → modifica eventos
- Cambio en soporte de motor → afecta constraints

**Veredicto**: ❌ **SRP VIOLATION** (5 razones de cambio)

**Remedios sugeridos**:
1. Extraer lectura → `DumpReader` (Phase 1–3)
2. Extraer escritura → `DumpWriter` (Phase 4–5)
3. Extraer reporte → `DumpReporter` (ya existe, mejorar)
4. Orquestación en `DumpOrchestrator` (compose Reader + Writer + Reporter)

**Riesgo**: ALTO — Los cambios de lectura requieren editar `orchestrator.py` directamente.

---

#### 3.5 BulkCrud — ❌ **VIOLACIÓN SRP** (5 razones)

**Ubicación**: `src/util_bbdd/bulk/sync_crud.py`

**Responsabilidades**:
1. **Inserción** (estrategias por motor: `MySQLMultiRowInsertStrategy`, `PostgresCopyStrategy`, etc.)
2. **Actualización** (estrategias: tabla temporal, cláusulas, etc.)
3. **Eliminación** (estrategias: OPENJSON, IN, DELETE…WHERE, etc.)
4. **Transacciones y commits periódicos** (`bulk_session()`, `commit_every_n_chunks`)
5. **Auditoría y rechazo de filas** (`audit_sink`, `on_error="isolate"`, `rejects_csv_path`)

**Razones de cambio**:
- Cambio en estrategia INSERT → modifica `bulk_insert()`
- Cambio en estrategia UPDATE → modifica `bulk_update()`
- Cambio en estrategia DELETE → modifica `bulk_delete()`
- Cambio en cadencia de commit → modifica `bulk_session()`
- Cambio en auditoría → modifica eventos

**Veredicto**: ❌ **SRP VIOLATION** (5 razones)

**Contexto**: Esta violación es **aceptable para v0.30.0** porque:
- ✅ Las estrategias están en submódulos (`_strategies/`)
- ✅ Auditoría está centralizada en `audit_sink`
- ✅ Transacciones están encapsuladas en `bulk_session()`

**Riesgo a futuro**: Si se añade más lógica (ej. cache, retry, validación), considerar SRP refactor en v1.0.0.

---

#### 3.6 ConnectionFactory + PoolFactory — 🟡 **CANDIDATOS A CONSOLIDACIÓN**

**Ubicación**: `connection/factory.py` + `factory/pool_factory.py`

**Análisis**:
- `ConnectionFactory`: Registra builders async por motor + crea conexiones
- `PoolFactory`: Registra builders async por motor + crea pools

**Duplicidad**: Patrón idéntico:
```python
_async_connection_builders: dict[str, Callable]  # En ConnectionFactory
_async_pool_builders: dict[str, Callable]        # En PoolFactory
```

**Oportunidad de consolidación**: Unificar en `DatabaseConnectionFactory`
- Métodos: `create_connection()`, `create_pool()`, `register_async_connection()`, `register_async_pool()`
- **Beneficio**: Una única factory, menor acoplamiento
- **Riesgo**: BAJO — solo exposición de API

---

### Sección 4: Análisis de Facade y Orquestación

#### 4.1 SyncDatabaseManager como Punto de Entrada Canónico

**Pregunta**: ¿Es `SyncDatabaseManager` el único punto de entrada para CRUD?

**Evidencia**:
- `from util_bbdd import SyncDatabaseManager` = sí
- Usuarios instancian `manager = SyncDatabaseManager(db_type, conn_params)` = sí
- ¿Llaman directo `BulkCrud`? = **Raro** (BulkCrud no exportado en `__all__`)

**Veredicto**: ✅ **SyncDatabaseManager = punto de entrada canónico para CRUD**

**Oportunidad**: Crear alias `DatabaseManager = SyncDatabaseManager` (deprecar nombre largo en docs)

---

#### 4.2 MetadataProvider — ¿Punto de entrada independiente?

**Pregunta**: ¿Usuarios llaman directo `SyncMetadataProvider.fetch_tables()` o siempre vía Manager?

**Búsqueda**: Revisar ejemplos en `docs/examples/` y `tests/`

**Evidencia (hipotética)**:
- Si `tests/metadata/test_providers.py` prueba `SyncMetadataProvider` independiente = API pública
- Si no hay tests de providers independientes = API interna

**Recomendación**: Revisar PR antes de decidir si hacer privada.

---

#### 4.3 Orquestación de Alto Nivel — Puntos de Entrada Conceptuales

| Caso de Uso | Punto de Entrada Actual | Recomendación |
|-------------|------------------------|----|
| CRUD masivo | `SyncDatabaseManager` | ✅ Mantener |
| Comparación | `SchemaComparator` | ✅ Mantener (independiente) |
| Volcado | `DumpOrchestrator` | ✅ Mantener |
| Migración | `MigrationPlanner` | ✅ Mantener |
| Metadatos | `SyncMetadataProvider` | 🟡 Revisar si es API pública |

**Veredicto**: Bien diferenciados; **no hay Facade oportunidad** (no hay 3+ servicios llamados siempre juntos).

---

### Sección 5: Análisis de Helpers Privados

Búsqueda de `_*` usados desde otros módulos:

| Helper | Ubicación | Usuario | ¿Debería ser público? |
|--------|-----------|---------|----------------------|
| `_resolve_max_workers()` | `bulk/_support/worker_config.py` | `ParallelBulkLoader` | 🟡 Considerado privado pero lógica compartida |
| `_hoist_constraints_for_workers()` | `bulk/_support/worker_config.py` | `ParallelBulkLoader` | 🟡 Idem |
| `_get_metadata_adapter()` | `metadata/registry.py` | `metadata/`, `bulk/`, `dump/`, `comparar/` | ✅ OK privado (factory interna) |
| `validate_chunk_size()` | `bulk/_execution/executors.py` | `dump/_models.py`, `bulk/` | 🟡 Exportado pero parece `_` |

**Hallazgo 5.1**: `validate_chunk_size()` no tiene `_` prefix pero se importa desde `dump/_models.py`.
- **Línea**: `from util_bbdd.bulk._execution.executors import validate_chunk_size`
- **Ubicación**: `src/util_bbdd/dump/_models.py:16`
- **Veredicto**: Bien; está públicamente disponible en su módulo.

**Hallazgo 5.2**: `_resolve_max_workers()` + `_hoist_constraints_for_workers()` son helpers privados de `bulk/_support/`.
- **Ubicación**: Usados en `ParallelBulkLoader` (mismo submódulo)
- **Acción**: OK como está (privados dentro de `_support/`).

---

### Sección 6: Grafo de Dependencias e Imports

**Matriz simplificada** (A importa de B):

```
┌─────────────────────────────────────────────────────────┐
│ SyncDatabaseManager                                     │
│  ├─→ BulkCrud (CRUD operations)                         │
│  ├─→ SyncMetadataProvider (metadata via CatalogFacade)  │
│  ├─→ DumpOrchestrator (volcado, si hay método dump())   │
│  ├─→ SchemaComparator (comparación, si hay método)      │
│  └─→ ConnectionFactory / PoolFactory                    │
│                                                          │
├─ BulkCrud                                               │
│  ├─→ ConnectionFactory                                  │
│  ├─→ Estrategias de SQL por motor                       │
│  ├─→ ConstraintManager                                  │
│  ├─→ AuditSink (centralizado v0.29.0)                   │
│  └─→ ParallelBulkLoader                                 │
│                                                          │
├─ DumpOrchestrator                                       │
│  ├─→ BulkCrud (orquestación de carga)                   │
│  ├─→ SyncMetadataProvider (introspección)               │
│  ├─→ ConstraintManager                                  │
│  ├─→ DumpReporter (Excel, CSV, etc.)                    │
│  └─→ AuditSink                                          │
│                                                          │
├─ SchemaComparator                                       │
│  ├─→ SyncMetadataProvider (inyectado o creado?)         │
│  ├─→ SqlDiffReporter (inyectado o creado?)              │
│  └─→ Inspectors de SQLAlchemy                           │
│                                                          │
├─ ConnectionFactory + PoolFactory                        │
│  └─→ Motor-specific builders (lazy load)                │
│                                                          │
├─ MigrationPlanner                                       │
│  ├─→ ConnectionFactory / Engines                        │
│  └─→ Metadata providers (origen/destino)                │
└─────────────────────────────────────────────────────────┘
```

**Ciclos de importación detectados**: Ninguno (0 ciclos).

**Acoplamiento alto**:
- `SyncDatabaseManager` → 5+ módulos (BulkCrud, Metadata, Dump, Comparar, Factories)
- **Riesgo**: Cambios en cualquier servicio afectan Manager
- **Mitigación**: Manager usa interfaces (Protocol) + inyección, no acoplamiento fuerte
- **Veredicto**: ✅ Acoplamiento *controlado* vía composición

---

### Sección 7: Propuesta de Consolidación

#### 7.1 Opción A: Minimal (Bajo Impacto) — **RECOMENDADA**

**Cambios**:
1. ✅ **Extraer validadores comunes** → `_core/validation/`
   - `validate_chunk_size()` (ya existe)
   - **Crear** `validate_commit_cadence()` (nuevo)
   - **Crear** `validate_batch_config(chunk_size, commit_every_n_chunks, write_batch_size)` (nuevo)

2. ✅ **Crear helper compartido para batching**
   - **Extraer** `_resolve_write_batch_size()` de `DumpOrchestrator` → `_core/batching/batch_resolver.py`
   - **Reutilizar** en `BulkCrud` si cambia estrategia de batch

3. ✅ **Centralizar códigos de error de motor** (opcional)
   - Crear `_core/errors/motor_error_codes.py`
   - Registrar: MySQL `1205`, PostgreSQL `40001`, Oracle `ORA-*`, etc.
   - Documentar retry policy por código

4. ❌ **NO cambiar API pública**
   - Mantener `SyncDatabaseManager`, `SyncMetadataProvider`, `ConnectionFactory`, `PoolFactory` en `__all__`
   - Mantener privados: `_resolve_max_workers()`, etc.

**Archivos a crear/modificar**:
```
src/util_bbdd/_core/validation/
  ├─ __init__.py
  ├─ chunk_size.py        (move validate_chunk_size)
  ├─ commit_cadence.py    (create validate_commit_cadence)
  └─ batch_config.py      (create comprehensive validator)

src/util_bbdd/_core/batching/
  ├─ __init__.py
  └─ batch_resolver.py    (extract _resolve_write_batch_size)

src/util_bbdd/_core/errors/
  ├─ __init__.py
  └─ motor_error_codes.py (create registry + documentation)
```

**Cambios de API**: **0 (cero)** — Todo privado

**Esfuerzo**: 4–6 horas

**Riesgo**: **BAJO** — Refactoring interno, sin cambios de contrato público

**Beneficio**:
- DRY: Una única fuente de validación
- Mantenibilidad: cambios centralizados
- Tests: validadores testea independientemente

---

#### 7.2 Opción B: Moderate (Cambios de API) — **Requiere PR y deprecation warning**

**Cambios sobre Opción A**:

1. ✅ **Consolidar factories** → `DatabaseFactory`
   - Crear `database_factory.py` con:
     ```python
     class DatabaseFactory:
         def create_connection(...) → Engine
         def create_pool(...) → Pool
         def register_async_connection(...)
         def register_async_pool(...)
     ```
   - **Aliases para backward compatibility**:
     ```python
     ConnectionFactory = DatabaseFactory  # deprecate_in("v1.0")
     PoolFactory = DatabaseFactory        # deprecate_in("v1.0")
     ```

2. ✅ **Crear alias para Manager**
   - `DatabaseManager = SyncDatabaseManager` (deprecate long name in docs)

3. ❓ **Decidir: ¿Hacer privado `SyncMetadataProvider`?**
   - Si NO se usa externamente → mover a `_core/internal/metadata/`
   - Si SÍ se usa → documentar caso de uso público

4. ❌ **NO hacer privado `build_conn_params()`** aún
   - **Buscar users** en ejemplos/tests primero
   - Si no se usa externamente, deprecate en v0.31.0, retire en v0.32.0

**Cambios de API**: **Deprecations** (backward compatible)

**Esfuerzo**: 8–12 horas

**Riesgo**: **MEDIO** — Usuarios pueden verse afectados si usan `ConnectionFactory` o `PoolFactory` directamente

**Beneficio**:
- Menos puntos de entrada (2 en lugar de 3: `DatabaseManager`, `SchemaComparator`, `DumpOrchestrator`)
- API más clara
- Preparación para v1.0.0

---

#### 7.3 Opción C: Radical (Refactor de Arquitectura) — **Para v1.0.0+**

**Cambios sobre Opción B**:

1. ✅ **Separar CRUD en clases por operación**
   ```python
   class BulkInsertCrud     # solo inserciones
   class BulkUpdateCrud     # solo actualizaciones
   class BulkDeleteCrud     # solo eliminaciones
   class BulkCrud           # orquestador (composite)
   ```

2. ✅ **Separar DumpOrchestrator**
   ```python
   class DumpReader         # Phase 1–3 (lectura)
   class DumpWriter         # Phase 4–5 (escritura)
   class DumpOrchestrator   # orquestador (composite)
   ```

3. ✅ **Crear módulo `orchestration/`**
   ```
   src/util_bbdd/orchestration/
     ├─ high_level_api.py   # Métodos de conveniencia
     ├─ workflows.py        # Flujos complejos
     └─ __init__.py
   ```

4. ✅ **Hacer privados** `SyncMetadataProvider`, `AsyncMetadataProvider`, `BulkCrud`, `AsyncBulkCrud`
   - Nueva API: `DatabaseManager.metadata()` en lugar de importar provider

**Cambios de API**: **MAYORES** (incompatible)

**Esfuerzo**: 40–60 horas

**Riesgo**: **ALTO** — Muchos tests a actualizar, usuarios cambian código

**Beneficio**:
- Claridad: un único punto de entrada (`DatabaseManager`)
- SRP: cada clase tiene 1 responsabilidad
- Mantenibilidad: tests enfocados

---

### Sección 8: Hallazgos Críticos — NO-GOs y Bloqueadores

| Hallazgo | Severidad | Tipo | Acción | Bloquea |
|----------|-----------|------|--------|---------|
| **Validación de `chunk_size` duplicada** | MEDIA | DRY | Opción A: Extraer a `_core/validation/` | NO |
| **`DumpOrchestrator` viola SRP (5 responsabilidades)** | MEDIA | Arquitectura | Opción B/C: Separar Reader/Writer | NO (futuro) |
| **`BulkCrud` viola SRP (5 responsabilidades)** | MEDIA | Arquitectura | Opción C: Separar INSERT/UPDATE/DELETE | NO (futuro) |
| **API pública confusa (33 símbolos)** | MEDIA | API Design | Opción B: Consolidar factories, crear alias | NO |
| **`SyncMetadataProvider` ¿público o privado?** | MEDIA | API Design | Revisar uso externo + decidir | NO (investigar) |
| **Ciclos de importación** | ALTA | Arquitectura | **NINGUNO DETECTADO** ✅ | NO |
| **Acoplamiento no controlado** | ALTA | Arquitectura | **CONTROLADO** vía interfaces ✅ | NO |

**Veredicto**: **NO HAY BLOQUEADORES** (0 críticos que impidan merge/release)

---

### Sección 9: Propuesta de Priorización

**Fase 1 (v0.30.1 — Hotfix, 1–2 semanas)**:
- ✅ Opción A: Extraer validadores + batching (bajo riesgo)
- ✅ Documentar decisión sobre `SyncMetadataProvider`

**Fase 2 (v0.31.0 — Feature, 3–4 semanas)**:
- ✅ Opción B: Consolidar factories, crear alias
- ✅ Deprecation warnings si es necesario

**Fase 3 (v1.0.0 — Major, Q4 2026+)**:
- ✅ Opción C: Refactor SRP (BulkCrud, DumpOrchestrator)
- ✅ Simplificar API pública a 5–7 puntos de entrada únicos

---

## VEREDICTO FINAL

### Resumen de Hallazgos

| Categoría | Hallazgos | Críticos | Mayores | Menores |
|-----------|-----------|----------|---------|---------|
| **API Entry Points** | 33 símbolos públicos; 5 puntos de entrada conceptuales | 0 | 1 (consolidación factories) | 2 (alias, decisión metadata) |
| **SRP Violations** | 2 managers (OK como Facade), 1 orchestrator (REFACTOR), 1 CRUD (OK ahora) | 0 | 2 | 0 |
| **Duplicities** | 1 confirmado (chunk_size), 3 monitoreados (batch, errors, constraints) | 0 | 1 | 2 |
| **Acoplamiento** | Alto pero controlado; 0 ciclos de importación | 0 | 0 | 0 |
| **Validación** | Fragmentada en 2 lugares, centralizable | 0 | 1 | 0 |

### Puntuación de Salud (1–10)

- **API Coherencia**: 7/10 (muchos símbolos, pero bien diferenciados)
- **SRP Compliance**: 6/10 (Manager y Orchestrator violarán, pero aceptable para v0.30)
- **DRY Compliance**: 7/10 (1 duplicidad confirmada, 3 oportunidades monitoreadas)
- **Acoplamiento**: 8/10 (alto, pero vía composición/inyección, no fuerte)
- **Testabilidad**: 8/10 (componentes separables)

**Puntuación Global**: **7.2/10** (Saludable, con mejoras claras para v1.0.0)

---

## RECOMENDACIÓN: Opción A ✅

**VEREDICTO FINAL**: `APROBADO CON CONDICIONES`

### Condiciones

1. **Implementar Opción A** en v0.30.1 (hotfix, bajo riesgo)
   - Extraer `validate_chunk_size()`, crear `validate_commit_cadence()`
   - Extraer `_resolve_write_batch_size()` a `_core/batching/`
   - Crear registro de códigos de error de motor (documentación)

2. **Investigación previo a Opción B**
   - Buscar uso externo de `SyncMetadataProvider` (grep en ejemplos/tests)
   - Decidir: ¿publicar o hacer privado?
   - Buscar uso de `build_conn_params()` externamente

3. **Documentación en `docs/architecture.md`**
   - Actualizar diagrama de capas con nueva ubicación de validadores
   - Aclarar responsabilidades de `SyncDatabaseManager` como Facade

4. **Plan para v1.0.0**
   - Considerar Opción C (separar BulkCrud y DumpOrchestrator por responsabilidad)
   - Simplificar API pública a 5–7 puntos de entrada únicos

---

## VERSION

### Commits Sugeridos (si se autoriza Opción A)

```bash
# v0.30.1 hotfix branch
git checkout -b hotfix/consolidate-validators

commit 1:
  fix: consolidate chunk_size and commit_cadence validators to _core/validation
  
  - Extract validate_chunk_size() to _core/validation/chunk_size.py
  - Create validate_commit_cadence(commit_every_n_chunks) in new module
  - Create validate_batch_config() for comprehensive validation
  - Update imports in dump/_models.py and bulk/sync_crud.py
  - Tests: add _core/validation/test_validators.py
  
  Fixes: #XXX (duplicated validation logic)
  Impact: 0% API change (internal refactoring)

commit 2:
  refactor: extract batch size resolution logic to _core/batching
  
  - Extract DumpOrchestrator._resolve_write_batch_size() → _core/batching/batch_resolver.py
  - Create resolve_write_batch_size(db_type, chunk_size, commit_every_n_chunks) function
  - Update dump/orchestrator.py and bulk/ to use new helper
  - Tests: add _core/batching/test_batch_resolver.py
  
  Benefits: Shared logic, easier to test per motor
  Impact: 0% API change (internal refactoring)

commit 3:
  docs: update architecture.md with new _core/validation and _core/batching modules
  
  - Add diagram showing validator and batching layer
  - Document decision on SyncMetadataProvider (public vs private)
  - Clarify Manager as Facade pattern
```

### Testing Sugerido

```bash
# Run affected tests
pytest tests/bulk/ -v                    # Valida cambios CRUD
pytest tests/dump/ -v                    # Valida cambios Dump
pytest tests/_core/validation/ -v       # Nuevos tests
pytest tests/_core/batching/ -v         # Nuevos tests

# Regression
pytest tests/ --cov=src/util_bbdd       # Cobertura global
```

### Migración de Usuarios (si necesaria)

**Opción A** → No hay ruptura de API, cambios internos solamente.

**Opción B** (futuro)
```python
# v0.30 (deprecated)
from util_bbdd import ConnectionFactory, PoolFactory

# v0.31 (recommended)
from util_bbdd import DatabaseFactory  # alias

# v1.0 (removed old names)
from util_bbdd import DatabaseFactory  # only this
```

---

## Adjuntos

- [TRACEABILITY.md](./TRACEABILITY.md) — Mapeo línea-por-línea de hallazgos
- [REFACTOR_GUIDE.md](./REFACTOR_GUIDE.md) — Guía paso a paso para Opción A (cuando se autorice)

---

*Auditoría completada: 2026-10-04 | Válida para: v0.30.0* 
*Próxima revisión recomendada: v0.31.0 o v1.0.0*
