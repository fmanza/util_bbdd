# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.github/prompts/audit_module.prompt.md`, `.github/prompts/new_feature.prompt.md`, `.github/agents/plan-architect.agent.md`
- `.ai/audit/audit_module_baseline_inventory.md` (línea base `INV-*`, huecos `H-*`)
- `.ai/architecture.md` § Capas, `.github/instructions/architecture.instructions.md` § Regla #6, `scripts/gen_arquitectura_capas.py` (`LAYER`, `DRAWN`)
- `src/util_bbdd/bulk/audit.py`, `bulk/_audit/*`, `bulk/_support/persistence.py`, `bulk/_support/rejects.py`, `bulk/_support/excel.py`, `bulk/_execution/parallel_loader.py`, `bulk/crud.py`
- `src/util_bbdd/dump/_audit_summary.py`, `dump/_models.py`, `dump/orchestrator.py`, `dump/reporters.py`
- `src/util_bbdd/migrate/ir/models.py`, `migrate/planner.py`, `migrate/views/validation.py`, `migrate/reporters/*`
- `src/util_bbdd/_core/exceptions.py`, `src/util_bbdd/_core/export_safety.py`
- Tests que dependen de rutas privadas de la auditoría (grep en `tests/`)
- Externas: OpenTelemetry DB semantic conventions; OWASP Logging Cheat Sheet; OWASP CSV Injection

## Estado actual observado
- Versión `0.28.0` (`pyproject.toml`). Última sesión cerrada: `2026-10-02b-fix-audit-isolate` (5993 unit / 582 integración).
- No se ejecutan tests en esta sesión (solo lectura de código).
- `bulk`, `dump` y `migrate` no tienen código `async`: la auditoría es síncrona.
- Ni `bulk` ni `dump` usan `multiprocessing` ni `pickle`: la concurrencia es solo con hilos.

## Estado Git relevante
- Rama activa: develop
- Cambios locales previos: los artefactos de configuración de esta misma tarea (`.github/prompts/audit_module.prompt.md`, `.ai/audit/audit_module_baseline_inventory.md`, `.github/AGENTS.md`), sin commit.
- Último tag / versión publicada: v0.28.0 (`12d055c`)

## Clasificación metodológica
- Tipo principal: new_feature (paquete nuevo + extracción de código existente sin cambio funcional)
- Estado real de alcance: acotado (3 consumidores, fases incrementales)
- Consecuencia: PLAN + AUDIT_PLAN; IMPLEMENT solo tras aprobación por fases.

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes (si aplica):
- Ninguna para PLAN. Los inputs del prompt se toman por defecto (declarados como supuestos en el PLAN).
