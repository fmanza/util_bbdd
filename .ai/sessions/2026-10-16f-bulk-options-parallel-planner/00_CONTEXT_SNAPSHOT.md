# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.ai/architecture.md` (mapa de `bulk/` y `dump/`), `docs/architecture.md` (capas, Regla #6)
- `src/util_bbdd/bulk/crud.py`, `bulk/_execution/parallel_loader.py`, `range_partitioner.py`, `insert_strategies.py`
- `src/util_bbdd/dump/_models.py` (`DumpConfig`), `dump/orchestrator.py` (paralelismo por tablas y rangos)
- `docs/guides/benchmarks.md` (mediciones de la carga paralela: 200K/1M, 1/2/4 hilos), `docs/api/dump.md` (Q4)
- `.github/prompts/new_feature.prompt.md`, `refactor.prompt.md`, `.github/agents/plan-architect.agent.md`

## Estado actual observado
- Tests: `pytest` 6102 passed, 532 skipped (shell sin URLs del banco; `build/logs/baseline_v3_pytest.txt`).
- Uso de la API a migrar (inventario `ast`): 245 construcciones de `BulkCrud` y 106 de `ParallelBulkLoader` en tests;
  8 llamadas con `**kwargs`; ninguna con posicionales tras `engine`.
- Sonar S107 (máximo 13 parámetros) avisaba en `ParallelBulkLoader.__init__` (18) y `BulkCrud.__init__` (17).

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: v2.2.4 (`75f24ae7`)

## Clasificación metodológica
- Tipo principal: new_feature (planificador, fachada paralela) + refactor incompatible (paquetes de opciones)
- Estado real de alcance: mezclado por petición explícita del usuario; ejecutado por grupos G1–G8
- Consecuencia: versión MAJOR 3.0.0 con guía de migración

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes (si aplica):
- Ninguna
