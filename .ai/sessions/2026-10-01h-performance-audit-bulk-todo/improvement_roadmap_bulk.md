# Roadmap de mejoras de `bulk/` (performance-audit 2026-10-01h)

Hallazgos en `audit_report_bulk_20261001.md`; medidas en `validation_report_20261001.md`. Cada punto se implementa por
separado con el flujo indicado y commit `perf:`, `feat:`, `fix:` o `docs:`. Tras cada uno: `scripts/bench_bulk.py`
(1M, motores afectados) y `tests/integration` en los 5 servidores del banco.

## Fase 0 — Quick wins (≤ 1 h cada uno, sin cambio de API)

| # | Hallazgo | Flujo | Cambio | Criterio de aceptación |
|---|---|---|---|---|
| 0.1 | B-17 | `docs:` | Corregir `docs/functional/bulk_operations.md:26` (operación atómica por defecto) y `bulk_parallel_loading.md:72` (`max_retries`) | `mkdocs build --strict` limpio |
| 0.2 | B-15a | `/new-feature` | `exc.add_note(tabla, operación, lote, filas desde–hasta)` en el fallo de un lote | Test: el error de un lote incluye su rango |
| 0.3 | B-03 | `/refactor` | Columnas → tuplas en COPY, PyMySQL y execute_values | Equivalencia estricta de valores; PG INSERT 1M ≤ 5,0 s |
| 0.4 | B-02 (PK simple) | `/refactor` (`perf:`) | DELETE SQL Server por OPENJSON con fallback al `IN` | DELETE 1M ≤ 3 s y 10K ≤ 0,1 s; nivel < 130 usa el `IN` |

## Fase 1 — Rendimiento por motor y tolerancia a fallos (1–2 días)

| # | Hallazgo | Flujo | Cambio | Depende de |
|---|---|---|---|---|
| 1.1 | B-01 | `/new-feature` (`perf:`) | Staging de UPDATE en PostgreSQL (estrategia generalizada por dialecto; fallback sin `TEMP`) | — |
| 1.2 | B-13 | `/hotfix` | Clasificador de reintentos por código y desconexión (`is_retriable`) | — |
| 1.3 | B-14 | `/new-feature` | Backoff exponencial con jitter y tope en `ParallelBulkLoader` | 1.2 |
| 1.4 | B-02 (PK compuesta) | `/refactor` | `OPENJSON … WITH` en lugar del executemany por fila | 0.4 |
| 1.5 | B-04 | `/refactor` (`perf:`) | Tamaño de envío por estrategia (COPY/fast_executemany 20.000; `DELETE … IN` MySQL/MariaDB ≤ 5.000), tras repetir el barrido con `--repeat 3` | — |

## Fase 2 — Paralelización, checkpoints y backpressure (3–5 días)

| # | Hallazgo | Flujo | Cambio | Depende de |
|---|---|---|---|---|
| 2.1 | B-11 | `/new-feature` | Checkpoint por llamada (`rows_committed` por operación), reanudación en `*_from_chunks`, reintento que reanuda en `ParallelBulkLoader` (cadencia + `max_retries` compatibles) | 1.2, 1.3 |
| 2.2 | B-08 | `/new-feature` | `bulk_update_from_chunks` y `bulk_delete_from_chunks` | — |
| 2.3 | B-05 | `/new-feature` | `ParallelBulkLoader.update/delete` con particiones disjuntas por PK | 1.1 (PG), 2.2 |
| 2.4 | B-12, B-06 | `docs:` | Guía: punto de saturación por motor, 100K filas por commit, SQLite sin cadencias cortas | 2.1, 2.3 |

## Fase 3 — Investigación (spike, sin compromiso)

| # | Hallazgo | Pregunta | Cómo medirla |
|---|---|---|---|
| 3.1 | B-06 | ¿`ProcessPoolExecutor` desbloquea el INSERT de PG (limitado por el cliente)? | `ParallelBulkLoader(executor="process")` prototipo, 1M, 1/2/4 procesos |
| 3.2 | B-15b | Coste de aislar filas erróneas (bisección / Oracle `batcherrors`) | 1M con 1, 10 y 100 filas malas |
| 3.3 | B-05 | Causa del `ClientRead` en el UPDATE paralelo de PG | `py-spy dump` de los hilos durante el UPDATE |
| 3.4 | B-09 | ¿Prefetch estable en SQL Server/MySQL con 3 repeticiones? | E3 con `--repeat 3` |

## Descartado (no implementar)

UPDATE por staging en SQL Server y Oracle, DELETE Oracle con `SYS.ODCINUMBERLIST`, prefetch por defecto: ver
§ «Descartados tras medir» del informe.

## Métricas de éxito

Las de § VERSION del informe, medidas con `scripts/bench_bulk.py --sizes 1000000` y los prototipos de
`bench/proto_bulk_todo.py` convertidos en variantes del banco cuando la mejora entre en `src/`.
