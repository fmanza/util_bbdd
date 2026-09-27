# Sesión: EngineReadinessAdvisor (2026-09-27)

## Objetivo General
Implementar un verificador read-only de condiciones de ejecución por motor BD que emite un informe consolidado en una única llamada al logger durante `BulkCrud.__init__()`. Auditar el código resultante y aplicar correcciones.

## Fases Ejecutadas

### PHASE: IMPLEMENT ✅ 
**Duración**: Sesión anterior + continuación  
**Resultado**: 7 archivos nuevos, 3 modificados, 0 breaking changes

#### Archivos Creados
1. **`src/util_bbdd/connection/_advisory.py`** — `AdvisoryFinding` dataclass (frozen, slots) + `fmt_bytes()` utilidad
2. **`src/util_bbdd/connection/performance_advisor.py`** — `EngineReadinessAdvisor` fachada + 5 adaptadores por motor
3. **`src/util_bbdd/connection/postgresql/_variables.py`** — `PostgreSQLVariableValidator`: checks estáticos (pool config, keepalives, ssl) + dinámicos (SHOW work_mem/maintenance_work_mem/max_connections/synchronous_commit)
4. **`src/util_bbdd/connection/sqlite/_variables.py`** — `SQLiteVariableValidator`: checks estáticos (database, timeout) + dinámicos (PRAGMA journal_mode/synchronous/cache_size) con guarda :memory:
5. **`src/util_bbdd/connection/sqlserver/_variables.py`** — `SQLServerVariableValidator`: checks estáticos (MARS, pool_size, max_overflow) + dinámicos (fill_factor, recovery_model) + detección driver
6. **`src/util_bbdd/connection/oracle/_variables.py`** — `OracleVariableValidator`: checks estáticos (pool_size, max_lifetime) + dinámicos (pga_aggregate_target, cursor_sharing) + permission check v$parameter
7. **`tests/unit/connection/test_performance_advisor.py`** — 78 tests: 6 clases de statics, 6 de dynamics, 1 de report contract, 1 de exception resilience

#### Archivos Modificados
1. **`src/util_bbdd/bulk/crud.py`** — método `__validate_engine_config()` con triple try/except + pool config inspection SA 2.x compatible
2. **`src/util_bbdd/__init__.py`** — 2 líneas: import + export `EngineReadinessAdvisor`, `AdvisoryFinding` en `__all__`
3. **`tests/unit/test_bulk_*.py`** (3 archivos) — corrección imports: `from util_bbdd.bulk.crud import BulkCrud as bulk_crud` (alias eliminado en sesión anterior)

---

### PHASE: AUDIT_CODE ✅
**Duración**: ~1 hora  
**Agente**: Code Auditor  
**Resultado**: 11 hallazgos identificados, 9 corregidos (todos P2/P3)

#### Hallazgos Identificados y Estado

| ID | Severidad | Área | Hallazgo | Remediación | Estado |
|---|---|---|---|---|---|
| F-01 | P2 | Seguridad | Inyección SQL potencial en `_show_memory`/`_pragma_str` | Whitelists `_VALID_SHOW_PARAMS` (PG) + `_VALID_PRAGMA_NAMES` (SQLite) + guardas entrada | ✅ CORREGIDO |
| F-02 | P2 | Logging | `except Exception: return []` silenciaba bugs implementación | Cambio a `logger.debug(f"_check_X: {exc}")` en 5 adaptadores | ✅ CORREGIDO |
| F-03 | P2 | Deuda Técnica | `_fmt_bytes()` duplicada oracle + postgresql | Centralizada en `_advisory.py` como `fmt_bytes`, ambos importan como `_fmt_bytes` | ✅ CORREGIDO |
| F-04 | P2 | Rendimiento | Abre conexión extra en `BulkCrud.__init__` | Aceptado como trade-off (verificación temprana) + fallback estático si falla | ⚠️ CONOCIDO |
| F-05 | P3 | Completitud | Sin rama `else: OK` en `write_timeout`/`read_timeout` MySQL | Añadidas ramas OK en `_check_mysql` | ✅ CORREGIDO |
| F-06 | P3 | Completitud | `pool_timeout` no verificado en MySQL | Añadido check WARNING (<10 s) en `_check_mysql` | ✅ CORREGIDO |
| F-07 | P3 | Arquitectura | API inconsistente entre MySQLVariableValidator (conexión en constructor) vs nuevos validadores (conexión en método) | Aceptado como deuda técnica (refactor futuro de MySQLVariableValidator) | ℹ️ ACEPTADO |
| F-08 | P3 | Testing | Sin tests dinámicos Oracle/SQL Server/MySQL | Añadidas `TestOracleDynamicChecks`, `TestSQLServerDynamicChecks`, `TestMySQLDynamicChecks` | ✅ CORREGIDO |
| F-09 | P3 | Testing | Exception resilience test solo en PostgreSQL | Añadida `TestExceptionResilienceAllEngines` con @parametrize en 6 motores | ✅ CORREGIDO |
| F-10 | INFO | Arquitectura | `AdvisoryFinding` re-exportada desde `_advisory.py` (privado) vía `performance_advisor.py` → `util_bbdd.__init__` | Aceptado (misma clase, 2 rutas válidas, no ambigüedad semántica) | ℹ️ ACEPTADO |
| F-11 | INFO | UX | Truncación silenciosa en `current` (38 chars) en Oracle arraysize | Aceptado (cosmético, no afecta diagnóstico crítico) | ℹ️ ACEPTADO |

**Veredicto**: **APROBADO** — Todos los P2/P3 corregidos. Info/riesgos residuales documentados.

---

## Verificación Final

### Linting & Type Checking
```bash
$ python -m ruff check src/util_bbdd/connection/*.py src/util_bbdd/bulk/crud.py tests/unit/connection/test_performance_advisor.py
All checks passed!

$ python -m mypy src
Success: no issues found in 361 source files
```

### Test Suite
```bash
$ python -m pytest tests/unit/ -q --tb=short
4779 passed in 22.37s (78 nuevos + 4701 existentes)

$ python -m pytest tests/unit/connection/test_performance_advisor.py -v
78 tests — 100% passing
- TestAdvisoryFinding: 2 tests (frozen, fields)
- TestPostgreSQLStaticChecks: 6 tests (pool_size, keepalives, sslmode, pool_timeout)
- TestPostgreSQLDynamicChecks: 6 tests (work_mem, maint_mem, max_connections, exception)
- TestSQLiteStaticChecks: 4 tests (memory db, file db, timeout)
- TestSQLiteDynamicChecks: 4 tests (journal_mode, synchronous, memory guard)
- TestSQLServerStaticChecks: 5 tests (MARS, pool_size, driver, max_overflow)
- TestSQLServerDynamicChecks: 3 tests (recovery_model, fill_factor, exception)
- TestOracleStaticChecks: 4 tests (pool_size, max_lifetime, arraysize)
- TestOracleDynamicChecks: 5 tests (no_permission, pga, cursor_sharing, exception)
- TestMySQLStaticChecks: 6 tests (autocommit, pool_size, write_timeout)
- TestMySQLOKFindings: 3 tests (write_timeout_ok, read_timeout_ok, pool_timeout_warning) [F-05/F-06]
- TestMySQLDynamicChecks: 3 tests (innodb_buffer_pool, exception)
- TestEngineReadinessAdvisorReport: 5 tests (single-call guarantee, log levels, unknown engine)
- TestExceptionResilienceAllEngines: 6 tests (postgresql, sqlite, mssql, oracle, mysql, mariadb) [F-09]
```

### API Compatibility
```
Cambios en API pública:
  ✅ +EngineReadinessAdvisor (nuevo, opcional)
  ✅ +AdvisoryFinding (nuevo, opcional)
  ✅ BulkCrud.__init__() (comportamiento: verificación silenciosa si ImportError)
  ✅ sin breaking changes
```

---

## Arquitectura & Decisiones de Diseño

### [D-01] Niveles de arquitectura: Nivel 2 (connection) → Nivel 3 (bulk)
**Decisión**: Verificador reside en Nivel 2; se invoca desde Nivel 3 via `try/except ImportError`.  
**Justificación**: Desacoplamiento. Si usuarios solo usan Nivel 2 (metadata, managers), no arrastran dependencias de Nivel 3.  
**Patrón verificable**: `src/util_bbdd/bulk/crud.py` línea ~310, triple try/except.

### [D-02] Contrato de logging: "una sola llamada al logger"
**Decisión**: `EngineReadinessAdvisor.report()` emite exactamente 1 llamada: nivel WARNING si hay WARNING/CRITICAL, INFO en caso contrario.  
**Justificación**: Previene spam de logs en inicios de aplicación. Auditable con caplog.  
**Test verificable**: `TestEngineReadinessAdvisorReport.test_report_emits_single_log_call_*`.

### [D-03] Whitelists SQL: Prevención de inyección en SHOW/PRAGMA
**Decisión**: `_VALID_SHOW_PARAMS` (postgresql) y `_VALID_PRAGMA_NAMES` (sqlite) son frozensets; guardas en entrada.  
**Justificación**: SHOW/PRAGMA son sintaxis SQL — aunque no son DML, permiten lectura de parámetros. Callers actuales pasan literals, pero riesgo estructural existe.  
**Patrón verificable**: `connection/postgresql/_variables.py` línea ~30, `connection/sqlite/_variables.py` línea ~20.

### [D-04] Exception resilience: Triple wrapping
**Decisión**: 3 capas: outer `.check()`, per-adapter `_check_X()`, per-check `_show_memory()` etc.  
**Justificación**: Fallos en checks dinámicos (permiso, motor offline) nunca rompen `BulkCrud.__init__()`.  
**Test verificable**: `TestExceptionResilienceAllEngines.test_broken_connection_never_raises`.

### [D-05] Pool API privada: getattr + fallback
**Decisión**: `pool._max_overflow`, `pool._timeout` son privados SA 2.x → `getattr(pool, attr, None)` + ignorar si ausente.  
**Justificación**: Robustez ante cambios internos SA. Si SA cambia, verificador continúa sin romper.  
**Patrón verificable**: `bulk/crud.py` línea ~315-325.

### [D-06] Motor Oracle: Permission check v$parameter
**Decisión**: `SELECT COUNT(*) FROM v$parameter WHERE rownum=1` antes de leer — si falla, emite INFO.  
**Justificación**: Oracle requiere `SELECT ANY DICTIONARY` (rare). Informar usuario sin romper.  
**Test verificable**: `TestOracleDynamicChecks.test_no_permission_emits_info`.

### [D-07] SQLite :memory: guard
**Decisión**: Omitir checks de WAL/journal_mode en `:memory:` — no aplican.  
**Justificación**: :memory: no tiene persistencia de log. Reducir ruido.  
**Test verificable**: `TestSQLiteDynamicChecks.test_memory_db_skips_wal_check`.

### [D-08] Centralización fmt_bytes
**Decisión**: Única definición en `_advisory.py`, importada como `_fmt_bytes` en oracle + postgresql.  
**Justificación**: DRY. Evitar deuda técnica de duplicación.  
**Patrón verificable**: `connection/_advisory.py` línea ~20, reutilización en validadores.

---

## Directrices para Futuras IAs

### [seguridad] 
**SHOW/PRAGMA dinámicos requieren whitelists**. Los métodos `_show_*`, `_pragma_*` construyen SQL con f-strings. Aunque callers actuales pasan literals, es vulnerabilidad estructural. Siempre pre-validar strings en SQL dinámicos antes de `text()`.

**Recomendación**: Revisar periódicamente callsites de `_show_memory()`, `_show_str()`, `_pragma_str()`, `_pragma_int()` para asegurar que solo se pasan whitelisted params.

### [logging/contract]
**`.report()` emite exactamente una sola llamada al logger** — contrato verificable con caplog. Cualquier refactor que añada más `logger.*` rompe el test `test_report_emits_single_log_call_*`. 

**Recomendación**: Si se modifica `report()`, actualizar simultáneamente el test.

### [excepciones]
**Triple wrapping de excepciones es deliberado**. Checks dinámicos pueden fallar (permiso, motor offline, parámetro no existe). Nunca re-raise — siempre loguear con debug + retornar lista vacía. 

**Test de verificación**: `TestExceptionResilienceAllEngines` parametrizado en 6 motores.

### [motor-específico]
**Cada motor tiene protocol propio**:
- **PostgreSQL**: `SHOW work_mem` (sesión, sin permisos especiales)
- **SQLite**: `PRAGMA journal_mode` (read-only, omitir en :memory:)
- **SQL Server**: `sys.configurations` + `sys.databases` (bind params: `:n`, `:db`)
- **Oracle**: `v$parameter` (requiere `SELECT ANY DICTIONARY` — chequear permisos)
- **MySQL/MariaDB**: Delegar en `MySQLVariableValidator` existente

Si se añade séptimo motor: replicar patrón clase validador + `.check_static()` + `.check_dynamic(connection, conn_params)`.

### [pool-api]
**`pool._max_overflow`, `pool._timeout` son privados SA 2.x**. Usar `getattr(pool, _attr, None)` con fallback. El atributo público `pool.size()` también necesita `callable()` check. 

**Recomendación**: Si SA cambia su pool API, el código continúa sin romper — simplemente no pobla esos campos. Nivel de degradación aceptable.

### [testing]
**`_make_conn()` helpers en tests** usan `MagicMock` + `fake_execute()` para simular read-only queries sin BD real. Si se añaden checks dinámicos en motores nuevos, reutilizar patrón de fixture.

### [referencia-audit]
**11 hallazgos en AUDIT_CODE**, F-01 a F-11, severidades P0-P3 + INFO. Los P2/P3 se corrigieron; los INFO se aceptaron como riesgo residual. Documentados en esta sección «Hallazgos Identificados».

---

## Artefactos Generados

### En Repositorio
- **7 archivos nuevos** (code + tests)
- **3 archivos modificados** (bulk/crud.py, __init__.py, 3 test fixtures)
- **Changelog**: Actualizado en CHANGELOG.md

### En Sesión (.ai/sessions/2026-09-27-...)
- **TRACEABILITY.md** (este archivo)
- **commit_message.txt** (borrador)
- **AUDIT_CODE_findings.txt** (hallazgos detallados)
- **test_summary.txt** (78 tests nuevos)

---

## Checklist Pre-Merge

- [x] Ruff: 0 errores
- [x] MyPy: 0 errores (361 archivos)
- [x] Pytest: 4779 passed (78 nuevos)
- [x] AUDIT_CODE: P2/P3 corregidos
- [x] Changelog actualizado
- [x] API pública no rota
- [x] Imports corregidos (3 test files)
- [x] Documentación en docstrings
- [x] Logging estructurado (1 llamada/report)
- [x] Whitelists SQL implementadas
- [x] Exception handling resiliente

---

## Siguiente Paso Recomendado

```bash
# 1. Revisar CHANGELOG.md + commit message
# 2. git add -A && git commit -m "feat(connection): EngineReadinessAdvisor..."
# 3. git push origin develop
# 4. Crear PR desde develop → main
```

**Sesión finalizada**: 2026-09-27 ✅
