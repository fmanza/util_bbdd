# PR 8: Remover Métodos Deprecated (Post-Transición)

## Estado: ANÁLISIS INICIAL
**Fecha:** 8 de marzo de 2026
**Prioridad:** Baja (Limpieza de código)
**Impacto:** BREAKING CHANGE (v0.3.0)

> Nota Fase 4 (2026-03-31): este plan de retirada es historico. Las referencias a imports desde `database_queries.py` documentan el estado previo; para documentacion actual, los aliases deben apuntar a `database_exceptions.py` y los modulos legacy deben tratarse como compatibilidad transitoria o ya retirada segun el corte actual.

> Lectura actual: donde este documento menciona `backward compat`, debe leerse como compatibilidad residual del momento analizado, no como recomendación vigente para código nuevo.

---

## Items Deprecated para Remover

### 1. DatabaseQueryError (Exception)
**Ubicación:** `src/util_bbdd/database_queries.py` línea 27
**Tipo:** Old exception class (antes de refactoring PR 5)

```python
class DatabaseQueryError(Exception):
    """
    DEPRECATED: Use QueryNotFoundError, QueryValidationError, etc.
    Alias deprecated_query_error = QueryNotFoundError
    """
```

**Estado Actual:**
- ✅ Existe alias en `database_exceptions.py`: `DatabaseQueryError = QueryNotFoundError`
- ✅ Todos los nuevos usos de QueryNotFoundError/QueryValidationError/etc
- ❌ Aún existe definición redundante en `database_queries.py`

**Impacto de Remover:**
- BREAKING: Users importing `from database_queries import DatabaseQueryError`
- Safe: Alias en database_exceptions.py proporciona backward compat
- Migration: Update imports a `from util_bbdd.database_exceptions import QueryNotFoundError`

---

### 2. DatabaseQueries.validate_query_parameters()
**Ubicación:** `src/util_bbdd/database_queries.py` línea 276
**Tipo:** Public method (deprecated)

```python
def validate_query_parameters(self, query_name: str, **kwargs) -> bool:
    """
    DEPRECATED: Use QueryResolver.resolve() for comprehensive validation
    """
```

**Estado Actual:**
- ✅ Logic delegated to `analyze_query_parameters()` → QueryResolver
- ✅ Tests still check method exists
- ❌ Still public, might be used by consumers

**Usages Internos:**
- `database_queries.py` línea 394: En método build_query_info()
- `database_manager.py` línea 1338: `DatabaseManager.validate_query_parameters()`
- `database_queries.py` línea 2029: En get_query_info()

**Impacto de Remover:**
- BREAKING: Public API removal
- Safe alternative: `QueryResolver.resolve()` desde `util_bbdd.query.resolver` o via la API publica vigente del manager
- Migration: See MIGRATION_GUIDE_v0.1_to_v0.2.md

---

### 3. DatabaseQueries.analyze_query_parameters()
**Ubicación:** `src/util_bbdd/database_queries.py` línea 304
**Tipo:** Public method (deprecated)

```python
def analyze_query_parameters(self, query_name: str, params: dict | None = None) -> dict:
    """
    DEPRECATED: Use QueryResolver for comprehensive resolution
    """
```

**Estado Actual:**
- ✅ Logic moved to QueryResolver
- ✅ Tests still check method exists
- ❌ Still public, might be used by consumers

**Usages Internos:**
- Called from `validate_query_parameters()` línea 292
- Called from `_validate_query_parameters_and_build_error()` línea 998
- Called from `_query_info_internal()` línea 1184

**Impacto de Remover:**
- BREAKING: Public API removal
- Safe: All internals use QueryResolver already
- Migration: QueryResolver.resolve() provides same info

---

## Análisis de Riesgos

### ✅ Safe to Remove:
1. **DatabaseQueryError** - Alias ya existe, solo duplicado
2. **analyze_query_parameters()** - Totalmente delegado a QueryResolver
3. **validate_query_parameters()** - Solo lógica de delegación

### ⚠️ Requires Updates:
1. Tests: `test_database_queries_refactor_pr5.py` (línea 175, 182)
2. Internal calls en `database_queries.py`
3. Wrapper en `database_manager.py` (línea 1327)
4. Documentation y MIGRATION_GUIDE

### ❌ NOT Recommended:
- Remover durante v0.2.x (transición ongoing)
- Remover sin deprecation warning period
- Remover sin updating migration guide

---

## Plan de Implementación

### Phase 1: Validación (15 min)
- [ ] Verify NO external consumers (check GitHub issues/discussions)
- [ ] Confirm all internal uses can be replaced
- [ ] Check version history (deprecated since v0.2.0)
- [ ] Estimation valid para v0.3.0+

### Phase 2: Removal (30 min)
- [ ] Delete `class DatabaseQueryError` from `database_queries.py`
- [ ] Delete `validate_query_parameters()` from `DatabaseQueries`
- [ ] Delete `analyze_query_parameters()` from `DatabaseQueries`
- [ ] Delete wrapper `validate_query_parameters()` from `DatabaseManager`
- [ ] Update internal calls to use QueryResolver directly

### Phase 3: Test Updates (20 min)
- [ ] Remove deprecation tests (test_..._still_available_but_deprecated)
- [ ] Add removal confirmation tests
- [ ] Verify 241/241 unit tests still PASS
- [ ] Verify 19/19 E2E tests still PASS

### Phase 4: Documentation (15 min)
- [ ] Update CHANGELOG.md (Removed section)
- [ ] Update MIGRATION_GUIDE_v0.1_to_v0.2.md (add v0.3.0 section)
- [ ] Update README.md (remove deprecated examples)
- [ ] Create 08_ESTADO_COMPLETO_PR8.md

### Estimado Total: ~80 min

---

## Risk Mitigation

1. **Versioning:** PR 8 → v0.3.0 (major bump due to breaking changes)
2. **Communication:** Add removal notes to CHANGELOG
3. **Timeline:** Minimum 2 weeks after PR 7 merge so users see deprecation
4. **Alternatives:** Users can use QueryResolver directly

---

## Decision Point

⚠️ **This PR is OPTIONAL** for v1.0 delivery.

**Recommendation:**
- If time available: Proceed with PR 8 (clean codebase for v0.3.0)
- If time constrained: Defer to future maintenance (v0.3.0+)
- Either way: Deprecation already in place, con compatibilidad residual mantenida en ese corte historico

---

## Current Status

```
Items Ready for Removal: 3
├─ DatabaseQueryError (Exception class)
├─ validate_query_parameters() method
└─ analyze_query_parameters() method

Estimated Work: 80 minutes
Tests Impact: 0 regressions expected (241/241 + 19/19)
Version Target: v0.3.0+
Status: OPTIONAL for v1.0
```
