# TECH DEBT AUDIT: Logging Obligatorio + Variables Globales
**Fecha**: 18 de abril de 2026
**Rama**: develop (v0.6.7.dev0)
**Status**: ✅ **GO** — Iniciación autorizada

---

## 📊 RESUMEN EJECUTIVO (ACTUALIZADO 18:00 UTC)

| Métrica | Valor | Estado |
|---------|-------|--------|
| **Clases totales auditadas** | 283 | — |
| **Con logger tipado** | 38 (13%) | 🟡 BAJO |
| **Con logger no tipado** | 8 (2.8%) | 🟡 BAJO |
| **Con logger inyectado** | 7 (2.5%) | 🟡 BAJO |
| **Sin logger** | 230 (81%) | 🔴 CRÍTICO |
| **Total con logging** | 53 (18.7%) | 🔴 CRÍTICO |
| **Variables globales mutables** | 0-3 (< 0.1%) | ✅ EXCELENTE |
| **Deuda técnica** | SEVERA | 🔴 |

---

## 🔴 HOTSPOTS CRÍTICOS (Máximo Impacto)

### 1. **Comparar Layer — 0% cobertura (~15 clases, 0/15 con logger)**

**Archivos afectados:**
- [src/util_bbdd/comparar/comparator.py](src/util_bbdd/comparar/comparator.py#L30) — `SchemaComparator` (L30, logger module-level ❌)
- [src/util_bbdd/comparar/reporters/](src/util_bbdd/comparar/reporters/) — 6 clases reporters sin logger
  - `HtmlDiffReporter` (html_reporter.py:26)
  - `ExcelDiffReporter` (excel_reporter.py:22)
  - `MarkdownDiffReporter` (markdown_reporter.py:22)
  - `WordDiffReporter` (word_reporter.py:31)
  - `SqlDiffReporter` (sql_reporter.py:78)
  - `SchemaDiffReporter` (facade.py:37)

**Estimación**: ~1,500 LOC | 3-4 horas refactor | **QUICK WIN**

---

### 2. **Metadata Layer — 13% cobertura (~46 clases, 6 con logger)**

**Problema raíz**: `BaseSourceAdapter` recibe logger como parámetro pero NO lo almacena como `self.logger`

**Archivos afectados:**
- [src/util_bbdd/metadata/adapters/base_adapter.py](src/util_bbdd/metadata/adapters/base_adapter.py#L22) — `BaseSourceAdapter` (L22)
- [src/util_bbdd/metadata/adapters/base_adapter.py](src/util_bbdd/metadata/adapters/base_adapter.py#L154) — `BaseRoutineAdapter` (L154)
- ~20 clases concretas (MariaDB, PostgreSQL, Oracle, SQLServer, SQLite adapters — sync + async)

**Estimación**: ~2,500 LOC | 5-7 horas refactor | **FASE MEDIA**

---

### 3. **Managers Layer — 8% cobertura (~12 clases, 1 con logger)**

**Archivos afectados:**
- [src/util_bbdd/managers/sync_mgr.py](src/util_bbdd/managers/sync_mgr.py#L73) — `SyncDatabaseManager` ✅ (tiene logger)
- [src/util_bbdd/managers/async_mgr.py](src/util_bbdd/managers/async_mgr.py#L57) — `AsyncDatabaseManager` (verificar)
- [src/util_bbdd/managers/_manager_lifecycle_sync.py](src/util_bbdd/managers/_manager_lifecycle_sync.py#L17) — `SyncLifecycleManager` ❌
- [src/util_bbdd/managers/_manager_lifecycle_async.py](src/util_bbdd/managers/_manager_lifecycle_async.py#L13) — `AsyncLifecycleManager` ❌
- [src/util_bbdd/managers/_manager_session.py](src/util_bbdd/managers/_manager_session.py) — `SyncSessionManager`, `AsyncSessionManager` ❌
- Múltiples strategy classes (GenericMetadataFetchStrategy, MariaDBMetadataFetchStrategy, etc.) ❌
- Storage strategies (12 clases) ❌

**Estimación**: ~3,000 LOC | 8-12 horas refactor | **FASE MEDIA (CRÍTICA)**

---

### 4. **Query Layer — 33% cobertura (~3 clases, 1 con logger)**

**Archivos afectados:**
- [src/util_bbdd/query/registry.py](src/util_bbdd/query/registry.py#L24) — `QueryRegistry` (verificar)
- [src/util_bbdd/query/resolver.py](src/util_bbdd/query/resolver.py#L55) — `QueryResolver` ✅ (tiene logger)
- [src/util_bbdd/query/queries.py](src/util_bbdd/query/queries.py#L24) — `DatabaseQueries` ❌

**Estimación**: ~800 LOC | 1-2 horas refactor | **QUICK WIN**

---

## 📋 PLAN DE IMPLEMENTACIÓN (5 Fases)

### **Fase 1: Comparar Layer (0% → 100%)**
- **Archivos**: 8, Clases: 15
- **Cambios**: Instanciar `self.logger` en cada clase; migrar `logger.` a `self.logger.`
- **Riesgos**: BAJO (módulo aislado)
- **Tests**: `tests/comparar/test_diff_reporters.py` (~30 tests)
- **Esfuerzo**: 3-4 horas

### **Fase 2: Query Layer (33% → 100%)**
- **Archivos**: 3, Clases: 3
- **Cambios**: Instanciar `self.logger` en QueryRegistry + DatabaseQueries
- **Riesgos**: BAJO (quick win)
- **Tests**: `tests/unit/test_query_registry.py`
- **Esfuerzo**: 1-2 horas

### **Fase 3: Metadata Adapters (13% → 90%)**
- **Archivos**: 24+, Clases: ~20
- **Cambios**: Refactor BaseSourceAdapter + BaseRoutineAdapter; inyectar `self.logger` en subclases
- **Riesgos**: MEDIO (múltiples motores, requiere testing)
- **Tests**: `tests/metadata/test_adapters.py`, introspection tests
- **Esfuerzo**: 5-7 horas

### **Fase 4: Managers Layer (8% → 95%)**
- **Archivos**: 12+, Clases: ~20
- **Cambios**: Instanciar `self.logger` en lifecycle, session, strategy, storage classes
- **Riesgos**: ALTO (API pública, orquestación central)
- **Tests**: `tests/integration/test_sync_manager.py`, integration suite
- **Esfuerzo**: 8-12 horas

### **Fase 5: Otros módulos (analysis, doc, bulk, results)**
- **Archivos**: ~20, Clases: ~30
- **Cambios**: Auditoría + implementación rápida (varios ya tienen logger)
- **Riesgos**: BAJO
- **Esfuerzo**: 4-6 horas

### **Total: ~21-33 horas ≈ 2-3 días dev**

---

## 🎯 CRITERIOS DE ACEPTACIÓN

- [ ] 100% de clases con lógica tienen `self.logger: logging.Logger` tipado
- [ ] Todos los loggers instanciados en `__init__()` o `__post_init__()`
- [ ] 0 variables globales mutables nuevas
- [ ] Tests pasan con 100% coverage en logging statements
- [ ] `mypy --strict` sin errores relacionados a logging
- [ ] 0 `print()` en código de librería (excepto tests)
- [ ] CHANGELOG.md actualizado
- [ ] PRs cumplen checklist de logging (v. `.github/copilot-instructions.md`)

---

## ✅ VARIABLES GLOBALES: EXCELENTE ESTADO

**Hallazgo**: 0 violaciones graves detectadas

- ✅ Constantes inmutables: Bien (MaxRetries, Patterns, etc.)
- ✅ ClassVar en clases: Bien (ConnectionPool._instances, etc.)
- ✅ Logger module-level: Bien (cuando no requiere inyección)
- ✅ 1-2 singleton builders: Controlados con locks

**Veredicto**: **CUMPLIDO** — No requiere cambios

---

## 🔐 RIESGOS Y MITIGACIONES

| Riesgo | Impacto | Mitigación |
|--------|---------|-----------|
| **Credential leakage en logs** | ALTO | Implementar filter `logging.Logger` que sanitice passwords |
| **PII exposure** | MEDIO | Review de format strings; usar `***` para sensibles |
| **Logger inconsistente** | BAJO | Lint: `ruff` + `mypy --strict` para `logging.Logger` tipo |
| **Regresión en tests** | BAJO | Captura de logs con `caplog` pytest |
| **Performance** | NEGLIGIBLE | Instanciar en `__init__()`, no en bucles |

---

## 🚨 VEREDICTO

| Aspecto | Resultado |
|--------|-----------|
| **Estado Global** | 🔴 SIGNIFICATIVO |
| **Riesgo de no hacer nada** | 🔴 ALTO (debugging imposible en prod) |
| **Impacto de refactor** | 🟡 MEDIO (cambios internos, bajo riesgo) |
| **Viabilidad** | ✅ GO (3-4 días, recursos disponibles) |
| **Iniciación** | ✅ **AUTORIZADA** |

---

## 📌 NEXT STEPS

1. **Revisar y aprobar PLAN** (este documento)
2. **Ejecutar Fase 1 (Comparar)** — Martes/Miércoles
3. **Ejecutar Fase 2 (Query)** — Mismo día PM
4. **Ejecutar Fases 3-4 (Metadata + Managers)** — Miércoles/Jueves
5. **Verificación final + merge** — Viernes

---

*Tech Debt Audit completado: 2026-04-18 — Config Reviewer + Plan Architect + Code Auditor*
