# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (P-05) y `02_BASELINE_MOTORES_REALES.md`
- `src/util_bbdd/bulk/_execution/batch.py`: `_DEFAULT_SQL_BASED_DELETE_DIALECTS`, `SqlBasedDeleteStrategy`, `GenericDeleteStrategy`, `DeleteStrategyResolver`, `DeleteBatchExecutor`
- `tests/unit/test_bulk_internal_helpers.py` (tests existentes de las estrategias DELETE, con dialecto MySQL)
- `tests/integration/test_bulk_engines.py` (`xfail(strict=True)` de P-05)

## Estado actual observado
- Árbol limpio tras `ece985f` (hotfix P-18 + P-01) y `9c79a17`.
- Contenedores del banco (`util_bbdd_bench_*`) en marcha; ODBC Driver 18 en el host.

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: v0.10.0 (release 0.11.0 en `CHANGELOG.md`)

## Clasificación metodológica
- Tipo principal: hotfix
- Estado real de alcance: acotado (1 clase)
- Consecuencia: se procede.

## Gate G0 · Context Ready
Veredicto: GO
