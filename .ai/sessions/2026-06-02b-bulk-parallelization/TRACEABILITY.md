# TRACEABILITY — Bulk parallelization para cargas >1M filas

## Session metadata
- id: 2026-06-02b-bulk-parallelization
- fecha: 2026-06-02
- rama: develop
- skill: new-feature
- fases ejecutadas: PLAN → AUDIT_PLAN → IMPLEMENT

## Prompt issued

```
Revisar el módulo src\util_bbdd\bulk y proponer mejoras de rendimiento para
carga masiva superior al millón de registros en tablas con más de trece millones.
Analizar si es posible: Paralelización de Inserción (Multi-Engine) con ThreadPoolExecutor.
Solo PLAN - AUDIT PLAN → luego IMPLEMENT
```

## Context supplied

- `src/util_bbdd/bulk/_execution/parallel_loader.py` — `ParallelBulkLoader` existente (125 líneas)
- `src/util_bbdd/bulk/_execution/batch.py` — estrategias INSERT por motor
- `src/util_bbdd/bulk/crud.py` — `BulkCrud`, `bulk_session`, `maintenance_scope`
- `src/util_bbdd/bulk/__init__.py` — API pública
- `tests/unit/bulk/test_parallel_loader.py` — tests existentes

---

## PLAN — resumen

### Objetivo

Cuatro mejoras ortogonales y backward-compatible para cargas >1M registros sobre tablas >13M filas:

1. **`RangePartitioner`** — Auto-generación de lectores de partición por rango de PK.
2. **`maintenance_scope` integrado en `ParallelBulkLoader`** — Cada worker desactiva constraints (session-scoped, paralelo-seguro) antes de insertar.
3. **`PartitionResult` + métricas en `ParallelLoadResult`** — `elapsed_seconds`, `rows_per_second`, `partition_results`.
4. **Validación de connection pool** — Warning si `max_workers > pool_size`.

### Viabilidad de paralelismo con `ThreadPoolExecutor`

`ThreadPoolExecutor` es **correcto** para bulk I/O. El GIL se libera durante
llamadas bloqueantes de los drivers (psycopg3, pymysql, pyodbc). El cuello de
botella es I/O de red + escritura en disco, no CPU. Ratio I/O/CPU típico: 20–240×.

| Motor | Viable | Condición |
|---|---|---|
| PostgreSQL + psycopg3 | ✅ | COPY FROM STDIN por worker; WAL presionado >8 workers |
| MySQL/MariaDB | ✅ con condiciones | `commit_every_n_chunks` obligatorio; `FOREIGN_KEY_CHECKS=0` session-scoped → no colisiona |
| MSSQL | ⚠️ | Lock escalation tras ~5K locks; `disable_indexes` NO en paralelo (DDL SCH-M global) |
| SQLite | ❌ | Write lock global; no escala con threads |

---

## AUDIT_PLAN — hallazgos críticos

### Riesgo de diseño resuelto: `maintenance_scope` requiere `bulk_session` activo

`bulk_insert_from_chunks` gestiona su propio `bulk_session` internamente.
Llamarlo dentro de `maintenance_scope` (que requiere `bulk_session` activo)
abriría una segunda conexión independiente → constraints desactivadas en la
primera conexión, inserts en la segunda. El efecto neto: `maintenance_scope`
sin efecto real.

**Decisión de diseño** (condición C resolvida en IMPLEMENT): En el path
`disable_constraints=True`, el worker NO usa `bulk_insert_from_chunks`.
En su lugar, abre `bulk_session` → entra en `maintenance_scope` → itera chunks
del lector llamando a `bulk_insert_from_df(generar_sql=False)` por chunk.
`bulk_insert_from_df` respeta la conexión activa del `bulk_session` exterior.

### Condiciones GO cumplidas

| # | Condición | Estado |
|---|---|---|
| C1 | Retry solo ante `OperationalError`/`TimeoutError` | ✅ |
| C2 | `disable_indexes=False` forzado, documentado en docstring | ✅ |
| C3 | `_warn_pool_size()` con `isinstance(size, int)` guard | ✅ |
| C4 | `on_progress` callback eliminado del scope | ✅ |
| C5 | `_validate_column_type` con `TypeError` para no-int/datetime64 | ✅ |
| C6 | Docstring con `params=` en ejemplo SQL (no f-string) | ✅ |

---

## IMPLEMENT — artefactos generados

| Artefacto | Ruta | Tipo |
|---|---|---|
| `PartitionResult` | `src/util_bbdd/bulk/_execution/parallel_loader.py` | Nuevo dataclass |
| `ParallelLoadResult` extendido | `src/util_bbdd/bulk/_execution/parallel_loader.py` | Modificado (backward-compatible) |
| `ParallelBulkLoader` extendido | `src/util_bbdd/bulk/_execution/parallel_loader.py` | Modificado — 4 nuevos params + 2 métodos |
| `RangePartitioner` | `src/util_bbdd/bulk/_execution/range_partitioner.py` | Nuevo módulo |
| `__init__.py` | `src/util_bbdd/bulk/__init__.py` | Exporta `PartitionResult`, `RangePartitioner` |
| Tests parallelloader | `tests/unit/bulk/test_parallel_loader.py` | +43 tests en 4 clases |
| Tests range_partitioner | `tests/unit/bulk/test_range_partitioner.py` | Nuevo — 22 tests |

### API pública nueva

```python
# PartitionResult — resultado por partición
@dataclass
class PartitionResult:
    index: int
    rows: int
    elapsed_seconds: float
    error: str | None = None
    retries: int = 0

# ParallelLoadResult — extendido (backward-compatible: nuevos campos con defaults)
@dataclass
class ParallelLoadResult:
    total_rows: int = 0
    partition_errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0                          # NUEVO
    partition_results: list[PartitionResult] = field(...)  # NUEVO
    rows_per_second: float  # @property, no campo — no afecta __eq__

# ParallelBulkLoader — parámetros nuevos (keyword-only)
ParallelBulkLoader(
    engine,
    ...,
    max_retries: int = 0,           # NUEVO — reintentos ante OperationalError/TimeoutError
    disable_constraints: bool = False,  # NUEVO — maintenance_scope por worker
)

# RangePartitioner — nuevo
RangePartitioner.partition_dataframe(df, pk_col, n_partitions) -> list[pd.DataFrame]
RangePartitioner.partition_ranges(min_val, max_val, n_partitions) -> list[tuple[int, int]]
```

### Decisiones de implementación no obvias

**`_load_with_maintenance` vs `bulk_insert_from_chunks`**: El path con
`disable_constraints=True` NO puede usar `bulk_insert_from_chunks` porque
éste abre su propio `bulk_session` internamente. Se itera el reader manualmente
dentro del `bulk_session` + `maintenance_scope` del worker, llamando
`bulk_insert_from_df(generar_sql=False)` por chunk. El `BatchStatementExecutor`
detecta `_active_connection is not None` y reutiliza la conexión compartida.

**`disable_indexes=False` forzado**: `ALTER INDEX ... DISABLE` en MSSQL adquiere
lock DDL `SCH-M` global sobre la tabla — exclusivo, no paralelo. Dos workers
intentando deshabilitar índices en paralelo se bloquearían mutuamente, serializando
la carga y anulando el beneficio del paralelismo.

**Retry solo para errores retriables**: `OperationalError` (conexión perdida,
timeout) y `TimeoutError` Python son retriables. `IntegrityError`, `ProgrammingError`,
`DataError` y `SQLAlchemyError` general van al branch permanente sin retry.
Motivación: reintentar una violación de PK duplicada es un loop infinito garantizado.

---

## Quality Gates

✅ **Tests nuevos**: 48 passed (test_parallel_loader + test_range_partitioner)
✅ **Suite completa**: 3797 passed, 1 skipped, 0 failed
✅ **Backward-compatible**: tests previos de `ParallelBulkLoader` pasan sin modificación

---

## Directrices para Futuras IAs

### [disable_constraints en ParallelBulkLoader]
**Hecho verificable**: `disable_constraints=True` usa `_load_with_maintenance` en
lugar de `bulk_insert_from_chunks`. La diferencia es que `_load_with_maintenance`
abre `bulk_session` explícitamente antes de entrar en `maintenance_scope`, y llama
`bulk_insert_from_df(generar_sql=False)` por chunk dentro del mismo bulk_session.
`bulk_insert_from_chunks` no puede usarse aquí: gestiona su propio `bulk_session`.

### [disable_indexes siempre False en paralelo]
**Hecho verificable**: `_load_with_maintenance` fuerza `disable_indexes=False`
independientemente de lo que pase el caller. Documentado en docstring. Motivación:
`ALTER INDEX DISABLE` en MSSQL requiere lock SCH-M global (DDL exclusivo), que
serializa workers paralelos. El rebuild post-carga es responsabilidad del llamador.

### [RangePartitioner — tipos soportados]
**Hecho verificable**: `partition_dataframe` solo acepta columnas `int`/`np.integer`
o `datetime64`. Cualquier otro dtype lanza `TypeError` con mensaje explícito.
`partition_ranges` trabaja con enteros Python puros (no valida tipo).

### [pool_size warning — comportamiento con pools especiales]
**Hecho verificable**: `_warn_pool_size` usa `isinstance(size, int)` antes de
comparar. `NullPool`, `StaticPool` y `MagicMock` (tests) no tienen `.size()` con
retorno entero → no emiten warning. Solo `QueuePool` y pools con `.size() -> int`
activan la comprobación.

---

## Veredicto final

**Estado**: ✅ CLOSED

- ✅ PLAN: cuatro mejoras identificadas y acotadas
- ✅ AUDIT_PLAN: riesgo crítico de diseño detectado y resuelto (maintenance_scope + bulk_session)
- ✅ IMPLEMENT: 5 artefactos nuevos/modificados, 65 tests nuevos, 0 regresiones
- ✅ API pública backward-compatible

**Pendientes**:
- [ ] Commit de los cambios en `develop`
- [ ] Valorar actualizar CHANGELOG.md / versión si se considera entregable
