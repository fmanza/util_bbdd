# TRACEABILITY

## Session metadata
- id: 2026-10-16g-tech-debt-parallel-followups
- fecha: 2026-10-16
- rama: develop (base `84b3264c`, tag `v3.0.0`)
- skill: tech_debt, VERSION v3.0.1
- fase: PLAN + AUDIT_PLAN → IMPLEMENT (recomendaciones) → AUDIT_CODE → VERSION

## Prompt issued
«PLAN y AUDIT_PLAN de» la deuda menor anotada en el AUDIT_CODE de v3.0.0 (TEMP consultado dos veces, INFO de
auditoría deshabilitada por carga, filas paralelas fuera de `rows_committed`, `MAX − MIN + 1` en `dump`, reglas de
Oracle inestables). Después: «IMPLMENTE con las recomendaciones y autorizo benchmarks D5» y «si» (VERSION, commit, tag y
push).

## Context supplied
- `.github/prompts/tech_debt.prompt.md`; `03_AUDIT_CODE.md` de la sesión `2026-10-16f-bulk-options-parallel-planner`.
- Código de `bulk/crud.py`, `bulk/_execution/parallel_loader.py`, `staging_update.py`, `dump/orchestrator.py`.
- Memoria: banco, `JAVA_HOME` de HSQLDB, Bash pierde barras invertidas, Oracle inestable.

## AI output summary
- PLAN (`01_PLAN_AUDIT_PLAN.md`): D1 son N+2 consultas, no 2; D3 no es deuda; D4 puede usar el `COUNT(*)` ya existente.
  `DEUDA_MENOR`, GO_CONDICIONAL.
- IMPLEMENT + AUDIT_CODE (`02_IMPLEMENT_AUDIT_CODE.md`): D1 (caché del loader + traspaso desde la fachada), D2
  (`warn_if_disabled`), D3 (docs), D4 (`rows_hint`), D5 (`scripts/bench_parallel.py` y Oracle medido: no gana). 16 tests
  nuevos. `LIMPIO`.
- VERSION 3.0.1: CHANGELOG, `pyproject.toml`, `README.md` (2), `docs/index.md`, `docs/roadmap.md`, pie de
  `docs/architecture.md`, `CURRENT_STATE` (también el tag de 3.0.0, ya creado), `INDEX`, `SESSIONS_DIGEST`.

## Tests and evidence
- `build/logs/td_pytest.txt`: 6219 passed, 532 skipped (sin URLs del banco).
- `build/logs/td_integration.txt`: `tests/integration` 589 passed, 7 skipped (6 motores, `JAVA_HOME=jdk-25`).
- `ruff`, `mypy` (339 ficheros), `zensical build --strict`, `scripts/gen_arquitectura_capas.py`: limpios.
- `build/logs/td_bench_oracle_abab.txt`: Oracle 200K/1M, 1/2/4 hilos, 5 tandas alternas.

## Known limitations
- La fachada accede a un atributo privado del loader (`_temp_tables_allowed`), dentro del paquete `bulk`.
- `scripts/bench_parallel.py` mezcla en la salida estándar los tiempos de `util.timing.medir_tiempo` (usar `--out`).

## Rollback
- `git revert` de los dos commits de la sesión. Sin cambios de API ni de datos; D4 vuelve a la cota `MAX − MIN + 1`.

## Directrices para Futuras IAs
- **[bulk]**: el privilegio `TEMP` de PostgreSQL se comprueba en tres sitios con funciones distintas: la fachada
  (`BulkCrud.parallel_plan`, para el plan), el loader (`_staging_update_available`, cacheado por instancia y rellenado
  por la fachada) y cada worker (`StagingUpdateStrategy`, en su sesión: es la comprobación que decide la vía de cada
  lote y no debe quitarse).
- **[bulk]**: `AuditOptions.warn_if_disabled` controla también el INFO por carga de `ParallelBulkLoader`.
- **[bulk]**: `rows_committed`/`last_operation_rows_committed` son el prefijo confirmado para reanudar; no sumar filas
  de cargas paralelas (las particiones no forman un prefijo).
- **[dump]**: con `parallel_pk_ranges="auto"`, `_load_in_pk_ranges` recibe `rows_hint` (el `COUNT(*)` de
  `collect_row_counts`, `-1` si no se contó) y planifica con `min(MAX − MIN + 1, rows_hint)`.
- **[benchmarks]**: las reglas de `ParallelPlanner.RULES` se validan con `scripts/bench_parallel.py` (calentamiento,
  tandas alternas, criterio ≥ 1,5× sin solape de IQR). En Oracle 23 Free, sin calentamiento los tiempos son erráticos.
- **[herramientas]**: en scripts Python escritos con heredoc de Bash, `"\\n"` pierde la barra y queda un salto de línea
  real dentro de la cadena (error de sintaxis); escribir esos scripts con Write.

## Verdict
CLOSED
