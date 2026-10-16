# IMPLEMENT — Paquetes de opciones de BulkCrud y planificador de paralelismo (v3.0.0)

Decisiones aceptadas por el usuario: D1 (`DumpConfig` sigue plano), D2 (fachada paralela de `BulkCrud` en 3.0.0),
D3 (campos sin prefijo). Sin commit (pendiente de AUDIT_CODE y VERSION).

## Cambios por grupo

| Grupo | Cambios |
|---|---|
| G1 | `bulk/options.py` (nuevo): `BatchOptions`, `AuditOptions`, `RejectOptions`, `ExecutionOptions`, `RetryOptions`, `ParallelOptions`, `BulkOptions` (`of`, `for_worker`, `as_kwargs`). `OptionalPathField(label=...)` en `_core/validation/paths.py` para que el error diga `audit.csv_path` / `rejects.csv_path` |
| G2 | `BulkCrud(engine, *, batch, audit, rejects, execution, parallel)` y `ParallelBulkLoader` con los mismos paquetes; workers con `BulkOptions.for_worker` (ahora reciben `insert_resolver`, `update_via_staging` y `prefetch_blocks`). Migración automática (`ast`) de 241 llamadas en tests/docs/scripts y 6 manuales (`**kwargs`) |
| G3 | `bulk/_execution/parallel_planner.py` (nuevo): `ParallelPlanner`, `PlanInput`, `ParallelPlan`, `ParallelRule`, `SINGLE_WRITER_DIALECTS`; loader con `_plan()` y `ParallelLoadResult.plan`; regla SQLite en el loader |
| G4 | `BulkCrud.bulk_*_from_df` con `parallel`: `parallel_plan()`, `options`, `last_parallel_result`; particiones (INSERT por tramos; UPDATE/DELETE por PK: rangos o hash); `ParallelLoadError` (`_core/exceptions.py`, público en `util_bbdd.exceptions`); contadores de auditoría y `rows_rejected` agregados |
| G5 | `DumpConfig.parallel_pk_ranges: int \| "auto"` (validado); orquestador: `_bulk_options()` → `BulkOptions`, `_pk_ranges_requested`, `_plan_pk_ranges`, `_known_pool_capacity`; `_single_writer_target` usa `SINGLE_WRITER_DIALECTS` |
| G6 | `_skip_rows` → `_support/iterables.skip_rows`; `_validate_partition_ranges` → `RangePartitioner.validate_disjoint`; `_partition_error` → `@staticmethod`; `_EXPECTED_ERRORS`/`_IDEMPOTENT_MIN_RETRIES` → `ClassVar` (`EXPECTED_ERRORS`, `IDEMPOTENT_MIN_RETRIES`); alias `_closing_iterable` eliminado. `HashPartitioner` admite varias columnas; `RangePartitioner.is_rangeable` |
| G7 | `docs/api/bulk_crud.md`, `bulk_parallel.md`, `exceptions.md`, `dump.md`; funcionales (`bulk_parallel_loading`, `audit`, `bulk_audit`, `bulk_operations`, `dump_data_export`); guías (`benchmarks`, `dump_guide`, `exceptions`, `performance_*`); ejemplos; `docs/guides/api_3_0_migration.md` (nuevo, en `mkdocs.yml`); `README.md`; `.ai/architecture.md`; `docs/architecture.md` |
| G8 | Benchmarks nuevos en el banco (abajo); reglas de INSERT con umbral 50K |

## Desviaciones respecto al PLAN (justificadas)

- `ParallelOptions.min_rows_per_partition` → `min_rows` (umbral de filas para paralelizar en `"auto"`; `None` = el menor
  volumen medido de cada regla). Un mínimo por partición no estaba medido.
- `ParallelPlan` no lleva `n_partitions` ni `partitioner`: las particiones las hace quien llama (una por hilo en
  `BulkCrud` y `dump`); el particionador lo elige `BulkCrud` por el tipo de la PK.
- `max_parallel_tables` no acepta `"auto"`: no hay ninguna medición de tablas en paralelo; `"auto"` siempre daría 1.
- `ParallelOptions.mode` por defecto `"manual"` (no `"off"`): en `ParallelBulkLoader` mantiene el comportamiento 2.x; en
  `BulkCrud`, `parallel=None` es el «off» por defecto.
- `RetryOptions` va dentro de `ParallelOptions.retry` (simplificación 1 del AUDIT_PLAN).
- La creación anticipada del directorio de auditoría (PL-4) sigue en el constructor del loader, no en
  `AuditOptions.__post_init__` (un paquete no debe tener efectos en disco al construirse).
- Las reglas manuales de `dump` (aviso de MySQL/MariaDB, recorte por pool de origen y destino) siguen en el orquestador;
  la regla de SQLite y la tabla de mediciones están solo en el planificador.
- T4 verificado: las estrategias de `InsertStrategyResolver` incluidas no guardan estado por ejecución; se comparte la
  instancia y se documenta que un resolver propio debe ser thread-safe.

## Validación

| Comando | Resultado | Log |
|---|---|---|
| `pytest` (línea base, antes de cambiar nada) | 6102 passed, 532 skipped | `build/logs/baseline_v3_pytest.txt` |
| `pytest` (final, shell sin URLs del banco) | 6195 passed, 532 skipped (+93 tests nuevos) | `build/logs/v3_pytest_final.txt` |
| `pytest tests/integration` (banco, 5 motores) | 582 passed, 7 skipped; 7 de HSQLDB por falta de `JAVA_HOME` | `build/logs/v3_integration.txt` |
| `pytest tests/integration -k hsqldb` con `JAVA_HOME=jdk-25` | 7 passed | `build/logs/v3_integration_hsqldb.txt` |
| `ruff check`, `ruff format --check`, `mypy src tests/unit/test_protocol_conformance.py` | limpios (339 ficheros) | — |
| `scripts/gen_arquitectura_capas.py` | sin aristas nuevas; solo cambia el recuento (337 → 339 ficheros) | — |
| `zensical build --strict` | sin avisos; anclas nuevas comprobadas en `site/` | `build/logs/v3_docs_build.txt` |

Tests nuevos: `tests/unit/bulk/test_options.py`, `test_parallel_planner.py`, `test_crud_parallel.py`,
`tests/unit/dump/test_auto_pk_ranges.py`.

## Benchmarks (banco, 2026-10-16)

`build/logs/v3_bench_parallel_auto.txt` y `build/logs/v3_bench_oracle_threads.txt` (scripts en el scratchpad de la
sesión, sobre la tabla de `scripts/bench_bulk.py`). Resumen en `docs/guides/benchmarks.md` § «Hilos automáticos».

- `"auto"` acierta en los 5 motores: donde paraleliza, 1,55×–2,82×; donde no, el INSERT de PostgreSQL gana ≤ 1,16× y
  Oracle es inestable.
- INSERT a 50K filas: MySQL 1,82×, MariaDB 1,68×, SQL Server 2,57× → umbral de `"auto"` bajado de 200K a 50K.
- Oracle 1M: INSERT 1,33× (2–4 hilos), UPDATE ~1×, DELETE peor con 4 hilos; el INSERT en serie varió 13,4 s ↔ 27,3 s
  entre tandas. Se mantiene en serie.

## Pendiente para AUDIT_CODE

- Con `mode="off"` el loader registra un INFO «1 hilos en lugar de N».
- El UPDATE de PostgreSQL desde `BulkCrud` consulta el privilegio `TEMP` dos veces (plan de `BulkCrud` y del loader).
- La fachada paralela no cuenta las filas de la carga en `rows_committed` (documentado en `last_parallel_result`).

## Pendiente para VERSION

`pyproject.toml` 3.0.0; `CHANGELOG.md` [3.0.0] con sección de migración; `README.md`, `docs/index.md`, `docs/roadmap.md`
(versión vigente); pie de figura de `docs/architecture.md` (v3.0.0, 339 ficheros); `.ai/CURRENT_STATE.md`;
`TRACEABILITY.md` con «Directrices para Futuras IAs».
