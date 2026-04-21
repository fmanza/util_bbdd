# TRACEABILITY — Tech Debt comparar/ + doc/

**Sesión:** 2026-04-21-tech-debt-comparar-doc
**Estado:** CLOSED
**Fecha cierre:** 2026-04-21
**Skill:** tech-debt

## Fases ejecutadas

| Fase | Artefacto | Estado |
|------|-----------|--------|
| PLAN | `01_TECH_DEBT_AUDIT.md` (sección PLAN) | ✅ |
| AUDIT_PLAN | `01_TECH_DEBT_AUDIT.md` (sección AUDIT_PLAN) | ✅ |
| AUDIT_CODE | `01_TECH_DEBT_AUDIT.md` (sección AUDIT_CODE) | ✅ |
| VERSION | N/A (scope: solo análisis) | — |

## Veredicto global

**DEUDA_SIGNIFICATIVA** — 15 ítems en comparar/, 6 en doc/. Tres quick wins de correctitud (C13 doble `;`, C15 routines modified, QW-6 atributos instancia) listos para Fase 1 de v0.8.1.

## Próximos pasos sugeridos

1. PR de Fase 1 (Quick Wins): commits atómicos por ítem
2. PR de Fase 2 (correctitud + tests): C12, C15, D2, D6
3. Issue de arquitectura para Fase 3: C3+C9 (RoutineFetcherRegistry), D1 (DatabaseDocumentation factory)

## Cambios implementados

**Implementación completada 2026-04-21** — 1969 tests passed, 1 skipped. Ruff clean. Mypy strict clean.

### PR-1 — Quick Wins (comparator.py)
- C1: Logging unificado — `logger.debug` → `self.logger.debug` en `_compare_routines`; `logging.getLogger().warning` → `logger.warning` en `_get_view_definition_safe`
- C2: `_ROUTINE_FETCHERS.update({})` → asignación directa `= {}`
- C6: Eliminados métodos dead code `_compare_columns` y `_compare_comments`
- C7: Eliminado fallback SA 1.4 `getattr(inspector, "bind", None)` (5 ocurrencias)

### PR-1 — Quick Wins (sql_reporter.py)
- C13: Corregido doble `;` en `_render_add_column_with_type:683`

### PR-2 — Correctitud + Seguridad
- C8: Añadido `_is_safe_identifier()` en `SchemaComparator`; aplicado en `_get_routines_mariadb` para procedures y functions
- C12: Reset de caches `_col_cache/_fk_cache/_idx_cache/_col_error_cache` al inicio de `render()`
- C15: `_render_single_routine_diff` para `modified` emite `DROP IF EXISTS` antes de recrear en dialectos sin `CREATE OR REPLACE PROCEDURE` (mariadb, mysql, sqlserver, generic)

### PR-3 — Excepciones + render_all
- C10: `render_all` acepta `raise_on_error: bool = False`; si `True`, relanza la excepción en lugar de silenciarla
- D6: Añadidas `DocumentationError`, `DocumentationConfigError`, `DocumentationRenderError` en `_core/exceptions.py`; exportadas desde `__init__.py` raíz

### Deuda NO implementada (Fase 3 — requiere PLAN propio)
- C3: SRP SchemaComparator — fetchers inline
- C9: DdlNormalizer duplicación
- D1: DatabaseDocumentation I/O en constructor
- D4/D5: Ports circulares/granularidad

Documentación creada en:
- `.ai/sessions/2026-04-21-tech-debt-comparar-doc/`
- `docs/v0.8.1/TECH_DEBT_v0.8.1.md`
