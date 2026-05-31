# TRACEABILITY

## Session metadata
- id: 2026-05-31-dump-performance
- fecha: 2026-05-31
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE

## Prompt issued

```
Saber como src\util_bbdd\dum lee los datos de una tabla se los pasa a un dataframe
y estos al bulk, teniendo en cuenta que los tiempos de respuesta actuales no son muy buenos.
Analiza los cuellos de botella actuales, propón mejoras, PLAN y AUDIT PLAN.
Implementar todas las propuestas.
```

## Context supplied
- `src/util_bbdd/dump/orchestrator.py` — orquestador dump completo
- `src/util_bbdd/bulk/crud.py` — `BulkCrud`, `bulk_crud`, `reflect_table`, `bulk_insert_from_df`
- `src/util_bbdd/bulk/_execution/batch.py` — `BatchStatementExecutor.execute()`
- `src/util_bbdd/dump/_models.py` — `DumpConfig`, `TableDumpResult`, `DumpResult`
- `tests/unit/test_bulk_internal_helpers.py`
- `tests/unit/test_bulk_crud_helpers.py`
- `tests/unit/dump/test_orchestrator.py`
- Suite verde previa: 3547 passed, 1 skipped

## Análisis de cuellos de botella

### Bottleneck 1 — `reflect_table` sin caché (hot path)
Por cada chunk de datos, `bulk_insert_from_df` llamaba a `reflect_table` que instanciaba
`MetaData()` + `Table(..., autoload_with=engine)` → 1 round-trip SQL de introspección
por chunk. Con `chunk_size=5000` y tabla de 500K filas → 100 llamadas de introspección
innecesarias a la misma tabla.

### Bottleneck 2 — nueva transacción por chunk
`BatchStatementExecutor.execute()` abría `engine.begin()` → commit → close por cada
invocación. N chunks = N transacciones = N ciclos de conexión TCP (especialmente costoso
en Snowflake, Oracle Remote y SQL Server Azure).

### Bottleneck 3 — `COUNT(*)` obligatorio sobre tablas grandes
`_process_table` ejecutaba `COUNT(*)` origen + `COUNT(*)` destino incondicionalmente,
incluso en tablas de millones de filas sin estadísticas actualizadas (Snowflake,
Oracle). El coste podía superar el del propio volcado.

## AI output summary

### PLAN
- **Propuesta A** (`reflect_table` cache): Identity Map `_table_cache: dict[str, Table]` en
  `BulkCrud.__init__`; `reflect_table` devuelve objeto cacheado en llamadas sucesivas.
  Impacto: elimina N-1 round-trips de introspección por tabla.
- **Propuesta B** (`bulk_session` + conexión inyectada): nuevo `@contextmanager bulk_session()`
  en `BulkCrud` que abre 1 única transacción para todo el loop de chunks. `BatchStatementExecutor`
  gana `_active_connection: Any | None`; si está inyectado, reutiliza la conexión en lugar de
  abrir `engine.begin()` por lote. Semántica cambia: partial-commit → table-atomic.
- **Propuesta C** (`collect_row_counts`): nuevo campo `collect_row_counts: bool = True` en
  `DumpConfig`; cuando `False`, omite todos los `COUNT(*)` y devuelve `-1` como sentinel.
  `DumpReporter` ya manejaba `-1` con guarda `if res.source_rows >= 0`.

### AUDIT_PLAN veredictos
- **Propuesta A**: APROBADO — sin cambio de API, aislamiento por instancia garantizado
- **Propuesta B**: APROBADO CON CONDICIONES — semántica de rollback documentada; inner try/except
  por chunk eliminado; outer except cubre errores de lectura origen con prefijo "Error leyendo origen:"
- **Propuesta C**: APROBADO CON CONDICIONES — verificado que `DumpReporter` ya maneja `-1`;
  campo con default `True` para retrocompatibilidad total

### IMPLEMENT

#### `src/util_bbdd/bulk/crud.py`
- Import: `Iterator` añadido a `collections.abc`; `from contextlib import contextmanager` añadido
- `__init__`: `self._table_cache: dict[str, Table] = {}` tras `self.engine = validate_engine(engine)`
- `reflect_table()`: Identity Map — comprueba `_table_cache` antes de `MetaData()+autoload_with`;
  almacena resultado en caché tras primera reflexión
- Nuevo método `bulk_session(*, atomic: bool = True) -> Iterator[None]`: abre `engine.begin()`,
  inyecta la conexión en `_batch_statement_executor._active_connection`, limpia en `finally`.
  Con `atomic=False`, yield puro (comportamiento legacy).

#### `src/util_bbdd/bulk/_execution/batch.py`
- `BatchStatementExecutor.__init__`: `self._active_connection: Any | None = None`
- `execute()`: si `_active_connection is not None`, llama `_execute_on_connection` con la conexión
  inyectada; si no, abre `with self._engine.begin()` (legacy)
- Nuevo método `_execute_on_connection(connection, records, stmt)`: extrae la lógica del loop de
  batches para reutilización

#### `src/util_bbdd/dump/_models.py`
- `DumpConfig`: nuevo campo `collect_row_counts: bool = True` tras `bulk_audit_path`
- Docstring: entrada para `collect_row_counts` con justificación (Snowflake, Oracle, tablas grandes)

#### `src/util_bbdd/dump/orchestrator.py`
- Import: `from util_bbdd.bulk import BulkCrud, bulk_crud` (añadido `BulkCrud`)
- Import: `from ._protocols import BulkInserter` eliminado (ya no usado)
- `_process_table` ruta skipped: `COUNT(*)` condicionado a `cfg.collect_row_counts`
- `_process_table` ruta principal:
  - `COUNT(*)` origen y destino condicionados a `cfg.collect_row_counts`
  - `crud: BulkCrud` (antes `crud: BulkInserter`)
  - Loop de chunks envuelto en `with crud.bulk_session()`
  - Inner `try/except` por chunk eliminado; outer `except` cubre errores de lectura origen

### Tests añadidos (9 nuevos)

| Test | Fichero | Qué verifica |
|---|---|---|
| `test_reflect_table_caches_result` | `test_bulk_internal_helpers.py` | Segunda llamada devuelve mismo objeto |
| `test_reflect_table_cache_isolated_per_instance` | `test_bulk_internal_helpers.py` | Caché no compartido entre instancias |
| `test_batch_executor_uses_injected_connection` | `test_bulk_internal_helpers.py` | `engine.begin()` no llamado si `_active_connection` inyectado |
| `test_bulk_session_reuses_single_connection` | `test_bulk_crud_helpers.py` | `engine.begin()` llamado exactamente 1× para N chunks |
| `test_bulk_session_resets_active_connection_on_exit` | `test_bulk_crud_helpers.py` | `_active_connection` vuelve a `None` al salir del CM |
| `test_bulk_session_atomic_false_does_not_inject_connection` | `test_bulk_crud_helpers.py` | `atomic=False` preserva comportamiento legacy |
| `test_dump_config_collect_row_counts_defaults_true` | `test_orchestrator.py` | Default `True` en `DumpConfig` |
| `test_collect_row_counts_false_returns_minus_one` | `test_orchestrator.py` | `_safe_count` no llamado; resultados `-1` |
| `test_process_table_calls_bulk_session` | `test_orchestrator.py` | `bulk_session()` invocado en procesado de tabla |

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| BulkCrud | `src/util_bbdd/bulk/crud.py` | modificado |
| BatchStatementExecutor | `src/util_bbdd/bulk/_execution/batch.py` | modificado |
| DumpConfig | `src/util_bbdd/dump/_models.py` | modificado |
| DumpOrchestrator | `src/util_bbdd/dump/orchestrator.py` | modificado |
| Tests bulk internos | `tests/unit/test_bulk_internal_helpers.py` | modificado (+3 tests) |
| Tests bulk crud | `tests/unit/test_bulk_crud_helpers.py` | modificado (+3 tests) |
| Tests orchestrator | `tests/unit/dump/test_orchestrator.py` | modificado (+3 tests, nueva clase) |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests totales | 3547 | 3556 |
| Tests nuevos sesión | — | +9 |
| ruff | ✅ | ✅ |
| mypy | ✅ 330 source files | ✅ 330 source files |
| pytest | ✅ 3547 passed, 1 skipped | ✅ 3556 passed, 1 skipped |

## Directrices para Futuras IAs

- **[bulk/BulkCrud._table_cache]**: Identity Map por instancia. Si se crea una nueva instancia de
  `BulkCrud` por tabla (fuera del loop), el caché no aporta nada. La ganancia es cuando se reutiliza
  la misma instancia para varios chunks de la misma tabla (patrón del `DumpOrchestrator`).
- **[bulk/bulk_session semántica]**: Con `atomic=True` (default), un error en cualquier chunk hace
  rollback de TODA la tabla. Si el usuario necesita commits parciales (resiliencia por chunk),
  debe usar `atomic=False`. El comportamiento pre-sesión (partial-commit) era el de `atomic=False`.
- **[dump/collect_row_counts]**: `-1` es el sentinel para "no contado". `DumpReporter` ya lo maneja
  con `if res.source_rows >= 0 else "—"`. No añadir lógica especial en nuevos reporters.
- **[dump/orchestrator import]**: `BulkInserter` ya no se importa en `orchestrator.py`. La anotación
  de tipo es `crud: BulkCrud`. `BulkInserter` sigue existiendo en `_protocols.py` para otros usos.
- **[patrón establecido]**: El loop de chunks en `_process_table` siempre debe estar dentro de
  `with crud.bulk_session()` para garantizar atomicidad por tabla y reutilización de conexión.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Ninguno
