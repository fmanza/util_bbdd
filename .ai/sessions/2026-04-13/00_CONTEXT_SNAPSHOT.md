# CONTEXT SNAPSHOT

## Contexto del repositorio revisado

- `.ai/architecture.md` — arquitectura v0.6.7, jerarquía 3 niveles, responsabilidades de `_core/` y `core/`
- `.ai/sessions/INDEX.md` — inventario de sesiones previas
- `.ai/sessions/2026-04-10/TRACEABILITY.md` — sesión previa que eliminó `_foundation/` y consolidó `_core/`
- `src/util_bbdd/_core/__init__.py` — contrato público del módulo (no exporta `capabilities`)
- `src/util_bbdd/_core/capabilities.py` — fichero bajo auditoría
- `src/util_bbdd/_core/types.py`, `exceptions.py`, `contracts.py`, `constants.py`
- `src/util_bbdd/core/__init__.py` — contrato público del módulo
- `src/util_bbdd/core/capabilities.py` — fichero canónico según arquitectura
- `src/util_bbdd/connection/factory.py` — consumidor Level 2 de `_core.capabilities`
- `src/util_bbdd/factory/pool_factory.py` — consumidor Level 2 de `_core.capabilities`
- `tests/unit/test_engine_capabilities.py` — test que importa de `core.capabilities`

## Estado actual observado

- Tests: estado previo a esta sesión: 1703 passed / 1 skipped (sesión 2026-04-10). No ejecutados en esta sesión (solo auditoría).
- Lint / mypy: limpio al cierre de sesión 2026-04-10 (0 errores mypy, 241 ficheros).
- Cambios locales pre-existentes: ninguno (rama develop limpia).

## Estado Git relevante

- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: v0.6.7 (commit 12ef34f)

## Clasificación metodológica

- Tipo principal: audit-code
- Estado real de alcance: acotado (dos módulos específicos)
- Consecuencia: pendiente decisión del usuario sobre si ejecutar IMPLEMENT (fix es mínimo y de bajo riesgo)

## Gate G0 · Context Ready

Veredicto: GO
Condiciones pendientes:
- Ninguna para la fase de auditoría.
- Si se aprueba IMPLEMENT: ejecutar ruff + mypy + pytest tras el fix.
