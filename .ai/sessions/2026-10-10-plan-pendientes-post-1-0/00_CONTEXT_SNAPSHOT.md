# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.ai/CURRENT_STATE.md` (cabecera, tabla de versiones, «Próximos pasos»)
- `docs/roadmap.md`
- `.ai/sessions/2026-10-10-api-1-0-final/TRACEABILITY.md` y `02_DOC_REVIEW.md`
- `.ai/sessions/2026-10-10-plan-pendientes-global/PLAN_AUDIT_PLAN.md` y `Q6_PLAN_API_1_0.md` (A5)
- `src/util_bbdd/bulk/crud.py` (estructura, constructor, propiedades, `maintenance_scope`), `bulk/_support/`,
  `bulk/_execution/`, `audit/legacy_csv.py`, `audit/files.py`, `dump/_models.py`, `dump/orchestrator.py`,
  `dump/reporters.py`
- `tests/_core/test_batching.py`, `tests/unit/bulk/test_parallel_loader*.py`,
  `tests/unit/connection/test_performance_advisor_once.py`, `tests/comparar/test_comparator.py`
- `.github/workflows/*.yml`, `mkdocs.yml` (nav de rendimiento y constraints)

## Estado actual observado
- Tests (v1.0.0, según `CURRENT_STATE`): sin banco 5678 passed, 523 skipped; con banco 6194 passed, 7 skipped;
  cobertura 91 %; mypy limpio (332 ficheros). No se re-ejecuta la puerta en esta sesión (solo lectura); sí una suite
  completa con `--cov` + `tracemalloc` para el ítem 4 (`build/logs/postv1_fullcov_tracemalloc.txt`).
- Lint / mypy: sin cambios de código desde v1.0.0.
- Cambios locales ajenos: `.ai/sessions/2026-10-10-api-1-0-final/NEXT_SESSION_PROMPT.md` sin seguimiento (del usuario;
  no se toca).

## Estado Git relevante
- Rama activa: `develop` = `origin/develop` = `158903b6` (tag `v1.0.0` en origin, también `v0.43.0` y `v0.44.0`).
- `main` = `origin/main` = `3c94ca4a` (v0.42.1); `main` es ancestro de `develop`: 10 commits, fast-forward posible.
- `origin/HEAD` → `origin/main`: la rama por defecto de GitHub muestra aún v0.42.1.
- 8 ramas `origin/dependabot/*` (2026-03-31 a 2026-06-23); rama local `migrate/zenical-pure` ya fusionada (PR #19).
- Último tag: `v1.0.0`.

## Clasificación metodológica
- Tipo principal: planificación multi-flujo (refactor, new_feature, test, docs, chore, release).
- Estado real de alcance: pendiente de descomposición → se descompone en bloques B0–B7 con un flujo cada uno.
- Consecuencia: no se mezcla refactor (A5) con new_feature (rutas `str`) en el mismo commit ni en la misma fase.

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes (si aplica):
- Ninguna para PLAN/AUDIT_PLAN. Los externos (PR #18, CI en GitHub) no son verificables aquí.
