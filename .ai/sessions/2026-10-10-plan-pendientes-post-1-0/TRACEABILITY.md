# TRACEABILITY

## Session metadata
- id: 2026-10-10-plan-pendientes-post-1-0
- fecha: 2026-10-10
- rama: develop (base v1.0.0, `158903b6`)
- skill: planificación (PLAN + AUDIT_PLAN)
- fase: PLAN + AUDIT_PLAN (detenida a la espera de aprobación)

## Prompt issued
«Sesión nueva: PLAN + AUDIT_PLAN de los pendientes de util_bbdd tras v1.0.0» (texto completo saneado en
`00_REQUEST.md`; origen: `.ai/sessions/2026-10-10-api-1-0-final/NEXT_SESSION_PROMPT.md`).

## Context supplied
- `.ai/CURRENT_STATE.md`, `docs/roadmap.md`
- `.ai/sessions/2026-10-10-api-1-0-final/TRACEABILITY.md`, `02_DOC_REVIEW.md`
- `.ai/sessions/2026-10-10-plan-pendientes-global/PLAN_AUDIT_PLAN.md`, `Q6_PLAN_API_1_0.md`

## AI output summary
- P1: `git rev-parse`, `merge-base --is-ancestor`, `ls-remote --tags`: FF de 10 commits posible; tags 0.43.0, 0.44.0 y
  1.0.0 ya en origin; `origin/HEAD` → `main`.
- P2: estructura de `bulk/crud.py` (1943 líneas, 63 métodos); la auditoría y los rechazos ya están delegados; el bloque
  grande que queda es `maintenance_scope` (~375 líneas). `grep _BulkCrud__` en tests: 11 ficheros, 4 nombres, ninguno
  de los que se moverían.
- P3: sonda en directorio temporal (`build/logs/postv1_probe_paths.txt`) + trazas de `DumpOrchestrator.run()`:
  `output_dir=str` carga los datos y falla al escribir el informe sin `DumpResult`.
- P4: subconjunto con y sin `--cov` (`postv1_resourcewarnings_subset_{cov,nocov}.txt`), `PYTHONTRACEMALLOC=25`
  (`postv1_resourcewarnings_tracemalloc.txt`) y suite completa con `--cov` + `tracemalloc`
  (`postv1_fullcov_tracemalloc.txt`: 5678 passed, 523 skipped, 340 `ResourceWarning` + 3 `SADeprecationWarning`),
  agrupado por fichero de test con un script del scratchpad (`postv1_resourcewarnings_by_origin.txt`: 40 ficheros).
- P5: listado de `docs/`, barrido de símbolos retirados y de instalación por PyPI.
- P6/P7/N1/N2: lectura de `CURRENT_STATE`, `ls-remote refs/pull/*`, disparadores de `.github/workflows/*.yml`, ramas
  `origin/dependabot/*`.
- Emitido `PLAN_AUDIT_PLAN.md` (inventario P1–P7, N1–N2, O1; decisiones D1–D6; bloques B0–B7; AUDIT_PLAN
  GO_CONDICIONAL). Sin cambios en `src/`, `tests/` ni `docs/`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-10-10-plan-pendientes-post-1-0/00_REQUEST.md` | emitido |
| CONTEXT SNAPSHOT | `.ai/sessions/2026-10-10-plan-pendientes-post-1-0/00_CONTEXT_SNAPSHOT.md` | emitido |
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-10-plan-pendientes-post-1-0/PLAN_AUDIT_PLAN.md` | GO_CONDICIONAL |
| Logs | `build/logs/postv1_*` | emitido |

## Directrices para Futuras IAs
- **[bulk]**: la auditoría de `BulkCrud` vive en `bulk/_support/persistence.py` (`BulkPersistenceManager`) y los
  rechazos en `bulk/_support/rejects.py` (`RejectsWriter`, `Isolator`); lo más grande que queda en `crud.py` es
  `maintenance_scope` (líneas 1492–1866 en v1.0.0).
- **[tests]**: los `ResourceWarning: unclosed database` con `--cov` vienen de Engines SQLite creados en tests sin
  `dispose()`; aparecen en el test que hace `gc.collect()` (`test_performance_advisor_once.py:94`), no en el que fuga.
  Localizar con `PYTHONTRACEMALLOC=25` (con `python -I` se ignora: usar el intérprete sin `-I`).
- **[dump]**: un fallo no previsto en `DumpExcelReporter` (p. ej. `TypeError`) escapa de `DumpReportError` y se pierde
  el `DumpResult` aunque los datos ya estén cargados.

## Veredicto final
Veredicto: GO_CONDICIONAL (PLAN + AUDIT_PLAN; a la espera de D1–D6)
Pendientes al cierre:
- Respuesta del usuario a D1–D6 y autorización para B1.
