# TRACEABILITY

## Session metadata
- id: 2026-10-16f-bulk-options-parallel-planner
- fecha: 2026-10-16
- rama: develop (base `75f24ae7`, v2.2.4)
- skill: new_feature + refactor incompatible (alcance mixto pedido explícitamente), VERSION v3.0.0
- fase: análisis → PLAN + AUDIT_PLAN (opción B) → IMPLEMENT (D1–D3 recomendadas) → AUDIT_CODE → VERSION

## Prompt issued
Estrategia para que la ejecución de `bulk/_execution/parallel_loader.py` se decida automáticamente con un algoritmo
optimizado, con parámetros de la API de `BulkCrud` en paquetes compactados (recibía más de 13); implicaciones en `bulk`
y `dump`; por qué hay funciones fuera de la clase en `parallel_loader.py`. Después: «PLAN y AUDIT_PLAN con B»,
«IMPLEMENT acepto recomendaciones», «Si lo necesitas puedes ejecutar nuevos benchmarks», «Si» (AUDIT_CODE) y
«VERSION y commit».

## Context supplied
- `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md`; prompts `new_feature` y `refactor`; agente Plan Architect.
- Código de `bulk/`, `dump/`, `_core/validation`, `docs/guides/benchmarks.md` (mediciones de la carga paralela).
- Memoria del proyecto: banco (contraseña de los contenedores, SQL Server en 51833, `JAVA_HOME` de HSQLDB), no usar
  `git add -A`, puerta también sin URLs del banco.

## AI output summary
- Análisis: `dump` no decide el nº de hilos (lo recorta y particiona); reglas por motor dispersas; 3 copias manuales de
  los parámetros de `BulkCrud` (los workers perdían `insert_resolver`, `update_via_staging`, `prefetch_blocks`); el
  «13» de la solicitud es el límite de Sonar S107.
- PLAN/AUDIT_PLAN (`01_PLAN_AUDIT_PLAN.md`): opción B, MAJOR 3.0.0, GO_CONDICIONAL (D1–D3, T4).
- IMPLEMENT (`02_IMPLEMENT.md`): `bulk/options.py`, `bulk/_execution/parallel_planner.py`, fachada paralela en
  `BulkCrud`, loader por paquetes con `_plan()`, `ParallelLoadError`, `parallel_pk_ranges="auto"`, reubicación de las
  funciones sueltas; migración `ast` de 241 llamadas + 6 manuales; documentación y guía de migración.
- Benchmarks en el banco (autorizados): validación de `"auto"` en 5 motores y umbral del INSERT 200K → 50K; Oracle 1M
  con 1/2/4 hilos (se mantiene en serie).
- AUDIT_CODE (`03_AUDIT_CODE.md`): 5 hallazgos corregidos (A1–A5) con tests; 5 de deuda menor; GO.
- VERSION 3.0.0: CHANGELOG (Removed/Added/Changed/Fixed/Performance/Tests), `pyproject.toml`, `README.md`,
  `docs/index.md`, `docs/roadmap.md`, pie de `docs/architecture.md` (339 ficheros), `CURRENT_STATE`, `INDEX`,
  `SESSIONS_DIGEST`.

## Tests and evidence
- `build/logs/baseline_v3_pytest.txt`: línea base 6102 passed, 532 skipped.
- `build/logs/v3_pytest_audit.txt`: 6203 passed, 532 skipped (shell sin URLs del banco).
- `build/logs/v3_integration_audit.txt`: `tests/integration` 589 passed, 7 skipped (6 motores, `JAVA_HOME=jdk-25`).
- `ruff check`, `ruff format --check`, `mypy src tests/unit/test_protocol_conformance.py` (339 ficheros): limpios.
- `scripts/gen_arquitectura_capas.py`: sin aristas nuevas. `zensical build --strict`: sin avisos.
- `build/logs/v3_bench_parallel_auto.txt`, `build/logs/v3_bench_oracle_threads.txt`: benchmarks.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST / CONTEXT | `.ai/sessions/2026-10-16f-bulk-options-parallel-planner/00_*.md` | emitido |
| PLAN + AUDIT_PLAN | `01_PLAN_AUDIT_PLAN.md` | emitido |
| IMPLEMENT | `02_IMPLEMENT.md`; `src/util_bbdd/bulk/options.py`, `bulk/_execution/parallel_planner.py` y 16 ficheros de `src/` | completado |
| AUDIT_CODE | `03_AUDIT_CODE.md` | GO |
| Guía de migración | `docs/guides/api_3_0_migration.md` | completado |

## Known limitations
- La carga paralela desde `BulkCrud` no es atómica (documentado; `ParallelLoadError`).
- `max_parallel_tables` no tiene modo `"auto"` (sin mediciones de tablas en paralelo).
- Reglas de Oracle basadas en Oracle 23 Free (2 hilos de CPU, tiempos inestables).
- Deuda D1–D5 de `03_AUDIT_CODE.md`.

## Rollback
- `git revert` del commit de release. Es una MAJOR: quien ya haya migrado a 3.0 tendría que volver a los parámetros
  sueltos (la guía de migración sirve en sentido inverso). Sin cambios de datos ni de formato de CSV.

## Directrices para Futuras IAs
- **[bulk]**: `bulk/options.py` es el único punto de las opciones de `BulkCrud` y `ParallelBulkLoader`. Una opción
  nueva se añade a un paquete (no como parámetro suelto) y llega sola a los workers vía `BulkOptions.for_worker`.
- **[bulk]**: `ParallelPlanner.RULES` (`bulk/_execution/parallel_planner.py`) es la única tabla de reglas de
  rendimiento de la carga paralela (bulk y dump). Criterio: ≥ 1,5× en la medición, hilos del mejor tiempo, desde el
  menor volumen medido; lo no medido va en serie. Al repetir benchmarks, actualizar la regla y su `evidence`.
- **[bulk]**: separación política/mecanismo: el planificador no ejecuta SQL; los hechos (pool, `TEMP`) los obtiene el
  llamador. Reglas de seguridad (todos los modos) frente a reglas medidas (solo `"auto"`).
- **[bulk]**: `ParallelBulkLoader` importa `BulkCrud`; la fachada paralela de `BulkCrud` importa el loader de forma
  diferida (en `__load_partitions`) para evitar el ciclo.
- **[bulk]**: la fachada paralela va en serie con `generar_sql`, dentro de `bulk_session()`, de `rejects_scope()` y en
  `*_from_chunks`. UPDATE/DELETE por rangos solo con PK única entera/datetime sin repetidos; si no, `HashPartitioner`.
- **[dump]**: `DumpConfig` sigue con campos planos (decisión D1); `DumpOrchestrator._bulk_options()` es el único
  traductor a los paquetes de `bulk`.
- **[herramientas]**: para migrar llamadas a una API nueva, un script `ast` que reescribe solo el texto de la llamada
  (posiciones de `ast`) funciona, pero **pierde los comentarios dentro de los argumentos**: revisar el diff buscando
  líneas `-` con `#`. Los heredocs largos con comillas fallan en el Bash de este entorno: escribir el script con Write.
- **[banco]**: Oracle 23 Free da tiempos inestables entre tandas (memoria `reference-oracle-free-bench-unstable`).

## Verdict
CLOSED
