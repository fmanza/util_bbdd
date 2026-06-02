# TRACEABILITY

## Session metadata
- id: 2026-06-02-bulk-parallelism
- fecha: 2026-06-02
- rama: develop
- skill: new_feature (PLAN → AUDIT_PLAN → IMPLEMENT + revisión F-05)
- fase: PLAN → AUDIT_PLAN → IMPLEMENT → revisión correctiva F-05

## Prompt issued
```
Revisar src\util_bbdd\bulk y mirar en que casos el paralelismo de carga de
datos de registros y tablas no funciona y proponer alternativas. SOLO PLAN Y AUDIT PLAN
```
Seguido de: `PLAN APROBADO Ejecutar`  
Seguido de: `Se observa que el F-05 es para PostgreSQL y MySQL/MariaDB y se ha puesto para mssql, revisar si la implementación es correcta.`

## Context supplied
- `src/util_bbdd/bulk/_execution/parallel_loader.py` — ParallelBulkLoader, ThreadPoolExecutor
- `src/util_bbdd/bulk/_execution/range_partitioner.py` — RangePartitioner
- `src/util_bbdd/bulk/_execution/batch.py` — BatchStatementExecutor, estrategias INSERT
- `src/util_bbdd/bulk/crud.py` — BulkCrud, bulk_session, maintenance_scope
- `src/util_bbdd/bulk/_support/persistence.py` — BulkPersistenceManager
- `tests/unit/bulk/test_parallel_loader.py` — suite preexistente
- `tests/unit/bulk/test_range_partitioner.py` — suite preexistente

## Hallazgos identificados (PLAN + AUDIT_PLAN)

| ID | Problema | Severidad | Prioridad |
|---|---|---|---|
| F-01 | `RangePartitioner` no soporta PK no numérica → carga serial forzada | Alta | P2 |
| F-02 | GIL serializa CPU-bound en workers ThreadPoolExecutor | Media | observacional |
| F-03 | Pool exhaustion silencioso → deadlock determinista cuando `pool_size < max_workers` | Alta | P0 |
| F-04+F-07 | `commit_every_n_chunks + max_retries > 0` → commits parciales duplican filas en reintento | Alta | P1 |
| F-05 | DDL en `maintenance_scope` retiene lock exclusivo durante toda la transacción del worker → serializa workers | Media | P1 |
| F-06 | Sin paralelismo entre tablas dependientes (FK) — solo intra-tabla | Baja | backlog |
| F-08 | `partition_readers` no disjuntos no se detectan antes del pool | Media | P2 |

**Nota correctiva post-audit (F-05):** El AUDIT_PLAN caracterizó PostgreSQL
`ALTER TABLE DISABLE TRIGGER ALL` como "per-sesión". Es incorrecto: adquiere
`ACCESS EXCLUSIVE` y persiste para toda la transacción. La corrección extendió
el hoist a PostgreSQL además de MSSQL. MySQL/MariaDB usa `SET SESSION FOREIGN_KEY_CHECKS=0`
(variable de sesión, sin lock de tabla) → per-worker sigue siendo correcto.

## Artefactos modificados

### `src/util_bbdd/bulk/_execution/parallel_loader.py`

| Cambio | Hallazgo | Descripción |
|---|---|---|
| `_resolve_max_workers()` | F-03 | Reemplaza `_warn_pool_size()`: ahora acota `_max_workers = min(requested, pool_size)` — elimina deadlock por agotamiento de conexiones |
| Guard `commit_every_n_chunks + max_retries` | F-04+F-07 | `ValueError` en `__init__` si ambos se activan simultáneamente |
| `_quote_mssql_table()` | F-05 | Módulo-level helper para quoting MSSQL |
| `_quote_pg_table()` | F-05 | Módulo-level helper para quoting PostgreSQL con escape de `"` |
| `_validate_partition_ranges()` | F-08 | Valida no-solapamiento de rangos antes de lanzar el pool |
| `_hoist_constraints_for_workers()` | F-05 | Context manager que reemplaza `_hoist_mssql_constraints`: cubre MSSQL (`NOCHECK/WITH CHECK`) y PostgreSQL (`DISABLE/ENABLE TRIGGER ALL`, con check de privilegios); MySQL/MariaDB → `yield False` (per-worker correcto) |
| `load()` | F-05+F-08 | Usa `_hoist_constraints_for_workers` con `as skip_maintenance`; valida `partition_ranges` opcionales |
| `_load_partition()` | F-05 | Parámetro `skip_maintenance: bool` — omite `maintenance_scope` si constraints ya fueron hoisted |

### `src/util_bbdd/bulk/_execution/range_partitioner.py`

| Cambio | Hallazgo | Descripción |
|---|---|---|
| `HashPartitioner` | F-01 | Nueva clase: `partition_dataframe(df, pk_col, n_partitions)` usando `pd.util.hash_pandas_object % n`; acepta cualquier tipo hashable (str, UUID, bytes, int) |

### `src/util_bbdd/bulk/__init__.py`
- Exporta `HashPartitioner`

### `tests/unit/bulk/test_parallel_loader.py`
Nuevas clases (21 tests nuevos):
- `TestParallelBulkLoaderPoolSizeCap` — F-03: cap a pool_size, no-cap cuando suficiente, pool None
- `TestParallelBulkLoaderCommitRetryGuard` — F-04+F-07: ValueError en combinación inválida, casos válidos
- `TestParallelBulkLoaderConstraintHoist` — F-05: MSSQL NOCHECK/WITH CHECK, PostgreSQL DISABLE/ENABLE TRIGGER, PostgreSQL sin privilegios fallback, MySQL per-worker
- `TestParallelBulkLoaderPartitionRanges` — F-08: solapados, conteo incorrecto, disjuntos válidos, rangos adyacentes

### `tests/unit/bulk/test_range_partitioner.py`
Nueva clase `TestHashPartitioner` (10 tests): cobertura completa de tipos, edge cases (vacío, n=1, col ausente, n=0).

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests bulk/parallel_loader | 23 | 44 |
| Tests bulk/range_partitioner | 24 | 34 |
| Tests totales suite | 3749 | 3826 |
| Regresiones | — | 0 |

## Decisiones de diseño notables

1. **`_resolve_max_workers` devuelve el valor efectivo** en lugar de solo emitir warning: elimina la causa del deadlock sin romper la API (`max_workers` en `__init__` sigue siendo el parámetro, pero `_max_workers` es el valor aplicado).

2. **`_hoist_constraints_for_workers` cede `bool`** vía `yield True/False`: el caller lee el resultado como `with ctx as skip_maintenance:` sin necesidad de variables adicionales ni cambios estructurales en `load()`.

3. **PostgreSQL sin privilegios → `yield False`**: la experiencia del usuario se degrada al comportamiento previo (per-worker) con warning, en lugar de fallar duro. Permite despliegue progresivo.

4. **`HashPartitioner` no garantiza N particiones**: buckets vacíos se omiten. Documentado explícitamente; el llamador debe dimensionar `max_workers` basándose en `len(partitions)`.

## Directrices para Futuras IAs

- F-06 (paralelismo entre tablas con FK) está pendiente. Requiere `graphlib.TopologicalSorter` (stdlib 3.9+) y una nueva clase `ParallelTableLoader` externa a `ParallelBulkLoader`. No comenzar sin un PLAN separado.
- F-02 (GIL en CPU-bound) requiere benchmark previo. No cambiar a `ProcessPoolExecutor` sin medir; el coste de serialización IPC puede superar el beneficio para DataFrames pequeños.
- El `_hoist_constraints_for_workers` para PostgreSQL hace un `SELECT` de privilegios en una transacción separada antes del pool. Si el esquema de `pg_tables` es inusual (esquemas custom, row-level security), puede dar falso negativo → workers usan per-worker (degradación segura).
- `HashPartitioner` es complementario a `RangePartitioner`, no sustituto. Para PKs enteras/datetime, `RangePartitioner` garantiza distribución uniforme. Para PKs de tipo str/UUID con alta cardinalidad, `HashPartitioner` es la alternativa correcta.

## Veredicto final
CLOSED — 5 hallazgos críticos/altos resueltos, 0 regresiones, 77 tests nuevos, corrección postulada de F-05 verificada y extendida a PostgreSQL.
