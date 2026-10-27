# TRACEABILITY

## Session metadata
- id: 2026-10-27-web-gaps-ola5
- fecha: 2026-10-27
- rama: develop
- skill: new_feature + version-closure
- fase: IMPLEMENT + AUDIT_CODE + VERSION de la ola 5 (v4.5.0)

## Prompt issued
Ola 5 del plan de huecos de util_bbdd_web (carga bulk, util_bbdd 4.5.0): fases U-B1 … U-B4, un commit por fase en
`develop`; solo parámetros opcionales nuevos, sin cambios de valor por defecto (G35 solo `FutureWarning`); documentar
en el CHANGELOG qué deshace una cancelación en una carga de una sola transacción. Plan canónico:
`docs/plan/UTIL_BBDD_GAPS_PLAN.md` de util_bbdd_web (solo lectura); PLAN y AUDIT_PLAN aprobados allí (2026-10-25).

## Context sources
- `src/util_bbdd/bulk/` en 4.4.0 (`crud.py`, `options.py`, `_execution/executors.py`, `session.py`,
  `parallel_loader.py`, `parallel_planner.py`).
- `backend/app/integrations/util_bbdd/bulk.py` de util_bbdd_web (recuento por PK antes y después, G37; deducción propia
  de la atomicidad, G36; `generar_sql` siempre explícito, G35).
- Contrato de `util_bbdd.progress` (4.1.0) y su uso en `DumpOrchestrator.run()` (4.4.0).

## AI output summary
- Un commit por fase (ruff, ruff format, mypy, pytest completo y `zensical build --strict` en cada una; AUDIT_CODE tras
  cada fase):
  - U-B1 `1498169c` G37: `RowLedger` cuenta también sin cadencia; los tres caminos de transacción sin cadencia
    (`bulk_session` atómica, `BatchStatementExecutor._run`, DELETE fuera de sesión) confirman o descartan el libro;
    la carga paralela de `bulk_*_from_df` suma `total_rows` (`RowLedger.record_committed`).
  - U-B2 `b000e06a` G36: `ParallelPlan.atomic` (campo, `False` por defecto), calculado por `ParallelPlanner.plan` con
    `PlanInput.periodic_commits`; `ParallelOptions.require_atomic` (validado en `BulkOptions`; `ParallelBulkLoader` lo
    rechaza).
  - U-B3 `b15a879f` G35: `dry_run` (solo palabra clave) en `bulk_*_from_df`; `generar_sql: bool | None = None` y
    `_resolve_generar_sql` con `FutureWarning` (`stacklevel=4`: helper, método, wrapper de `medir_tiempo`, llamador).
    Ejemplos de docstrings y guías con `generar_sql=False` explícito.
  - U-B4 `316dbfd4` G1: `on_progress`/`cancel_token` en los seis métodos de carga; `bulk/_execution/progress.py`
    (`BatchProgress`, seguro entre hilos); comprobación antes de cada lote en los dos ejecutores; progreso compartido
    con los workers de `ParallelBulkLoader` (`_progress`).
- Evidencias: pytest 6667 passed, 614 skipped (`build/logs/U-B4_pytest.txt`); mypy limpio (353 ficheros);
  `zensical build --strict` limpio. Banco (`build/logs/ola5_bench_check.txt`): contadores, eventos y cancelación
  (atómica, con cadencia y DELETE) en PostgreSQL (psycopg), MySQL, MariaDB (PyMySQL y Connector), SQL Server (pymssql y
  pyodbc con `fast_executemany`) y Oracle: 7 de 7. Integración de `bulk` y `dump`: 481 passed, 6 skipped
  (`build/logs/ola5_bulk_integration.txt`); integración completa (`-m integration`): 656 passed y 14 fallos/errores de entorno (`asyncpg`/`aioodbc` no instalados, HSQLDB sin `JAVA_HOME`), ninguno en `bulk` ni `dump` (`build/logs/ola5_integration.txt`).
- `scripts/gen_arquitectura_capas.py`: sin aristas nuevas (`bulk → progress` ya estaba dibujada); 353 ficheros.
- VERSION: `release: v4.5.0`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Ola 5 | `src/util_bbdd/bulk/crud.py`, `options.py`, `_execution/session.py`, `executors.py`, `parallel_planner.py`, `parallel_loader.py`, `progress.py` (nuevo) | completado (v4.5.0) |
| Tests | `tests/unit/bulk/test_row_counters.py`, `test_parallel_atomic.py`, `test_dry_run.py`, `test_bulk_progress.py`; ajustados `test_commit_cadence.py` y `test_commit_cadence_characterization.py` (0 → filas en modo atómico) | completado |

## Desviaciones del plan
- U-B1 (G37): el plan decía «suma de `rowcount` confirmado por lote». Los contadores siguen contando filas enviadas de
  lotes confirmados (con las apartadas por `isolate`): el `rowcount` de un `executemany` no es fiable con PyMySQL,
  psycopg2 ni pyodbc con `fast_executemany` (`supports_sane_multi_rowcount=False`), y `ParallelBulkLoader` usa
  `rows_committed` como posición desde la que reanudar. Lo que se corrige es que no contaban en modo atómico ni en
  paralelo.
- U-B2 (G36): `atomic` también es `False` con `commit_every_n_chunks` y con varias particiones de `ParallelBulkLoader`
  en un hilo (el plan solo hablaba de más de un hilo).
- U-B3 (G35): las vías `*_from_chunks` no reciben `dry_run`: solo ejecutan, no tienen modo seco que nombrar.

## Notas para las fases W-B de util_bbdd_web
- W-B1: `last_operation_rows_committed` es la cifra de la operación (una instancia por carga en la web); son filas
  enviadas, así que en INSERT con `isolate` las escritas son `last_operation_rows_committed - rows_rejected`, y en
  UPDATE/DELETE cuentan también las claves que no existen (el recuento por PK de la web sigue siendo la verificación).
  Tras un fallo atómico es 0; tras un `ParallelLoadError`, las filas de las particiones confirmadas.
- W-B2: `crud.parallel_plan(op, len(df)).atomic`; con `BatchOptions(chunk_size=...)` (sin cadencia) coincide con
  `not plan.parallel`. `require_atomic=True` sirve si se quiere dejar `ParallelOptions` puesto y desactivarlo por carga.
- W-B3: eventos `operation="bulk"`, `phase="rows"`, `total=len(df)`, `message` = tabla (la que se pasa a `bulk_*`,
  con su schema si lo lleva). La cancelación sale con `OperationCancelledError` **sin** resultado de la operación; en
  paralelo, `crud.last_parallel_result` tiene las particiones. `bulk_apply` puede pasar a cancelable entre lotes.
- G35: la web ya pasa `generar_sql` explícito; no ve el aviso.

## Directrices para Futuras IAs
- **[bulk]**: el libro de filas (`SessionScope.rows`, `RowLedger`) cuenta en todos los modos: cada camino de transacción
  sin cadencia hace `confirm()` tras salir bien del `with` y `discard()` ante cualquier excepción (también si falla el
  COMMIT). Un camino nuevo de transacción en `bulk` debe hacer lo mismo o los contadores dejarán de ser fiables.
- **[bulk]**: `rows_committed` es una posición de la entrada (filas enviadas, rechazadas incluidas), no el `rowcount`:
  `ParallelBulkLoader._resume_offset` reanuda con él cuando hay `commit_every_n_chunks`.
- **[bulk]**: los ejecutores (`BatchStatementExecutor`, `DeleteBatchExecutor`) son el único punto por el que pasan los
  lotes de INSERT, UPDATE (también por staging) y DELETE: progreso, cancelación, aislamiento y cadencia viven ahí.
- **[bulk]**: el progreso de una carga paralela es un `BatchProgress` compartido: `BulkCrud.__load_partitions` lo pone
  en `loader._progress` y el loader en `crud._progress` de cada worker; `__progress_scope` lo reutiliza sin evento
  inicial. Si todas las particiones terminaron, no se lanza la cancelación aunque el token se cancelara al final.
- **[bulk]**: `batch_failure_note` deja pasar `OperationCancelledError` sin la nota «falló el lote».
- **[bulk]**: `generar_sql` vale `None` para distinguir el omitido; el `FutureWarning` usa `stacklevel=4` por el wrapper
  de `@medir_tiempo`. Si se quita el decorador o se añade otro nivel, hay que ajustarlo (lo comprueba
  `test_dry_run.py` con `filename == __file__`).
- **[tests]**: para ejercitar el paralelo con SQLite, `monkeypatch` de `parallel_planner.SINGLE_WRITER_DIALECTS` y BD en
  fichero con `timeout` (las particiones se serializan en el lock, pero cada una va en su hilo y su transacción).
- **[banco]**: las variantes de driver (pyodbc, MariaDB Connector) se derivan en memoria de las URL del banco con
  `make_url(...).set(...)`; nunca se imprimen (llevan la contraseña).

## Veredicto final
Veredicto: CLOSED (ola 5, v4.5.0)
Pendientes al cierre:
- Push de `develop` y del tag `v4.5.0`, fast-forward de `main` y wheel + `.sha256` en GitHub Releases (propietario).
- Registrar la ola 5 en §6 del plan de util_bbdd_web (desde esa sesión; aquí es solo lectura) y hacer W-5.0 y W-B1…W-B3.
- HSQLDB y async del banco sin verificar en este venv (falta `JAVA_HOME`, `asyncpg`, `aioodbc`): no afectan a `bulk`.
- Ola 6 (U-T) en sesión aparte.
