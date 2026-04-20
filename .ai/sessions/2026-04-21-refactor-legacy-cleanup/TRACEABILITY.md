# TRACEABILITY

## Session metadata
- id: 2026-04-21-refactor-legacy-cleanup
- fecha: 2026-04-21
- rama: develop
- skill: refactor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Eliminar todo rastro legacy del proyecto. Módulo: Todo el proyecto. Política de compatibilidad: Se autoriza romper contratos públicos. Flujo: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.

## Context supplied
- `.ai/architecture.md` — arquitectura v0.6.7
- `.ai/sessions/INDEX.md` — sesiones previas
- `.ai/sessions/2026-04-20-fase3-managers/TRACEABILITY.md` — sesión Fase 3 managers (IN_PROGRESS)

## AI output summary
- Exploración exhaustiva del proyecto (agente Explore) → identificó 4 grupos de wrappers deprecated en `managers/`, property legacy en `query/`, y comentarios/docstrings con referencias PR/legacy.
- Leyó 18 archivos fuente para mapear dependencias exactas.
- **PLAN**: 5 grupos de cambios, 16 archivos, objetivo eliminar 31 funciones wrapper deprecated + property legacy + comentarios PR.
- **AUDIT_PLAN**: Identificó gap en `CharsetCollationParser` (sin soporte mariadb en `_column_charset_parsers`) como riesgo funcional. Lo incluyó en implementación.
- **G1**: Eliminados wrappers deprecated de `_metadata_cache.py` (5), `_metadata_context.py` (6), `_metadata_parser.py` (11+mariadb added), `_metadata_request.py` (6), `_manager_lifecycle.py` (3). Total: 31 funciones eliminadas.
- **G2**: Actualizados 6 consumidores para usar OOP directamente: `_manager_cache_service.py`, `_manager_shared_mixin.py`, `_manager_session.py`, `_manager_lifecycle_sync.py`, `sync_mgr.py`, `async_mgr.py`.
- **G3**: Limpiados re-exporters `_manager_metadata.py` y `_manager_metadata_runtime.py` (eliminados deprecated de `__all__` e imports).
- **G4**: Limpiado `query/queries.py` — eliminada property `queries` legacy + docstring módulo + comentarios PR internos.
- **G5**: Actualizados 2 tests: `test_manager_internal_helpers.py` (OOP directo) y `test_database_queries_refactor_pr5.py` (sin property legacy).
- **AUDIT_CODE**: ruff ✅ (0 warnings), mypy ✅ (0 errores), pytest ✅ (1881 passed, 1 skipped).

## Artefactos generados

| Artefacto | Ruta | Estado |
|-----------|------|--------|
| `_metadata_cache.py` | `src/util_bbdd/managers/` | modificado |
| `_metadata_context.py` | `src/util_bbdd/managers/` | modificado |
| `_metadata_parser.py` | `src/util_bbdd/managers/` | modificado (+ mariadb support) |
| `_metadata_request.py` | `src/util_bbdd/managers/` | modificado |
| `_manager_lifecycle.py` | `src/util_bbdd/managers/` | modificado |
| `_manager_cache_service.py` | `src/util_bbdd/managers/` | modificado |
| `_manager_shared_mixin.py` | `src/util_bbdd/managers/` | modificado |
| `_manager_session.py` | `src/util_bbdd/managers/` | modificado |
| `_manager_lifecycle_sync.py` | `src/util_bbdd/managers/` | modificado |
| `sync_mgr.py` | `src/util_bbdd/managers/` | modificado |
| `async_mgr.py` | `src/util_bbdd/managers/` | modificado |
| `_manager_metadata.py` | `src/util_bbdd/managers/` | modificado |
| `_manager_metadata_runtime.py` | `src/util_bbdd/managers/` | modificado |
| `query/queries.py` | `src/util_bbdd/query/` | modificado |
| `test_manager_internal_helpers.py` | `tests/unit/` | modificado |
| `test_database_queries_refactor_pr5.py` | `tests/unit/` | modificado |

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Sesión `2026-04-20-fase3-managers` sigue IN_PROGRESS (Fase 3 managers v0.6.9 no completada en esta sesión).
