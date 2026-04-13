# TRACEABILITY

## Session metadata

- id: 2026-04-13
- fecha: 2026-04-13
- rama: develop
- skill: audit-code
- fase: PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION

## Prompt issued

```
Carpetas a revisar
    src\util_bbdd\_core
    src\util_bbdd\core

Contexto
    Identificar el motivo por el que se dispone de dos módulos core

Lee .ai/architecture.md antes de proponer cambios
Lee .ai/sessions/INDEX.md para contexto de decisiones previas

Documentar la sesión actual siguiendo .ai\sessions\INDEX.md
```

## Context supplied

- `.ai/architecture.md`
- `.ai/sessions/INDEX.md`
- `.ai/sessions/2026-04-10/TRACEABILITY.md`
- Todos los ficheros de `src/util_bbdd/_core/` (5 ficheros .py)
- Todos los ficheros de `src/util_bbdd/core/` (2 ficheros .py)
- Grep de consumidores: `connection/factory.py`, `factory/pool_factory.py`, `tests/unit/test_engine_capabilities.py`

## AI output summary

- Leídos `.ai/architecture.md` y `.ai/sessions/INDEX.md` como prerequisito.
- Listados y leídos todos los ficheros de `_core/` (5 py) y `core/` (2 py).
- Grepeados consumidores de `is_async_supported` y `DB_ASYNC_CAPABILITIES` en todo `src/`.
- Detectado: `_core/capabilities.py` y `core/capabilities.py` son byte-a-byte idénticos.
- Detectado: producción importa de `_core.capabilities`; tests importan de `core.capabilities`.
- Consultada sesión 2026-04-10: la eliminación de `_foundation/` no abordó `_core/capabilities.py`, que fue el origen de la duplicación.
- Emitido PLAN, AUDIT_PLAN, AUDIT_CODE con hallazgo central y veredicto.
- Emitido commit message y pruebas sugeridas para el fix pendiente.
- Documentada sesión (artefactos en `.ai/sessions/2026-04-13/`).
- Actualizado `.ai/sessions/INDEX.md` con entrada 2026-04-13.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-04-13/00_REQUEST.md` | emitido |
| CONTEXT_SNAPSHOT | `.ai/sessions/2026-04-13/00_CONTEXT_SNAPSHOT.md` | emitido |
| TRACEABILITY | `.ai/sessions/2026-04-13/TRACEABILITY.md` | emitido |
| INDEX actualizado | `.ai/sessions/INDEX.md` | modificado |
| `_core/capabilities.py` eliminado | `src/util_bbdd/_core/capabilities.py` | eliminado |
| `connection/factory.py` import redirigido | `src/util_bbdd/connection/factory.py:13` | modificado |
| `factory/pool_factory.py` import redirigido | `src/util_bbdd/factory/pool_factory.py:15` | modificado |

## Hallazgo principal

`_core/capabilities.py` es un duplicado exacto de `core/capabilities.py` introducido accidentalmente.
- `architecture.md` no lo menciona en el contrato de `_core/`.
- `_core/__init__.py` no lo exporta.
- Los consumidores de producción usan `_core.capabilities`; los tests usan `core.capabilities`.
- Riesgo: si se actualiza un motor en un dict y no en el otro, producción y tests divergen silenciosamente.

## Fix recomendado (pendiente aprobación)

1. `connection/factory.py:13` — cambiar `from .._core.capabilities` → `from ..core.capabilities`
2. `factory/pool_factory.py:15` — mismo cambio
3. Eliminar `src/util_bbdd/_core/capabilities.py`

Commit: `fix: eliminate duplicate capabilities — consolidate to core/capabilities.py`

## Validación post-IMPLEMENT

- ruff check src tests: ✓ (0 errores — reorden de imports necesario en factory.py y pool_factory.py)
- mypy src: ✓ (0 errores)
- pytest tests/: ✓ 1703 passed / 1 skipped

## Veredicto final

Veredicto: CLOSED
Pendientes al cierre: ninguno.
