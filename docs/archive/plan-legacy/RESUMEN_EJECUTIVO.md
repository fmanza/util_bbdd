# 📋 Resumen Ejecutivo: Refactorización util_bbdd

## 📌 Objetivo

Refactorizar `util_bbdd` sin backward compatibility para:
1. **Unificar acceso a consultas SQL** mediante `QueryRegistry` + `QueryResolver`
2. **Separar responsabilidades** (SRP): obtener query ≠ ejecutar query ≠ validar query
3. **Crear Executors desacoplados** para sync y async con contrato unificado
4. **Validación avanzada por motor** consultando `database_types.json`
5. **Completar AsyncDatabaseManager** con métodos faltantes
6. **Documentación clara** de breaking changes

## 🎯 Resultado esperado

```
Antes (estado actual):
├─ DatabaseManager (sync)
├─ AsyncDatabaseManager (async, incompleto)
├─ DatabaseQueries (5 responsabilidades mezcladas)
├─ database_manager.py & async_database_manager.py (duplicación)
└─ Validación inconsistente (sin `raise ... from err`)

Después (refactorizado):
├─ QueryRegistry (centraliza sql_queries.json)
├─ QueryResolver (resuelve + valida con SRP)
├─ SyncQueryExecutor (ejecuta sync)
├─ AsyncQueryExecutor (ejecuta async)
├─ DatabaseTypeValidator (validadores por motor)
├─ DatabaseManager (refactorizado, API compat)
├─ AsyncDatabaseManager (completo + métodos nuevos)
└─ DatabaseQueries (ahora es convenience layer)
```

## 📊 Estructura de PRs

| PR | Nombre | Duración | Cambios | Tests |
|----|--------|----------|---------|-------|
| 0 | Preparación | 2-3h | Models + Exceptions + QueryRegistry | 20+ |
| 1 | Query Resolver | 4-5h | QueryResolver + 6 Validadores | 40+ |
| 2 | Sync Executor | 4-5h | SyncQueryExecutor + refactor DatabaseManager | 30+ |
| 3 | Async Executor | 4-5h | AsyncQueryExecutor + Completude AsyncDatabaseManager | 30+ |
| 4 | Validadores avanzados | 3-4h | Reglas por motor desde database_types.json | 20+ |
| 5 | SRP database_queries.py | 3-4h | Decomponer + conveniencia | 20+ |
| 6 | Documentación | 2-3h | README + CHANGELOG + E2E tests | 10+ |

**Total estimado:** 23-28 horas de desarrollo

## 🚀 Cómo ejecutar

```bash
# 1. Revisar plan detallado
cat docs/ANALISIS_REFACTORIZACION_PR_FASES.md

# 2. Consultar checklists ejecutables
cat docs/PLAN_EJECUCION_CHECKLISTS.md

# 3. Comenzar PR 0
# - Crear src/util_bbdd/models.py
# - Expandir database_exceptions.py
# - Crear src/util_bbdd/query_registry.py
# - Tests en tests/unit/test_query_registry.py

pytest tests/unit/test_query_registry.py -v
```

## 🔄 Estado

- **Documentación:** ✅ Completa
- **PR 0:** 🔄 Por ejecutar
- **PR 1-6:** 🔄 Pendientes

## ⚠️ Breaking Changes

- `DatabaseQueryError` → nuevo alias de `QueryNotFoundError`
- Métodos eliminados: `analyze_query_parameters()`, `validate_query_parameters()` (from `DatabaseQueries`)
- Nuevas excepciones: `QueryNotFoundError`, `QueryValidationError`, `QueryParameterError`, etc.
- Nueva API: `execute_query(query_name, **params)` en managers

## 📚 Documentación generada

1. **ANALISIS_REFACTORIZACION_PR_FASES.md** (150+ líneas)
   - Análisis detallado de estado actual
   - 10 decisiones de diseño (ADR-style)
   - Modelo unificado de queries
   - Validación por motor
   - Plan de 7 PRs con checklists exactos
   - Tests requeridos
   - Tabla de incompatibilidades

2. **PLAN_EJECUCION_CHECKLISTS.md** (400+ líneas)
   - Checklist ejecutable por cada PR
   - Código esqueleto para PRs 0-3
   - Commands de validación
   - Fixtures de tests

3. **Este archivo:** Resumen ejecutivo

## 📍 Próximos pasos

1. Ejecutar PR 0: crear models.py, query_registry.py
2. Ejecutar PR 1: crear query_resolver.py + 6 validadores
3. Continuar con PR 2-6

---

**Análisis completado:** 6 de marzo de 2026
**Versión objetivo:** 0.2.0 (sin backward compatibility)
**Python mínimo:** 3.12
