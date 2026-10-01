# IMPLEMENT — Fases 0, 1 y 2 del roadmap de `bulk/`

- Alcance decidido por el usuario: Fase 0 + Fase 1. Decisiones: D-1 staging de UPDATE activo por defecto en PostgreSQL;
  D-2 backoff por defecto `(0.5, 30.0)`; D-3 (cadencia + reintentos con reanudación) aprobada para la Fase 2, no
  implementada aquí. 1.5 (B-04, tamaño de envío por estrategia) queda fuera hasta repetir el barrido (AUDIT_PLAN R-6).
- Sin commits (instrucción por defecto: commit solo a petición). Todos los ficheros tocados son de esta sesión.

## Cambios por punto

| # | Hallazgo | Ficheros | Tests |
|---|---|---|---|
| 0.1 | B-17 docs contradictorias | `docs/functional/bulk_operations.md`, `docs/functional/bulk_parallel_loading.md` | build `--strict` |
| 0.2 | B-15a lote y filas en el error | `_execution/executors.py` (`batch_failure_note`), `crud.py` (INSERT, UPDATE, streaming), `DeleteBatchExecutor` | `tests/unit/bulk/test_error_position.py` (6) + integración (6 motores) |
| 0.3 | B-03 tuplas desde columnas | `_execution/insert_strategies.py` (`_insert_rows`, `execute_columns`, `supports_columns`), `_execution/executors.py` (`execute_columns`, `_run`), `crud.py` (`__ejecutar_batch_stmt` despacha `SqlColumns`), `_support/sql_helpers.py` (`restore_binary_values` sin dict por bloque) | `test_insert_columns_path.py` (8, con espía de R-2) + integración |
| 0.4 + 1.4 | B-02 DELETE SQL Server con OPENJSON (simple y compuesta) | `_execution/delete_strategies.py` (`MSSQLOpenJsonDeleteStrategy`), `metadata/sqlserver/common.py` (`fetch_compatibility_level_sql`), `batch.py` | `test_delete_mssql_openjson.py` (13) + integración: 6 tipos de PK × 3 modos + 3 compuestas, con pyodbc y pymssql |
| 1.1 | B-01 UPDATE PostgreSQL por staging | `_execution/staging_update.py` (`StagingUpdateStrategy`, alias `MySQLStagingUpdateStrategy`, `STAGING_UPDATE_DIALECTS`), `metadata/postgresql/tables.py` (`fetch_can_create_temp_tables_sql`), `crud.py` | `test_staging_update_postgresql.py` (5) + integración (ENUM, JSONB, BYTEA, esquema, cadencia; tests de staging existentes ampliados a PG) + prueba manual sin TEMP |
| 1.2 | B-13 reintentos por código | `_support/retry.py` (`is_retriable`), `parallel_loader.py` | `test_retry_classification.py` (37, con clases reales de PyMySQL y psycopg) |
| 1.3 | B-14 backoff con jitter | `parallel_loader.py` (`retry_backoff`, `retry_on`, `PartitionResult.retry_wait_seconds`) | en `test_retry_classification.py` |

Docs y release notes: `docs/api/bulk_crud.md`, `docs/api/bulk_parallel.md`, `docs/guides/benchmarks.md`,
`docs/architecture.md` (pie de figura: 387 ficheros), `CHANGELOG.md` `[Unreleased]` (Added/Changed/Fixed).

## Incidencias durante la implementación
- **OPENJSON y COLLATE** (lo detectó la integración): el tipo reflejado de una columna de texto en SQL Server incluye su
  `COLLATE`, inválido dentro de `CAST`/`WITH`. Se compila el tipo sin intercalación (`_sql_type`); test unitario
  añadido.
- **ENUM en PostgreSQL**: `Table.create` de la temporal intentaría `CREATE TYPE`. La temporal se crea con
  `CREATE TEMPORARY TABLE … AS SELECT … WITH NO DATA` (tipos exactos). Cubierto en integración con un ENUM real.
- **Tests que parchean `__ejecutar_batch_stmt`**: la vía por columnas se saltaba ese método; ahora es el único punto de
  ejecución del INSERT y despacha `SqlColumns` sin trocearlo (R-2).
- **Simulaciones de desconexión**: tres tests construían `OperationalError` genérico; se les añadió
  `connection_invalidated=True`, que es como llega una desconexión real y lo que el clasificador reintenta.

## Validación

- `ruff check` / `ruff format --check`: limpios. `mypy src tests/unit/test_protocol_conformance.py`: sin errores
  (387 ficheros).
- `pytest` (unit, sin servidores): **5816 passed / 291 skipped**.
- `pytest tests/integration` (5 servidores, SQL Server con pyodbc): **432 passed**. Con pymssql (`-k mssql`, bulk y
  dump): **64 passed**.
- `zensical build --strict`: sin avisos. `gen_arquitectura_capas.py`: dibujo coherente (sin cambios de contenido).
- PostgreSQL sin privilegio TEMP (rol de prueba, TEMP revocado a PUBLIC y restaurado): WARNING único, UPDATE fila a fila,
  resultado correcto.

## Antes / después (`scripts/bench_bulk.py`, 1M filas, 1 repetición; `implement/final/`)

| Motor · operación | Línea base | Después | Factor |
|---|---|---|---|
| PostgreSQL UPDATE | 26,43 s | **10,89 s** | 2,43× |
| PostgreSQL INSERT | 6,00 s | **4,44 s** | 1,35× |
| PostgreSQL ciclo completo | 34,5 s | **17,3 s** | 2,0× |
| SQL Server DELETE | 9,27 s | **2,71 s** | 3,42× |
| SQL Server DELETE 1K / 10K (mediana de 3) | 0,214 / 0,810 s | **0,014 / 0,040 s** | 15× / 20× |
| SQL Server DELETE PK compuesta 1M (`implement/composite_1m.log`) | 8,55 s | **3,67 s** | 2,3× |
| MySQL INSERT | 17,60 s | 16,74 s | 1,05× (ruido ±10 %; Fase 0: 15,9 s) |
| MariaDB INSERT | 16,69 s | 15,57 s | 1,07× (ruido) |
| Resto (SQLite, Oracle, UPDATE MySQL/MariaDB/SQL Server, DELETE MySQL/MariaDB/PG/SQLite) | — | — | sin cambio fuera del ruido |

90/90 mediciones verificadas con SQL (72 a 1K–100K y 18 a 1M).

Métricas de éxito del informe: PG UPDATE ≤ 12 s ✔ (10,9); SQL Server DELETE ≤ 3 s / ≤ 0,1 s ✔ (2,7 / 0,04); PG INSERT
≤ 5,0 s ✔ (4,4); error permanente de PyMySQL con `max_retries=3` → 1 intento ✔ (test).

## Fase 2 (segunda petición: «Fase 2»)

Orden del AUDIT_PLAN: 2.2 → 2.1 → 2.3 → 2.4.

| # | Hallazgo | Cambios | Tests |
|---|---|---|---|
| 2.2 | B-08 streaming de UPDATE/DELETE | `crud.py`: `bulk_update_from_chunks`, `bulk_delete_from_chunks`, `__stream_operation` (una sesión, `closing_iterable`, reflexión antes de abrir la sesión), `_StreamPosition` (lote **y chunk** en la nota de error), caché de `StagingUpdateStrategy` por instancia (TEMP se comprueba una vez); `executors.py`: `DeleteBatchExecutor` con cadencia persistente entre chunks (`continue_cadence`) — sin ella, con chunks de pocos lotes nunca llegaba al commit periódico | `test_streaming_and_resume.py` + integración 6 motores |
| 2.1 | B-11 checkpoint y reanudación (D-3) | `session.py`: `RowLedger` con sub-libro de operación (`add`, `start_operation`, `op_committed`); `BulkCrud.last_operation_rows_committed`; `parallel_loader.py`: retirado el `ValueError` de cadencia + reintentos, `_skip_rows`, el reintento reanuda tras `crud.rows_committed` (solo con cadencia) | unit (R-3, prefijo, atómico = 0, reanudación sin duplicados) + integración 6 motores (fallo tras 600 filas, 1000 exactas) |
| 2.3 | B-05 UPDATE/DELETE paralelos | `ParallelBulkLoader.update()`/`.delete()` sobre `_run(operation)`; PostgreSQL sin TEMP → 1 hilo + WARNING; `disable_constraints` solo en `load()`; **2 reintentos mínimos** en `update`/`delete` (ver incidencia) | unit + integración 5 servidores (2 hilos) |
| 2.4 | B-06/B-12 guía | `docs/guides/benchmarks.md` § «UPDATE y DELETE en paralelo (1M filas)» y § «Checkpoints, reanudación y reintentos»; `docs/api/bulk_crud.md`, `docs/api/bulk_parallel.md`, `docs/functional/bulk_parallel_loading.md`; CHANGELOG | `zensical build --strict` |

### Incidencia: deadlock de InnoDB en el DELETE paralelo (R-5)
La medición R-5 (`implement/parallel_api.log`) dio un `ok: false` en MySQL con 2 hilos: `1213 Deadlock found` en un
`DELETE … IN (...)` de la partición 1, con particiones disjuntas y contiguas (bloqueo de hueco en la frontera). Con
`max_retries=0` por defecto la partición fallaba. Como UPDATE y DELETE por PK son idempotentes, `update()`/`delete()`
reintentan los errores transitorios al menos 2 veces (`_IDEMPOTENT_MIN_RETRIES`); `load()` no cambia. Prueba de estrés
tras el cambio (`implement/deadlock_stress.log`): 12/12 ciclos a 1M (MySQL y MariaDB, 2 y 4 hilos), un deadlock
reintentado con éxito, 0 errores.

### Medición R-5 (`ParallelBulkLoader`, 1M filas, media de 2; `implement/parallel_api.log`)

| Motor | UPDATE 1 → 4 hilos | DELETE 1 → 4 hilos | INSERT 1 → 4 hilos |
|---|---|---|---|
| PostgreSQL | 10,8 → 6,9 s | 1,8 → 0,9 s | 4,3 → 3,8 s |
| MySQL | 24,1 → 12,9 s | 7,2 → 4,3 s | 17,5 → 9,7 s |
| MariaDB | 22,2 → 12,6 s | 6,9 → 4,6 s | 16,4 → 9,6 s |
| SQL Server | 22,8 → 8,2 s | 3,0 → 1,2 s | 15,4 → 5,9 s |
| Oracle 23 Free | sin ganancia (2 hilos de CPU) | | |

Frente a la línea base (UPDATE en serie): PostgreSQL 26,4 → 6,9 s (3,8×), SQL Server 23,0 → 8,2 s (2,8×), MySQL 23,1 →
12,9 s (1,8×), MariaDB 21,9 → 12,6 s (1,7×). R-5 resuelto: en `bulk` (datos en memoria) MySQL/MariaDB sí escalan (~1,8×);
el empeoramiento de `dump` se debe a la lectura concurrente del origen.

### Validación de la Fase 2
- `ruff`/`ruff format`/`mypy` limpios; unit **5833 passed / 306 skipped**; integración **449 passed** (pyodbc) y
  **67 passed** con pymssql (`-k mssql`); `zensical build --strict` sin avisos; diagrama de capas sin cambios.
- Mutaciones: sin `continue_cadence` falla `test_delete_cadence_continues_across_chunks`; sin reanudación falla
  `test_retry_resumes_after_committed_rows_without_duplicates`.

## Pendiente
- 1.5 (B-04, tamaño de envío por estrategia) tras repetir el barrido con `--repeat 3`.
- Fase 3 (spikes): procesos para PG, aislamiento de filas erróneas, causa del `ClientRead`, prefetch.
- `/version-closure` (minor) y commits por punto cuando el usuario los pida.
