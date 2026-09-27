# PLAN y AUDIT_PLAN — pendientes del plan de reutilización de `bulk/` y `dump/`

- **Fecha**: 2026-09-27 · **Base**: `v0.17.3` (`develop`, `5c23d05`)
- **Flujo**: `/new-feature` — este documento cubre PLAN y AUDIT_PLAN. IMPLEMENT solo tras aprobación.
- **Origen**: los cuatro puntos que el refactor dejó fuera por cambiar comportamiento
  (`.ai/sessions/2026-09-26ze-code-reusability-bulk-dump/`, `2026-09-27-version-closure-v0.17.3/TRACEABILITY.md`).
- **Hallazgo nuevo al planificar**: el punto 2 esconde un defecto (2a), comprobado con un script (§ 2).

---

## Resumen

| # | Punto | Tipo | Riesgo | Esfuerzo | Recomendación |
|---|---|---|---|---|---|
| 2a | Un commit periódico del DELETE confirma filas de INSERT que `rows_committed` no cuenta | **fix** | Bajo | 2–3 h | Hacer primero |
| 1 | Una sola regla de capacidad del pool (`bulk` usa `size`; `dump`, `size + max_overflow`) | cambio de comportamiento | Medio | ½–1 día | Hacer, con la guarda de § 1 |
| 2b | `rows_committed` cuenta también las filas del DELETE | cambio de semántica | Bajo | 2 h (sobre 2a) | Decisión D-2 |
| 3 | `AuditError` bajo `DatabaseException` (`_core/exceptions.py`) | cambio de comportamiento | Bajo | 2–3 h | Hacer |
| 4 | Destino de `BulkInserter` (Protocol público sin uso) | deprecación | Bajo | 1–2 h | Deprecar ahora, retirar después |

Versionado propuesto: 2a como **v0.17.4** (PATCH). 1, 2b, 3 y 4 juntos como **v0.18.0** (MINOR: cambian
comportamiento observable y añaden una deprecación, sin romper firmas).

---

## 1. Regla única de capacidad del pool

### Inputs

| Campo | Valor |
|---|---|
| Objetivo | Que `ParallelBulkLoader` y `DumpOrchestrator` calculen igual cuántas conexiones admite un engine |
| Módulos | `bulk/_execution/parallel_loader.py` (`_resolve_max_workers`), `dump/orchestrator.py` (`_pool_capacity`, `_resolve_max_workers`, `_resolve_range_count`), nuevo `bulk/_support/pool.py` |
| API pública | Sin cambios de firma. Cambia el número efectivo de workers de `ParallelBulkLoader` cuando el pool tiene `max_overflow > 0` |
| Contrato de entrada | `Engine` con `QueuePool` (o sin `size()`: `NullPool`, `StaticPool`, mocks) |
| Contrato de salida | `pool_capacity(engine) -> int \\| None`: `size + max_overflow`; `None` si no se puede determinar |
| Reglas | Nunca más workers que conexiones disponibles; aviso WARNING al recortar (uno, no dos) |
| Restricciones | Sin dependencias nuevas; `_max_overflow` es un atributo privado de `QueuePool` (ya lo lee `dump`) |
| Motores | Todos (política de pool, no de dialecto) |
| Ficheros existentes | Sí: los citados y `tests/unit/bulk/test_parallel_loader.py` (7 tests de recorte), `tests/unit/dump/test_orchestrator.py` (`test_pool_capacity_includes_overflow`, `test_degrades_to_min_pool_capacity`) |

### PLAN

- **Situación actual**: `ParallelBulkLoader._resolve_max_workers` recorta a `pool.size()` (decisión 2026-06-02:
  «workers > pool_size causa deadlock»). `DumpOrchestrator._pool_capacity` usa `size + max_overflow` (lo documenta
  `DumpConfig.max_parallel_tables`). `dump` crea un `ParallelBulkLoader` por tabla con `parallel_pk_ranges`: calcula los
  rangos con una regla y el loader los vuelve a recortar con otra, con un segundo WARNING.
- **Por qué el loader era conservador** (comprobado en el código): en la ruta `disable_constraints=True`,
  `_load_with_maintenance` abre `bulk_session()` y después `maintenance_scope()`, que llama a `reflect_table()` por
  primera vez **con la sesión abierta**: cada worker usa dos conexiones a la vez durante la reflexión. Con
  `size + max_overflow` workers, el pool podría agotarse (`TimeoutError` de `QueuePool` a los 30 s).
- **Cambio**:
  1. `bulk/_support/pool.py: pool_capacity(engine) -> int | None` con la regla de `dump` endurecida: `max_overflow`
     que no sea `int` (mocks) cuenta como 0; `max_overflow < 0` (ilimitado) → `None` (sin recorte).
  2. `ParallelBulkLoader._resolve_max_workers` y `DumpOrchestrator._pool_capacity` la usan.
  3. **Guarda**: `_load_with_maintenance` refleja la tabla **antes** de abrir la sesión (`crud.reflect_table(tabla)`),
     para que cada worker use una sola conexión. Así `size + max_overflow` workers es seguro.
  4. Texto del WARNING del loader: «capacidad del pool (pool_size + max_overflow)» en lugar de «pool size».
- **Componentes**: `ParallelBulkLoader`, `DumpOrchestrator`, `pool_capacity`.
- **Tipos**: ninguno nuevo.

### AUDIT_PLAN

- **Funcionales**:
  - Con el engine por defecto (`pool_size=5, max_overflow=10`), `ParallelBulkLoader(max_workers=12)` pasa de 5 a 12
    workers: más carga concurrente sobre el servidor. Es lo que el usuario pidió con `max_workers`, pero cambia lo
    observado. Va en CHANGELOG como *Changed*.
  - `max_overflow=-1` (ilimitado): hoy `dump` lo trata como `size`; con la regla nueva no hay recorte. Decisión D-1.
  - Cambia el texto del WARNING: 2 tests buscan «pool size» (`test_pool_size_warning_emitted`,
    `test_cap_emits_warning_with_pool_size_text`).
- **Técnicos**:
  - `int(MagicMock())` vale 1: sin el endurecimiento del paso 1, los 7 tests del loader (que solo fijan `size()`)
    verían capacidad `size + 1`. Con él siguen igual.
  - La guarda del paso 3 hay que comprobarla: un test que cuente conexiones simultáneas por worker (evento
    `checkout`/`checkin` del pool) en la ruta con `disable_constraints=True`.
  - `_max_overflow` es privado de SQLAlchemy: si desapareciera, `pool_capacity` debe degradar a `size` (no a `None`).
  - Capas: `dump` (7) → `bulk` (6): permitido.
- **Seguridad**: ninguno (no toca SQL).
- **Simplificaciones**: no hace falta un parámetro nuevo; si D-1 se decide «como hoy», el paso 1 es una copia exacta del
  `_pool_capacity` de `dump` más el endurecimiento de mocks.
- **Veredicto**: **GO_CONDICIONAL** — condición: la guarda del paso 3 con su test de conexiones simultáneas.

---

## 2. `rows_committed` y el DELETE

### 2a. Defecto: un commit del DELETE confirma filas de INSERT que no se cuentan

Reproducido (SQLite, `chunk_size=1`, `commit_every_n_chunks=2`): en una `bulk_session`, INSERT de 1 fila (pendiente),
DELETE de 2 filas (commit periódico del DELETE) y error. En la BD: la fila insertada y los 2 borrados confirmados.
`rows_committed` = **0** (debería ser 1). `unaudited_committed_rows` = 0 (correcto: la auditoría sí se volcó en ese
commit por el gancho de la sesión).

**Causa**: los dos ejecutores comparten la conexión de la sesión (`SessionScope`, P-26), pero cada uno lleva sus
propias filas pendientes. Un commit de cualquiera confirma la transacción entera; solo el que hace el commit mueve sus
pendientes a confirmadas.

| Campo | Valor |
|---|---|
| Objetivo | Que cualquier commit de la sesión confirme en `rows_committed` todas las filas pendientes de INSERT/UPDATE |
| Módulos | `bulk/_execution/session.py`, `bulk/_execution/executors.py`, `bulk/crud.py`, tests |
| API pública | Sin cambios de firma; `rows_committed` deja de quedarse corto en sesiones que mezclan INSERT/UPDATE y DELETE |
| Reglas | Sin cadencia (`commit_every_n_chunks=None`) sigue en 0 (BLK-08) |

**PLAN**: separar en `CommitCadence` el contador de lotes (propio de cada ejecutor: el del DELETE por llamada) del
**libro de filas** (`rows_pending`/`rows_committed`), que pasa a `SessionScope` y comparten los dos ejecutores. Cada
commit (periódico de cualquiera, final de sesión o final de una llamada fuera de sesión) llama a
`session.confirm_rows()`. El DELETE sigue **sin sumar** filas (eso es 2b).

**AUDIT_PLAN**:
- Funcionales: solo cambia el valor en el caso del defecto. Los 5 tests de caracterización (`ca48fb4`, `b6b0269`)
  deben seguir pasando: la cadencia de lotes no cambia.
- Técnicos: `BatchStatementExecutor.rows_committed` lee del libro compartido; un ejecutor creado sin `SessionScope`
  (tests, uso directo) tiene el suyo propio, como hoy.
- Seguridad: ninguno.
- **Veredicto**: **GO**. Test de regresión: el escenario de arriba (`rows_committed == 1`).

### 2b. Contar también las filas del DELETE

| Campo | Valor |
|---|---|
| Objetivo | Que `rows_committed` sea «filas enviadas y confirmadas» de INSERT, UPDATE **y DELETE** |
| Módulos | `executors.py` (el DELETE registra sus filas en el libro de 2a), `_support/persistence.py` (`_dml_rows` deja de excluir DELETE), docstrings de `BulkCrud.rows_committed` y `unaudited_committed_rows` |
| API pública | Cambia el valor de `BulkCrud.rows_committed` cuando hay DELETE con cadencia. `ParallelBulkLoader` y `dump` solo insertan: no les afecta |
| Reglas | Las filas del DELETE son las **enviadas** (`len(df)`), como en el CSV de auditoría, no las que la BD dice haber borrado |

**AUDIT_PLAN**:
- Funcionales: quien use `rows_committed` como «filas insertadas» en sesiones con DELETE verá un número mayor. Hoy el
  docstring dice que en sesiones con DELETE `unaudited_committed_rows` «es aproximado»: con 2b pasa a ser exacto
  (`committed_rows` y `_dml_rows` cuentan lo mismo).
- Técnicos: `_dml_rows` debe cambiar en el mismo commit que el ejecutor, o `unaudited_committed_rows` se descuadra.
- **Veredicto**: **GO_CONDICIONAL** — depende de D-2 (¿el nombre `rows_committed` debe incluir DELETE?).

---

## 3. `AuditError` dentro de la jerarquía de `_core/exceptions.py`

| Campo | Valor |
|---|---|
| Objetivo | Que los errores de auditoría de `bulk` hereden de `DatabaseException`, como los de `dump` y `comparar` |
| Módulos | `_core/exceptions.py` (clases nuevas), `bulk/_audit/errors.py` (re-exporta), `util_bbdd/__init__.py` (exportar, opcional), `docs/api/exceptions.md` |
| API pública | `AuditError`, `AuditConfigError`, `AuditFileError`, `AuditDataError`, `AuditValidationError` siguen importándose desde donde se importan hoy (`util_bbdd.bulk`, `util_bbdd.bulk.audit`) y son las mismas clases |
| Contrato | `AuditConfigError` sigue siendo también `ValueError` (H8) |

### PLAN

- Mover las 5 clases a `_core/exceptions.py`: `AuditError(DatabaseException)` y las 4 subclases con la misma herencia
  (`AuditConfigError(AuditError, ValueError)`). `bulk/_audit/errors.py` las importa y re-exporta.
- `docs/api/exceptions.md`: añadir la familia de auditoría (hoy no documenta ni `Dump*` ni `Audit*`).

### AUDIT_PLAN

- **Funcionales**:
  - Un `except DatabaseException` del **usuario** alrededor de operaciones bulk pasará a capturar también los errores
    de auditoría (solo se lanzan con `audit_strict=True` o por configuración). En la librería no cambia nada: los
    únicos `except DatabaseException` están en `analysis/`, que no llama a `bulk`; `ParallelBulkLoader` y `dump`
    capturan `AuditError` por nombre.
  - `str(exc)` no cambia: `DatabaseException` solo añade texto si se pasan `operation`, `db_type` o `details`, y las 7
    llamadas actuales pasan solo el mensaje.
- **Técnicos**:
  - MRO de `AuditConfigError(AuditError, ValueError)`: `DatabaseException.__init__` llama a `super().__init__(msg)`, que
    resuelve a `ValueError`: correcto. Añadir un test de `isinstance` (`ValueError`, `DatabaseException`) y de `str()`.
  - Capas: `bulk` (6) → `_core` (1): permitido.
- **Seguridad**: ninguno.
- **Simplificaciones**: no crear una `BulkError` intermedia hasta que haga falta.
- **Veredicto**: **GO**.

---

## 4. Destino de `BulkInserter`

| Campo | Valor |
|---|---|
| Objetivo | Resolver un Protocol público que ningún código usa y que no describe lo que el volcado necesita |
| Módulos | `dump/_protocols.py`, `dump/__init__.py`, `docs/api/dump-autodoc.md`, `.github/prompts/performance_audit_dump.prompt.md` (lo menciona) |
| API pública | `util_bbdd.dump.BulkInserter` emite `DeprecationWarning` al importarlo; se retira en la siguiente versión menor |

### PLAN

- Opciones: (a) retirarlo ya (rompe `from util_bbdd.dump import BulkInserter`); (b) **deprecarlo** con `__getattr__`
  de módulo en `dump/__init__.py` que avisa y lo devuelve; (c) convertirlo en el contrato real del colaborador del
  orquestador (`DumpWriter`), lo que exigiría inyectarlo en `DumpOrchestrator`: API nueva sin caso de uso.
- **Recomendado (b)**: aviso ahora, retirada en v0.19.0. `dump-autodoc.md` lo marca como obsoleto; el prompt de
  auditoría deja de citarlo como contrato.

### AUDIT_PLAN

- **Funcionales**: quien lo importe verá un `DeprecationWarning` (con `-W error`, un fallo). Por eso no se retira
  directamente.
- **Técnicos**: `__getattr__` de módulo (PEP 562) no afecta a `from util_bbdd.dump import *` si `BulkInserter` sale de
  `__all__`; el test de exportaciones públicas, si existe, se actualiza. mkdocstrings debe seguir resolviendo la página
  (se mantiene `dump/_protocols.py`).
- **Seguridad**: ninguno.
- **Veredicto**: **GO**.

---

## Decisiones pendientes

| ID | Decisión | Recomendación |
|---|---|---|
| D-1 | `max_overflow=-1` (ilimitado): ¿sin recorte o como hoy en `dump` (solo `size`)? | Sin recorte: es lo que significa ilimitado |
| D-2 | ¿`rows_committed` incluye el DELETE (2b)? | Sí: hace exacto `unaudited_committed_rows` y coincide con el CSV, que ya cuenta los DELETE |
| D-3 | `BulkInserter`: ¿deprecar (b) o retirar ya (a)? | Deprecar ahora, retirar en v0.19.0 |
| D-4 | ¿Exportar la familia `Audit*` en `util_bbdd/__init__.py`? | Sí, junto a `DumpError`, para que la jerarquía pública esté completa |
| D-5 | Versionado: 2a en v0.17.4 y el resto en v0.18.0, o todo en v0.18.0 | 2a primero en v0.17.4: es un fix y no depende de las decisiones |

## Orden de implementación propuesto

1. **2a** (fix) → `fix(bulk)` + test de regresión → v0.17.4 si D-5 se acepta.
2. **3** (`AuditError`) → `feat(bulk)`; independiente.
3. **4** (`BulkInserter`) → `feat(dump)!` o `chore(dump)` con deprecación; independiente.
4. **1** (capacidad del pool) con la guarda de conexiones → `feat(bulk,dump)`; tests de integración contra el banco.
5. **2b** (si D-2) sobre 2a → `feat(bulk)`.
6. Cierre v0.18.0.
