# PLAN + AUDIT_PLAN — Paquetes de opciones de BulkCrud y planificador de paralelismo (v3.0.0)

## Session metadata
- id: 2026-10-16f
- fecha: 2026-10-16
- rama: develop (base `75f24ae7`, v2.2.4)
- skill: new_feature + refactor incompatible (alcance mixto **pedido explícitamente** por el usuario)
- fase: PLAN + AUDIT_PLAN (sin IMPLEMENT; se espera aprobación)
- decisión del usuario: **opción B** — reempaquetar todos los parámetros de una vez, sin capa de compatibilidad;
  versión MAJOR (2.2.4 → **3.0.0**).

## Solicitud original saneada
Crear una estrategia para que la ejecución de `bulk/_execution/parallel_loader.py` se decida automáticamente con un
algoritmo optimizado, a partir de parámetros pedidos en la API de `BulkCrud` (como ya hace `dump`). `BulkCrud` recibe
más de 13 parámetros: el resto debe llegar en paquetes compactados. Analizar implicaciones en `bulk` y `dump`.

---

## PLAN

### Objetivo
1. Sustituir los 16 parámetros sueltos de `BulkCrud` (más `engine`) y los 17 de `ParallelBulkLoader` por **paquetes de
   opciones inmutables** comunes a los dos, para que `ParallelBulkLoader` y `dump` construyan sus workers con **el mismo
   objeto** y no copiando la lista de parámetros a mano.
2. Añadir un **planificador de paralelismo** puro (`ParallelPlanner`) que decide workers y particiones por motor,
   operación, volumen y capacidad del pool, con reglas basadas solo en mediciones del repositorio.
3. Permitir que `BulkCrud.bulk_*_from_df` delegue en `ParallelBulkLoader` cuando el usuario active
   `ParallelOptions(mode="auto" | "manual")`. Por defecto (`"off"`) el comportamiento es el actual.
4. Hacer que `dump` use el planificador (`parallel_pk_ranges="auto"`, `max_parallel_tables="auto"`) y elimine sus
   reglas duplicadas.

### Diseño de la API (3.0.0)

Paquetes en `util_bbdd.bulk` (submódulo público de tipos auxiliares, `docs/guides/api_1_0_migration.md`), todos
`@dataclass(frozen=True, slots=True, kw_only=True)` con validación en `__post_init__`:

| Paquete | Campos (nombre 3.0 ← nombre 2.x) |
|---|---|
| `BatchOptions` | `chunk_size`, `commit_every_n_chunks`, `prefetch_blocks` (mismos nombres) |
| `AuditOptions` | `csv_path ← audit_csv_path`, `strict ← audit_strict`, `sink ← audit_sink`, `run_id ← audit_run_id`, `warn_if_disabled ← warn_if_audit_disabled` |
| `RejectOptions` | `on_error`, `csv_path ← rejects_csv_path`, `max_rejects` (aquí `validate_isolation`) |
| `ExecutionOptions` | `fast_executemany ← enable_fast_executemany`, `insert_resolver`, `update_via_staging`, `strip_strings`, `reflect_foreign_keys` |
| `RetryOptions` | `max_retries`, `backoff ← retry_backoff`, `retry_on` (validación hoy en `ParallelBulkLoader.__init__`) |
| `ParallelOptions` | `mode: "off" \| "manual" \| "auto"`, `max_workers`, `partition_column`, `min_rows_per_partition`, `disable_constraints`, `retry: RetryOptions` |
| `BulkOptions` | agregado de los anteriores; es lo que se pasa a workers (`dataclasses.replace`) |

Firmas resultantes:

```python
BulkCrud(engine, *, batch=None, audit=None, rejects=None, execution=None, parallel=None)        # 6 parámetros
ParallelBulkLoader(engine, *, batch=None, audit=None, rejects=None, execution=None, parallel=None)
BulkCrud.options -> BulkOptions                    # solo lectura
BulkCrud.last_parallel_result -> ParallelLoadResult | None
ParallelLoadResult.plan -> ParallelPlan | None     # aditivo
```

Modos de `ParallelOptions`:

| Modo | Uso | Reglas aplicadas |
|---|---|---|
| `"off"` | Por defecto en `BulkCrud`. Ejecución en serie actual. | — |
| `"manual"` | Por defecto en `ParallelBulkLoader` (comportamiento actual, `max_workers=4`). | Solo **reglas de seguridad**: capacidad del pool, SQLite = 1 escritor, PostgreSQL sin `TEMP` en UPDATE = 1. |
| `"auto"` | Opt-in. | Seguridad + **reglas de rendimiento** medidas; `max_workers` actúa como tope. |

### Planificador (`bulk/_execution/parallel_planner.py`, nuevo)

- Entrada `PlanInput`: dialecto, operación, filas estimadas, capacidad de pool (destino; origen en `dump`), presupuesto
  de conexiones, PK particionable (`range` | `hash` | `None`), `temp_tables_allowed`, `ParallelOptions`.
- Salida `ParallelPlan`: `workers`, `n_partitions`, `partitioner`, `reasons: tuple[str, ...]`.
- Función pura y determinista: los hechos (pool, privilegio `TEMP`) los recoge el llamador (`pool_capacity`,
  `metadata.facts.can_create_temp_tables`). Sin SQL dentro.
- Tabla de reglas `_RULES: ClassVar[...]` con solo los datos medidos que ya constan en el repositorio:

| Motor | insert | update | delete |
|---|---|---|---|
| SQLite | 1 (PD-06) | 1 | 1 |
| MySQL/MariaDB | 1 (Q4: rangos +84 % a +94 %) | paralelo (2,2×, B-05) | paralelo + reintentos mínimos (R-5) |
| SQL Server | paralelo (−37 % con 4 rangos) | paralelo (2,9×) | **sin medir → serie** |
| PostgreSQL | paralelo solo sobre umbral (−9 %) | paralelo con `TEMP` (4×); sin `TEMP` 1 | **sin medir → serie** |
| Oracle | 1 (−2 %) | **sin medir → serie** | **sin medir → serie** |

  Cualquier celda sin medición = serie en `"auto"`. El umbral de filas (`min_rows_per_partition` por defecto) **no
  está medido**: es condición del GO (ver AUDIT_PLAN).

### Rutas afectadas

| Ruta | Cambio |
|---|---|
| `src/util_bbdd/bulk/options.py` (nuevo) | Paquetes de opciones y `BulkOptions` |
| `src/util_bbdd/bulk/_execution/parallel_planner.py` (nuevo) | `ParallelPlanner`, `PlanInput`, `ParallelPlan` |
| `src/util_bbdd/bulk/crud.py` | Constructor por paquetes; `options`; ruta paralela en `bulk_*_from_df` (import diferido del loader) |
| `src/util_bbdd/bulk/_execution/parallel_loader.py` | Constructor por paquetes; workers con `BulkCrud(engine, **options.for_worker())`; planificador; `plan` en el resultado; regla SQLite; reubicar `_skip_rows` y `_validate_partition_ranges`; quitar el alias `_closing_iterable` |
| `src/util_bbdd/bulk/_support/iterables.py` | Recibe `skip_rows` |
| `src/util_bbdd/bulk/_execution/range_partitioner.py` | Recibe `validate_disjoint(ranges, n)` |
| `src/util_bbdd/bulk/_support/rejects.py`, `_support/retry.py` | Validaciones invocadas desde los `__post_init__` |
| `src/util_bbdd/bulk/__init__.py` | Exporta los paquetes, `ParallelPlan` |
| `src/util_bbdd/dump/_models.py` | `max_parallel_tables` y `parallel_pk_ranges` aceptan `"auto"`; los campos planos de `DumpConfig` se mantienen |
| `src/util_bbdd/dump/orchestrator.py` | `_bulk_options()` devuelve `BulkOptions`; `_resolve_max_workers`, `_resolve_range_count`, `_warn_slow_pk_ranges`, `_single_writer_target` delegan en el planificador |
| `tests/unit/bulk/**`, `tests/unit/dump/**`, `tests/integration/**` | Migrar 245 construcciones de `BulkCrud` y 106 de `ParallelBulkLoader`; nuevos `test_options.py`, `test_parallel_planner.py`, `test_crud_parallel.py` |
| `docs/` (13 ficheros con `BulkCrud(`, 7 con `ParallelBulkLoader(`), `docs/examples/*.py`, `README.md`, `.ai/runtime.md`, `.ai/architecture.md` | Ejemplos a 3.0 |
| `docs/guides/api_3_0_migration.md` (nuevo) + `mkdocs.yml` | Tabla de equivalencias 2.x → 3.0 |
| `CHANGELOG.md`, `pyproject.toml` | 3.0.0 con guía de migración (regla CRÍTICA de breaking changes) |
| `scripts/` (3 ficheros con `BulkCrud(`) | Migrar |

### Grupos de implementación (un commit por grupo)

| Grupo | Contenido | Tipo |
|---|---|---|
| G1 | `options.py` + tests de validación de paquetes (sin cablear) | `feat(bulk)!` |
| G2 | `BulkCrud` y `ParallelBulkLoader` por paquetes; workers con `BulkOptions` (corrige que `insert_resolver`, `update_via_staging` y `prefetch_blocks` no llegaran a los workers); migración de tests, `dump`, scripts | `refactor(bulk)!` |
| G3 | `ParallelPlanner` + modos en `ParallelBulkLoader` (incluida la regla SQLite); `ParallelLoadResult.plan` | `feat(bulk)` |
| G4 | Ruta paralela opcional en `BulkCrud.bulk_*_from_df` | `feat(bulk)` |
| G5 | `dump` con planificador y `"auto"`; eliminar sus reglas duplicadas | `refactor(dump)` + `feat(dump)` |
| G6 | Reubicar funciones de módulo de `parallel_loader.py` | `refactor(bulk)` |
| G7 | Documentación, guía de migración, CHANGELOG, diagrama de capas | `docs` |
| G8 | Benchmarks del banco para el umbral de filas y las celdas sin medir | `perf` (puede ir a 3.1.0) |

### Componentes y tipos
`BatchOptions`, `AuditOptions`, `RejectOptions`, `ExecutionOptions`, `RetryOptions`, `ParallelOptions`, `BulkOptions`,
`ParallelPlanner`, `PlanInput`, `ParallelPlan`, `ParallelMode = Literal["off", "manual", "auto"]`,
`Partitioner = Literal["range", "hash"]`.

### Riesgos (detalle en AUDIT_PLAN)
Atomicidad, contrato de errores, recursión worker → paralelo, estado mutable de opciones, ciclo de imports, coste de la
migración de tests, umbrales sin medir, contadores de auditoría agregados.

---

## AUDIT_PLAN

### Riesgos funcionales

| # | Riesgo | Mitigación |
|---|---|---|
| F1 | **Atomicidad**: en serie `bulk_insert_from_df` es una transacción; en paralelo son N independientes. | `mode="off"` por defecto. Docstring y guía lo dicen explícitamente. `"auto"` nunca se activa solo. |
| F2 | **Contrato de errores**: en serie se lanza excepción; el loader acumula `partition_errors`. | En la fachada de `BulkCrud`, si hay errores de partición, lanzar `ParallelLoadError(DatabaseException)` (nueva, en `_core/exceptions`) con el `ParallelLoadResult`. El resultado queda también en `last_parallel_result`. |
| F3 | Casos incompatibles con paralelo: `generar_sql=True`, `bulk_session()` externo activo, `maintenance_scope` abierto, `bulk_*_from_chunks` (iterador de un solo uso, incompatible con la reanudación B-11). | El planificador recibe estos hechos y devuelve serie con su `reason`; en `"manual"` → `ValueError` explícito si se pidió paralelo en una ruta incompatible. |
| F4 | Contadores (`audited_rows`, `rows_rejected`, `rows_committed`…) de la `BulkCrud` fachada no verían los de los workers. | Sumar los del `ParallelLoadResult` a los de la instancia (patrón `_loader_audit` de `dump`). Test de conciliación. |
| F5 | Rechazos con `on_error="isolate"`: la posición pasa a ser relativa a la partición (columna `particion`). | Documentarlo. Sin cambio de formato del CSV (ya existe la columna). |
| F6 | Sin PK particionable (compuesta, no entera) → `HashPartitioner` en memoria. En INSERT con identity, el reparto por hash es correcto (conjuntos disjuntos), pero el orden de inserción cambia. | `reason` explícita; `partition_column` permite forzar la columna. |
| F7 | `"manual"` debe reproducir exactamente el comportamiento actual de `ParallelBulkLoader`, salvo la regla SQLite nueva (cambio intencionado: hoy da `database is locked`). | Tests de regresión actuales del loader sin cambios de aserciones (solo de construcción). |

### Riesgos técnicos

| # | Riesgo | Mitigación |
|---|---|---|
| T1 | **Recursión**: un worker con `parallel.mode != "off"` volvería a paralelizar. | `BulkOptions.for_worker()` fuerza `mode="off"`; test explícito. |
| T2 | **Estado mutable**: `BulkCrud` cambia `_update_via_staging = False` en ejecución (`crud.py:1093`, sin privilegio). | Las opciones son inmutables y la degradación sigue siendo estado privado de la instancia. Nunca se muta el paquete. |
| T3 | **Ciclo de imports** `crud` ↔ `parallel_loader`. | Import diferido en la ruta paralela de `BulkCrud` (cuenta como `lazy` en `gen_arquitectura_capas.py`). No cambian las flechas entre paquetes: el planificador va en `bulk/` y `dump → bulk` ya existe. Ejecutar el script y `test_architecture_import_rules.py`. |
| T4 | **Thread-safety de `insert_resolver`**: hoy no llega a los workers; con `BulkOptions` se compartiría una instancia entre hilos. | **Pendiente de verificar** que las estrategias de `InsertStrategyResolver` no guardan estado por ejecución. Si lo guardan: `ExecutionOptions.insert_resolver` pasa a ser una fábrica (`Callable[[], InsertStrategyResolver]`). |
| T5 | **LSP/ISP**: el constructor baja de 17 a 6 parámetros (ISP mejora). Verificado: ningún Protocol de `tests/unit/test_protocol_conformance.py` ni de `dump/` describe `BulkCrud` o `ParallelBulkLoader`. | Sin Protocols que actualizar; `mypy src tests/unit/test_protocol_conformance.py` en la puerta igualmente. |
| T6 | **Tamaño de la migración**: 245 + 106 construcciones en tests, 13 + 7 ficheros de docs, 3 scripts. | Script de migración puntual en el scratchpad basado en `ast` (localiza llamadas y kwargs), aplicado fichero a fichero con diff revisado; **sin sed global** (memoria del proyecto). Los tests que leen privados del loader (`loader._max_workers`, `_max_retries`, `_chunk_size`, `_commit_every_n_chunks`, `_disable_constraints`) se pasan a `loader.options`. |
| T7 | **Sync/async**: `AsyncDatabaseManager` no usa `BulkCrud`. | Sin impacto; verificado con grep (solo `dump` y `parallel_loader` construyen `BulkCrud` en `src`). |
| T8 | **Umbrales sin medir**: el umbral de filas y varias celdas de la tabla de reglas. | Celdas sin medir = serie. G8 con `/performance-audit-bulk` en el banco antes de cambiarlas. No se inventan números. |
| T9 | `DumpConfig` sigue plano y traduce a `BulkOptions`. | Un único punto de traducción (`_bulk_options`), con test que cubra todos los campos. |

### Riesgos de seguridad
- No cambia la parametrización SQL: el planificador no ejecuta SQL; `dump` sigue usando `MIN/MAX` con identificadores
  citados por `quote_identifier`/`quote_table`.
- Rutas de CSV: se mantienen `validate_optional_path` y la creación anticipada de `AuditManager` (PL-4), ahora en
  `AuditOptions.__post_init__`, antes de tocar la BD.
- `retry_on` e `insert_resolver` son callables del usuario: mismo nivel de confianza que hoy.
- Más conexiones concurrentes en `"auto"`: siempre acotadas por `pool_capacity` (sin regresión de agotamiento del pool).

### Simplificaciones posibles
1. **Fusionar `RetryOptions` en `ParallelOptions`** (los reintentos solo existen en la ruta paralela). Recomendado:
   mantenerlo como subpaquete `ParallelOptions.retry`, sin parámetro propio en los constructores (ya reflejado).
2. **Aplazar G4** (fachada en `BulkCrud`) si se quiere un 3.0.0 más pequeño: G1–G3 + G5 dan ya el planificador en el
   loader y en `dump`; G4 es aditivo y cabría en 3.1.0 sin romper nada.
3. **Aplazar G8** a 3.1.0: con celdas sin medir en serie, `"auto"` es conservador y correcto.
4. `DumpConfig` no se reempaqueta (decisión abajo): evita una segunda ruptura dentro de la misma MAJOR.

### Decisiones abiertas para el usuario
- D1: ¿Reempaquetar también `DumpConfig` en esta MAJOR? **Recomendación: no.** Ya es un objeto de configuración, sus
  campos son de dominio del volcado y la ruptura no aporta reducción real de parámetros.
- D2: ¿G4 en 3.0.0 o en 3.1.0? **Recomendación: 3.0.0**, para que la primera versión con paquetes ya traiga el uso
  previsto por la solicitud.
- D3: Nombres sin prefijo (`AuditOptions(csv_path=...)`) frente a conservar los de 2.x (`audit_csv_path`).
  **Recomendación: sin prefijo**, con la tabla de equivalencias en la guía de migración.

### Estrategia de pruebas
- Unitarias SQLite en memoria: validación de cada paquete (mismos casos de error que hoy en los constructores);
  planificador con tabla de casos parametrizada por motor y operación (puro, sin BD); fachada paralela de `BulkCrud`
  sobre SQLite (que el plan dé 1 escritor y `reason` correcta) y con engine mock para workers > 1; recursión T1;
  conciliación de contadores F4; `ParallelLoadError` F2.
- Regresión: toda la suite actual migrada, sin cambiar aserciones de comportamiento.
- Integración opcional (`pytest.mark.integration`, banco): una carga `"auto"` por motor.
- Puerta: `ruff check`, `ruff format`, `mypy src tests/unit/test_protocol_conformance.py`, `pytest` (también en shell
  limpio sin URLs del banco), `zensical build --strict`, `scripts/gen_arquitectura_capas.py`.

### Veredicto: `GO_CONDICIONAL`

Condiciones (finitas):
1. Respuesta del usuario a D1, D2 y D3.
2. Verificar T4 (estado de `InsertStrategyResolver`) antes de G2.
3. `"auto"` solo usa celdas medidas; las demás, serie (T8). Ningún umbral sin medir entra como valor por defecto
   distinto de «serie».
4. `mode="off"` como valor por defecto de `BulkCrud` y `"manual"` en `ParallelBulkLoader` (sin cambio de
   comportamiento salvo la regla SQLite, que se documenta en el CHANGELOG).
5. Guía `docs/guides/api_3_0_migration.md` y sección de migración en el CHANGELOG en el mismo release.
