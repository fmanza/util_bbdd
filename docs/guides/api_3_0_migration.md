# Migración a la API 3.0

## 1. Objetivo

Adaptar el código que usa `util_bbdd` 2.x a 3.0.0. En **3.0.0** `BulkCrud` y `ParallelBulkLoader` ya no aceptan sus
parámetros sueltos (16 y 17): las opciones llegan en **paquetes** inmutables. Un parámetro antiguo da
`TypeError: BulkCrud.__init__() got an unexpected keyword argument 'chunk_size'`. No hay capa de compatibilidad.

El resto de la API pública no cambia: los métodos de `BulkCrud` y `ParallelBulkLoader`, sus resultados, `DumpConfig`
(sus campos siguen siendo planos) y el resto de puntos de entrada.

## 2. Qué cambia

- `BulkCrud(engine, *, batch, audit, rejects, execution, parallel)` y `ParallelBulkLoader` con los mismos paquetes.
- Los paquetes (`BatchOptions`, `AuditOptions`, `RejectOptions`, `ExecutionOptions`, `ParallelOptions`, `RetryOptions`)
  se importan de `util_bbdd.bulk`. Validan sus valores al construirse: un valor no válido falla al crear el paquete.
- **Nuevo**: carga paralela desde `BulkCrud` (`parallel=ParallelOptions(...)`) y planificador de hilos
  (`ParallelPlanner`, `mode="auto"`). Ver [CRUD masivo](../api/bulk_crud.md#carga-paralela-desde-bulkcrud-v300).
- **Nuevo**: `DumpConfig(parallel_pk_ranges="auto")`.
- **Cambio de comportamiento**: `ParallelBulkLoader` con SQLite usa un solo hilo (con un WARNING si se pidieron más).
  Hasta 2.x, varios hilos daban `database is locked`.
- **Corregido**: los workers de `ParallelBulkLoader` reciben ahora `insert_resolver`, `update_via_staging` y
  `prefetch_blocks`, que hasta 2.x se ignoraban sin aviso. Si construías el loader con `update_via_staging=False` en
  PostgreSQL, ahora sí se respeta y el `update()` va en un hilo (fila a fila en paralelo es más lento).

## 3. Equivalencias

### `BulkCrud`

| 2.x | 3.0 |
|---|---|
| `chunk_size=N` | `batch=BatchOptions(chunk_size=N)` |
| `commit_every_n_chunks=N` | `batch=BatchOptions(commit_every_n_chunks=N)` |
| `prefetch_blocks=True` | `batch=BatchOptions(prefetch_blocks=True)` |
| `audit_csv_path=p` | `audit=AuditOptions(csv_path=p)` |
| `audit_strict=True` | `audit=AuditOptions(strict=True)` |
| `audit_sink=s` | `audit=AuditOptions(sink=s)` |
| `audit_run_id=r` | `audit=AuditOptions(run_id=r)` |
| `warn_if_audit_disabled=False` | `audit=AuditOptions(warn_if_disabled=False)` |
| `on_error="isolate"` | `rejects=RejectOptions(on_error="isolate", csv_path=...)` |
| `rejects_csv_path=p` | `rejects=RejectOptions(csv_path=p, ...)` |
| `max_rejects=N` | `rejects=RejectOptions(max_rejects=N, ...)` |
| `enable_fast_executemany=False` | `execution=ExecutionOptions(fast_executemany=False)` |
| `insert_resolver=r` | `execution=ExecutionOptions(insert_resolver=r)` |
| `update_via_staging=False` | `execution=ExecutionOptions(update_via_staging=False)` |
| `strip_strings=False` | `execution=ExecutionOptions(strip_strings=False)` |
| `reflect_foreign_keys=False` | `execution=ExecutionOptions(reflect_foreign_keys=False)` |

### `ParallelBulkLoader`

Los mismos que `BulkCrud`, más:

| 2.x | 3.0 |
|---|---|
| `max_workers=N` | `parallel=ParallelOptions(max_workers=N)` |
| `disable_constraints=True` | `parallel=ParallelOptions(disable_constraints=True)` |
| `max_retries=N` | `parallel=ParallelOptions(retry=RetryOptions(max_retries=N))` |
| `retry_backoff=(b, m)` | `parallel=ParallelOptions(retry=RetryOptions(backoff=(b, m)))` |
| `retry_on=f` | `parallel=ParallelOptions(retry=RetryOptions(retry_on=f))` |

### Mensajes de error

| 2.x | 3.0 |
|---|---|
| `audit_csv_path debe ser una ruta (str o Path)…` | `audit.csv_path debe ser una ruta (str o Path)…` |
| `rejects_csv_path debe ser una ruta (str o Path)…` | `rejects.csv_path debe ser una ruta (str o Path)…` |
| `retry_backoff debe ser (base, máximo)…` | `backoff debe ser (base, máximo)…` |

El resto de mensajes (`chunk_size debe ser un entero ≥ 1`, `commit_every_n_chunks debe ser None o un entero ≥ 1`,
`max_workers…`, `max_retries…`, `on_error…`) no cambian.

## 4. Ejemplo

Antes (2.x):

```python
from util_bbdd.bulk import BulkCrud, ParallelBulkLoader

crud = BulkCrud(engine, chunk_size=5_000, commit_every_n_chunks=20, audit_csv_path="logs/audit.csv")
loader = ParallelBulkLoader(engine, max_workers=4, max_retries=2, disable_constraints=True)
```

Después (3.0):

```python
from util_bbdd.bulk import (
    AuditOptions,
    BatchOptions,
    BulkCrud,
    ParallelBulkLoader,
    ParallelOptions,
    RetryOptions,
)

batch = BatchOptions(chunk_size=5_000, commit_every_n_chunks=20)
audit = AuditOptions(csv_path="logs/audit.csv")
crud = BulkCrud(engine, batch=batch, audit=audit)
loader = ParallelBulkLoader(
    engine,
    parallel=ParallelOptions(max_workers=4, disable_constraints=True, retry=RetryOptions(max_retries=2)),
)
```

Los paquetes se pueden reutilizar entre instancias: `BulkCrud(engine, **crud.options.as_kwargs())` crea otra con las
mismas opciones.

## 5. Accesos a atributos privados

Si algún código leía atributos privados de `ParallelBulkLoader` (`loader._chunk_size`, `_max_retries`,
`_disable_constraints`, `_commit_every_n_chunks`), en 3.0 ya no existen: usa `loader.options` (p. ej.
`loader.options.parallel.retry.max_retries`). `BulkCrud.options` da lo mismo en `BulkCrud`.
