# TRACEABILITY

## Session metadata
- id: 2026-10-01n-feat-on-error-isolate
- fecha: 2026-10-01
- rama: develop (base `879c3ad`)
- skill: new-feature (PLAN + AUDIT_PLAN aprobados con D-1 `max_rejects=None` → IMPLEMENT → AUDIT_CODE → VERSION)

## Prompt issued
«Opciones nuevas» → PLAN/AUDIT_PLAN (`PLAN_AUDIT_PLAN.md`) → «Si» (las dos opciones, `max_rejects=None` por defecto).

## AI output summary
- `bulk/_support/rejects.py` (nuevo): `RejectsWriter` (CSV UTF-8 con tabuladores, cabecera si es nuevo, celdas con
  prefijo de fórmula neutralizadas con `'`, error = clase + primera línea del error del driver) e `Isolator`
  (`run_records`, `run_frame` para el DELETE, `run_columns` para `SqlColumns`, que solo pasa a registros si el bloque
  falla; bisección con SAVEPOINT; solo `IntegrityError`/`DataError`; `max_rejects`). `_savepoint` emite `BEGIN` en
  SQLite (pysqlite) si la transacción no ha empezado.
- `executors.py`: atributo `isolator` en los dos ejecutores; `first_row` en `execute`/`execute_columns`; `_send` extrae el
  envío de un lote de registros. Con `isolator=None` el camino es el de antes.
- `crud.py`: `BulkCrud(on_error="raise", rejects_csv_path=None, max_rejects=None)` con validación; `__isolating` fija el
  aislador en ambos ejecutores durante una operación (un `*_from_chunks` es una operación); `__first_row`; auditoría con
  filas aplicadas; `rows_rejected` (acumulado); los valores del CSV sin los alias de PK del UPDATE.
- Tests: `tests/unit/bulk/test_on_error_isolate.py` (21) e integración (4 tests, 6 motores; `pymssql` aparte):
  INSERT con PK duplicada (con y sin cadencia), UPDATE demasiado largo con y sin staging (PG, MySQL, MariaDB), DELETE con
  FK, y valor demasiado largo **no aislado** en Oracle y SQL Server.
- R-9 (`bench_isolate.py`, `bench_isolate.log`; INSERT 1M, 2 repeticiones): sin filas malas 1,00–1,02× (Oracle 1,00× y
  1,27×: ruido de una repetición); 10 filas malas 1,13–1,23×, PostgreSQL 1,65× (lotes de 20 000 con COPY). Peor que el
  prototipo S-2 (≤ 1,16×, executemany con lotes de 5000) en PostgreSQL; documentado.
- Docs: `docs/api/bulk_crud.md` (parámetros, propiedad, límites), `docs/functional/bulk_operations.md`,
  `docs/guides/benchmarks.md`, pie de `docs/architecture.md` (390 ficheros); CHANGELOG `[Unreleased]` → *Added*.

## AUDIT_CODE
- **Hallazgo corregido durante IMPLEMENT (habría sido crítico)**: en SQLite con pysqlite, el `SAVEPOINT` abría la
  transacción y su `RELEASE` la confirmaba; un fallo posterior de `bulk_session` no deshacía los lotes limpios. El primer
  test de atomicidad pasaba por casualidad (el lote fallido iba primero); ahora se prueba con lote limpio y con rechazo.
- R-1 confirmado más amplio de lo previsto: en SQL Server el valor demasiado largo no llega como `DataError` con ningún
  driver (pyodbc + `fast_executemany`: `ProgrammingError` en el cliente; pymssql: `OperationalError` 2628). No se
  amplían las clases aisladas (un `ProgrammingError`/`OperationalError` puede ser estructural); documentado.
- R-3: la PK duplicada en SQL Server no condena la transacción (test con pyodbc y pymssql).
- Staging dentro de SAVEPOINT: la temporal tiene nombre único por llamada; en PostgreSQL el rollback al SAVEPOINT la
  elimina; en MySQL el `DROP TEMPORARY` se ejecuta en el `except` de la estrategia.
- Sin hallazgos abiertos. Avisos de Sonar existentes (número de parámetros de `__init__`), no nuevos en naturaleza.

## /audit-code posterior (`e2ce535..HEAD`: P-1, prefetch_blocks, isolate)
- Veredicto: APROBADO CON CONDICIONES → condición cumplida.
- **M-1 (MEDIA, corregido)**: CSV de rechazos no escribible (abierto en Excel) → la operación fallaba bien, pero el log
  decía «Error registrando auditoría» y `rows_rejected` contaba la fila no escrita. Ahora nota y log propios
  («no se pudo escribir el CSV de rechazos») y `Isolator` incrementa solo tras `on_reject` sin error.
- **B-2 (BAJA, corregido)**: un WARNING por fila rechazada → DEBUG; el resumen por operación sigue en WARNING.
- Abiertos (BAJA): B-1 con `XACT_ABORT ON` en SQL Server el error visible es el del rollback al SAVEPOINT (el original en
  `__context__`); B-3 `_savepoint` con sqlite3 `autocommit=True`; B-4 `RejectsWriter` sin validar cabecera ni lock entre
  instancias (no lo usan `ParallelBulkLoader` ni `dump`).
- Tests añadidos (5): CSV no escribible, log por fila en DEBUG, isolate + prefetch, posiciones de
  `bulk_delete_from_chunks`, SQLite con cadencia y fallo posterior de la sesión.

## Validación
`ruff`/`mypy` limpios (390); `pytest` 5947 passed (tras el audit-code); integración bulk 293 passed (5 servidores) + `isolate and mssql` con
pymssql 4 passed; `zensical build --strict` sin avisos.

## Directrices para Futuras IAs
- **[bulk/rejects]**: el aislamiento vive en `bulk/_support/rejects.py`; los ejecutores solo lo llaman si su atributo
  `isolator` no es None, y `BulkCrud.__isolating` lo fija y lo quita (también si falla) alrededor de cada operación.
- **[bulk/sqlite]**: cualquier `begin_nested()` en SQLite con pysqlite (control heredado) necesita una transacción real
  debajo; si no, `RELEASE` confirma. Usar `rejects._savepoint`.
- **[bulk/rejects]**: solo `IntegrityError` y `DataError` se aíslan; qué clase llega depende del driver (Oracle y SQL
  Server no dan `DataError` para el truncado). Antes de prometer un caso, probarlo en integración con cada driver.
- **[bulk/rejects]**: `rows_committed`/`last_operation_rows_committed` cuentan posiciones (rechazadas incluidas); la
  auditoría cuenta filas aplicadas.

## Veredicto final
Veredicto: CLOSED
