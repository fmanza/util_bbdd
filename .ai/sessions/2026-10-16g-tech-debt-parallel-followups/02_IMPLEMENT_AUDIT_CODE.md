# IMPLEMENT + AUDIT_CODE — Deuda menor de la carga paralela

Aprobado por el usuario: recomendaciones del PLAN (D1 con traspaso privado, D3 cerrado sin código) y benchmarks de D5.

## IMPLEMENT

| # | Cambio | Ficheros | Test |
|---|---|---|---|
| D1 | El loader cachea el privilegio `TEMP` por instancia (`_temp_tables_allowed`) y la fachada de `BulkCrud` le pasa el que ya comprobó `parallel_plan`: de 2 conexiones extra por UPDATE paralelo de PostgreSQL a 1 (la de la fachada, cacheada por instancia). Las comprobaciones de los workers, en su sesión, se mantienen | `bulk/_execution/parallel_loader.py` (`__init__`, `_staging_update_available`), `bulk/crud.py` (`__load_partitions`) | `TestParallelFollowups.test_loader_checks_temp_once_per_instance`, `test_loader_uses_the_fact_passed_by_the_facade`, `test_facade_hands_its_temp_fact_to_the_loader` |
| D2 | El INFO «Auditoría deshabilitada en la carga paralela» solo con `audit.warn_if_disabled`; la fachada pasa `warn_if_disabled=False` (ya avisó al crearse). `dump` sin cambios | `parallel_loader.py` (`_run`), `crud.py` | `test_facade_does_not_repeat_the_audit_disabled_info`, `test_loader_alone_still_reports_disabled_audit` |
| D3 | Cerrado sin código: `docs/api/bulk_crud.md` explica por qué las filas paralelas no cuentan en `rows_committed` (prefijo de reanudación) | `docs/api/bulk_crud.md` | — |
| D4 | `_load_in_pk_ranges(..., rows_hint=source_rows)`: con `parallel_pk_ranges="auto"` planifica con `min(MAX − MIN + 1, COUNT(*))`; sin recuento (`-1`/`None`), la cota | `dump/orchestrator.py`, `dump/_models.py` (docstring), `docs/api/dump.md` | `test_row_count_below_the_threshold_wins_over_a_sparse_range`, `test_without_row_count_the_range_is_the_estimate`, `test_row_count_never_raises_the_range_estimate` |
| D5(a) | `scripts/bench_parallel.py` (nuevo): serie frente a N hilos, calentamiento, tandas alternas, mediana e IQR, veredicto con el criterio del planificador, `--out` (solo la tabla) | `scripts/bench_parallel.py`, `docs/guides/benchmarks.md` (§ «Banco de la carga paralela»), `.ai/runtime.md` | `tests/unit/test_bench_parallel_script.py` (7 tests, uno en proceso contra SQLite) |
| D5(b/c) | Oracle 200K y 1M, 1/2/4 hilos, 5 tandas alternas: **no gana** (0,92×–1,15×). Regla en serie; `evidence` actualizada; tabla en `benchmarks.md`; las ganancias anteriores (1,39×/1,89×, 27,3 s) eran de tandas sin calentar | `bulk/_execution/parallel_planner.py`, `docs/api/bulk_parallel.md`, `docs/guides/benchmarks.md` | `build/logs/td_bench_oracle_abab.txt` |

Otros: `docs/guides/benchmarks.md` tenía `BulkCrud(update_via_staging=False)` en la tabla de variantes de `bench_bulk.py`
(sintaxis 2.x) → `ExecutionOptions(update_via_staging=False)`.

## AUDIT_CODE (deuda técnica)

### Deuda tras los cambios

| Módulo | Hallazgo | Impacto | Prioridad |
|---|---|---|---|
| `bulk/crud.py` (`__load_partitions`) | Acceso al atributo privado `loader._temp_tables_allowed` desde la fachada (mismo paquete, comentado) | Mantenibilidad: acoplamiento privado dentro de `bulk/`; sin cambio de API ni de capas | aceptada (decisión del PLAN; alternativa global descartada por estado mutable) |
| `scripts/bench_parallel.py` | La salida estándar mezcla la tabla con los tiempos que imprime `util.timing.medir_tiempo` (dependencia externa opcional) | Legibilidad de la salida; mitigado con `--out` | aceptada |
| `dump/orchestrator.py` | `source_rows` se cuenta antes de cargar y puede quedar desfasado si el origen cambia durante el volcado | Igual que el informe actual; solo afecta a la decisión de rangos | aceptada |

Sin deuda nueva de tipado (`mypy` limpio, 339 ficheros) ni de seguridad (sin SQL nuevo; el script lee la contraseña del
entorno y no la imprime).

### Quick wins pendientes
- Ninguno.

### Riesgos si no se hubiera abordado
- D4: particionar tablas dispersas por debajo del umbral medido en SQL Server.
- D5: decisiones de `"auto"` sobre mediciones no reproducibles.

## Validación

| Comando | Resultado | Log |
|---|---|---|
| `pytest` (shell sin URLs del banco) | 6219 passed, 532 skipped (+16) | `build/logs/td_pytest.txt` |
| `pytest tests/integration` (banco, 6 motores) | 589 passed, 7 skipped | `build/logs/td_integration.txt` |
| `ruff check`, `ruff format --check`, `mypy src tests/unit/test_protocol_conformance.py` | limpios | — |
| `zensical build --strict`, `scripts/gen_arquitectura_capas.py` | sin avisos; sin aristas nuevas | `build/logs/td_docs_build.txt` |
| `scripts/bench_parallel.py --engines oracle --rows 200000,1000000 --workers 2,4 --repeat 5` | Oracle no gana en paralelo | `build/logs/td_bench_oracle_abab.txt` |

## Veredicto: `LIMPIO` (sobre los ítems D1–D5)

VERSION propuesta: **3.0.1 (PATCH)** — sin cambio de API; D5 no cambia ninguna regla (solo evidencia).
