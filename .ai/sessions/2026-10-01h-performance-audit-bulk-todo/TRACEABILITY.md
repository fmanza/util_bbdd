# TRACEABILITY

## Session metadata
- id: 2026-10-01h-performance-audit-bulk-todo
- fecha: 2026-10-01
- rama: develop (`e80059e`, v0.23.1)
- skill: performance-audit-bulk
- fase: PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION + validación con banco; después PLAN/AUDIT_PLAN del roadmap e IMPLEMENT de las Fases 0, 1 y 2

## Prompt issued
Ver `00_REQUEST.md` (objetivos: todo + paralelización, batching, backpressure, checkpoints, errores y tolerancia a
fallos, auditoría, rendimiento; todos los motores; 1M; línea base primero; validación; resultados por objetivo).

## Context supplied
- `.github/prompts/performance_audit_bulk.prompt.md`, `.github/agents/performance-auditor.agent.md`, `.ai/runtime.md`
- Sesiones previas: `2026-09-23-performance-audit-bulk` (P-01…P-29), `2026-09-25-performance-audit-bulk-sql`,
  `2026-09-27b-pendientes-bulk-dump`, `2026-09-24-p08-parallel-loader-descartado`
- Código completo de `src/util_bbdd/bulk/` (crud, `_execution/`, `_support/persistence.py`, normalize)

## AI output summary
- Línea base `scripts/bench_bulk.py` con 6 motores (SQL Server con pyodbc + ODBC 18): 72/72 mediciones verificadas.
- Prototipos en `bench/proto_bulk_todo.py`, `proto_oracle_delete.py`, `proto_pg_parallel_update.py` (E1–E9) y barrido de
  `chunk_size` (E6). Todos verificados con SQL; ejecutados en serie.
- Mapeo de excepciones de PyMySQL, psycopg, oracledb y pyodbc (B-13).
- 18 hallazgos (B-01…B-18, sin B-07/B-10/B-16 como hallazgos propios), 3 ideas descartadas tras medir.
- Veredicto **SIGNIFICATIVO**. Sin cambios en `src/`, `tests/` ni `docs/`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Solicitud y supuestos | `00_REQUEST.md` | emitido |
| Informe (PLAN, AUDIT_PLAN, AUDIT_CODE, VERSION) | `audit_report_bulk_20261001.md` | emitido |
| Roadmap | `improvement_roadmap_bulk.md` | emitido |
| Validación | `validation_report_20261001.md` | emitido |
| PLAN de implementación (Fases 0–2) | `PLAN.md` | emitido (2ª petición: «PLAN y AUDIT_PLAN») |
| AUDIT_PLAN (GO_CONDICIONAL, R-1…R-10, D-1…D-3) | `AUDIT_PLAN.md` | emitido |
| IMPLEMENT Fases 0 y 1 (B-17, B-15a, B-03, B-02, B-01, B-13, B-14) | `IMPLEMENT.md`, `implement/` | completado, sin commit |
| IMPLEMENT Fase 2 (B-08, B-11, B-05, guía) | `IMPLEMENT.md` § Fase 2, `implement/parallel_api.log`, `implement/deadlock_stress.log` | completado, sin commit |
| Línea base | `baseline/small/`, `baseline/1m/` | datos |
| Prototipos y resultados | `bench/` (`*.py`, `*.log`, `results/*.csv`, `chunks/`) | datos |

## Directrices para Futuras IAs
- **[bulk/update]**: fuera de MySQL/MariaDB el UPDATE es un executemany por fila; el staging solo se activa en
  `MYSQL_FAMILY` (`crud.py:228`). Para PG basta COPY a una temporal sin esquema + `update(t).values({t.c: tmp.c})` (SQLAlchemy
  genera `UPDATE … FROM`) y `DROP TABLE` (no `DROP TEMPORARY TABLE`): 2,35×.
- **[bulk/update]**: en SQL Server y Oracle el staging de UPDATE es **más lento**; en Oracle, además,
  `CREATE PRIVATE TEMPORARY TABLE` confirma la transacción en curso (rompe la atomicidad). No repetir.
- **[bulk/delete]**: el DELETE de SQL Server con `IN` de 2000 parámetros paga compilación por forma de sentencia; OPENJSON
  con un parámetro por lote: 3,45× a 1M y 20× a 10K.
- **[bulk/parallel]**: el UPDATE paralelo de PG por executemany empeora con cada hilo (82 % `ClientRead`, no es el convoy del
  GIL: `setswitchinterval` no cambia nada). Con staging escala (4 hilos 6,3 s/1M).
- **[bulk/parallel]**: Oracle 23 Free usa como máximo 2 hilos de CPU: no sirve para medir paralelismo en Oracle.
- **[bulk/checkpoints]**: con `commit_every_n_chunks`, `rows_committed` es exactamente el prefijo confirmado de la entrada;
  reanudar con `df.iloc[rows_committed:]` funciona en los 6 motores (contador acumulado por instancia, no por llamada).
- **[bulk/errores]**: PyMySQL mapea 1045, 1054 y 1292 a `OperationalError` (permanentes); oracledb mapea ORA-00060 a
  `DatabaseError`. Clasificar reintentos por código, no por clase.
- **[bench]**: el prototipo de staging sustituye `util_bbdd.bulk.crud.MySQLStagingUpdateStrategy` y fija
  `crud._update_via_staging = True`; es la forma de probar estrategias de UPDATE sin tocar `src/`.
- **[bulk/staging PG]**: en PostgreSQL un `CREATE` fallido aborta la transacción (`25P02`, verificado); el fallback por
  privilegio de MySQL (reaccionar al error) no sirve: comprobar `has_database_privilege(current_database(), 'TEMP')`
  antes (SQL en `metadata/postgresql`) o usar savepoint.
- **[bulk/columnas]**: `SqlColumns[a:b]` construye un dict por fila; trocear un bloque por columnas anula P-34/B-03 en
  silencio.
- **[bulk/lotes]**: `dump` midió 20.000 filas por lote −31 % en PG y +81 % en SQL Server (`dump/_models.py:130`); la
  auditoría de bulk (1 repetición) dio −10 % en SQL Server. No cambiar el lote de SQL Server sin repetir.
- **[bulk/insert]**: `BulkCrud.__ejecutar_batch_stmt` es el único punto de ejecución del INSERT (hay tests que lo parchean); un `SqlColumns` va a `execute_columns` sin trocear.
- **[bulk/delete mssql]**: el tipo reflejado de una columna de texto lleva `COLLATE`, inválido en `CAST`/`OPENJSON … WITH`; usar `_sql_type`.
- **[bulk/staging PG]**: crear la temporal con `CREATE TEMPORARY TABLE … AS SELECT … WITH NO DATA`; `Table.create` intentaría `CREATE TYPE` con columnas ENUM.
- **[bulk/retry]**: simular una desconexión en tests con `OperationalError(..., connection_invalidated=True)`; un `OperationalError` sin código ya no se reintenta.
- **[bulk/stream]**: las vías `*_from_chunks` son **una** operación en el libro de filas (`start_operation` al empezar el stream); `__run_bulk_pipeline` no la reinicia mientras `self._stream` no es `None`.
- **[bulk/delete]**: el contador de lotes del DELETE es del ejecutor y se reinicia por llamada salvo `continue_cadence=True` (chunks 2..n de un stream).
- **[bulk/parallel]**: InnoDB da deadlock 1213 entre particiones contiguas y disjuntas en el DELETE paralelo; `update()`/`delete()` reintentan al menos 2 veces (`_IDEMPOTENT_MIN_RETRIES`). No aplicar a `load()`: el INSERT no es idempotente.
- **[bench]**: `bench/bench_parallel_api.py` ejecuta su banco a nivel de módulo: no importarlo desde otros scripts.
- **[bench]**: en Windows, lanzar los prototipos con `PYTHONIOENCODING=utf-8` (los nombres de variante llevan «→»).

## Cierre de versión (v0.24.0)

### Commits
- `b597914` docs(bulk) B-17 · `7b64aac` feat(metadata) SQL de catálogo · `874dd82` feat(bulk) Fases 0–2 ·
  `fe64156` docs(bulk) · `a72e696` docs(sessions) · `release: v0.24.0` (este cierre) y tag anotado `v0.24.0`.
- No fue posible un commit por punto: B-03, B-15a, B-08, B-11, B-13 y B-14 comparten funciones de `crud.py`,
  `executors.py` y `parallel_loader.py`; el commit de código se verificó aislado (stash del resto): 5833 passed.

### Impacto en API pública
- Añadido: `BulkCrud.bulk_update_from_chunks`, `bulk_delete_from_chunks`, `last_operation_rows_committed`;
  `ParallelBulkLoader.update`, `delete`, `retry_backoff`, `retry_on`; `PartitionResult.retry_wait_seconds`;
  `StagingUpdateStrategy`, `MSSQLOpenJsonDeleteStrategy`, `is_retriable` (internos de `bulk._execution`/`_support`).
- Comportamiento: staging de UPDATE en PostgreSQL por defecto; reintentos por código de error y con espera; cadencia +
  reintentos permitidos (reanuda); `update`/`delete` paralelos reintentan al menos 2 veces; DELETE de SQL Server por
  OPENJSON; notas en los errores de lote. Ninguna firma existente cambia; nada retirado. `MySQLStagingUpdateStrategy`
  sigue como alias.
- Compatibilidad: Python >= 3.12 (sin cambios). Motores: PostgreSQL (staging requiere `TEMP`), SQL Server (OPENJSON
  requiere nivel >= 130; fallback automático), MySQL/MariaDB, Oracle y SQLite sin requisitos nuevos.

### Checklist (`sync.instructions.md`)
- [x] `ruff check`/`ruff format --check` limpios; `mypy src tests/unit/test_protocol_conformance.py` sin errores (387).
- [x] `pytest`: 5833 passed / 306 skipped; `tests/integration` con 5 servidores: 449 passed (pyodbc), 67 passed con
  pymssql (`-k mssql`, bulk/dump).
- [x] `python -m build`: `util_bbdd-0.24.0` (sdist y wheel).
- [x] CHANGELOG `[0.24.0] - 2026-10-01` (con *Migración*) y `[Unreleased]` vacío; `pyproject.toml`, `README.md`,
  `docs/index.md`, `docs/roadmap.md` y pie de `docs/architecture.md` en 0.24.0 (`test_docs_version.py`: 3 passed).
- [x] `zensical build --strict`: sin avisos.
- [x] `## Directrices para Futuras IAs` poblada.

### Rollback
- Nada publicado: `develop` va por delante de `origin/develop` y el tag `v0.24.0` es local. Antes del push:
  `git tag -d v0.24.0` y `git reset --hard e80059e` (descarta los 6 commits) o revert selectivo.
- Tras el push: `git revert` del commit de release y de `874dd82` (código); `7b64aac` es aditivo (funciones de SQL sin
  uso tras el revert). Desactivar sin revertir: `BulkCrud(update_via_staging=False)` (PostgreSQL) y
  `ParallelBulkLoader(retry_backoff=(0, 0), retry_on=lambda e: isinstance(e, (OperationalError, TimeoutError)))`.
  El DELETE por OPENJSON no tiene interruptor: se revierte con el commit.
- Riesgo del rollback: vuelve el UPDATE fila a fila en PostgreSQL (26 s/1M) y el `ValueError` con cadencia +
  reintentos.

### Handoff
- Hecho: push de `develop` y del tag `v0.24.0` (2026-10-01). Siguiente: B-04.
- Roadmap pendiente: 1.5 (B-04) tras `scripts/bench_bulk.py --sizes 1000000 --chunk-size {1000,5000,20000,50000}
  --repeat 3`; Fase 3 (spikes) en `improvement_roadmap_bulk.md`.

## Veredicto final
Veredicto: CLOSED (auditoría: SIGNIFICATIVO)
Pendientes al cierre:
- 1.5 (B-04, tras repetir el barrido) y Fase 3 (spikes).
- `v0.24.0` cerrada y publicada (push de `develop` y tag `v0.24.0`, 2026-10-01).
