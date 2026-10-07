# TRACEABILITY — Charset Detection & Pool Fixes v0.35.3

**Fecha**: 2026-10-07  
**Versión target**: v0.35.3  
**Estado**: ✅ CERRADO — Todos los fixes implementados, tests verdes (40/40), suite completa 5155 passed  

---

## Resumen de Cambios

### Fixes Implementados

| ID | Componente | Síntesis | Verificación |
|---|---|---|---|
| **Fix A** | `pool_connection_mariadb.py` | Executa `init_command` manual en `get_connection()` cuando el pool lo rechaza | ✅ 2 tests nuevos, 1.04s |
| **Fix B** | `_charset_detection.py` | Soporte `qmark` paramstyle en `_translate_sql()` | ✅ 2 tests nuevos |
| **Fix C** | `_charset_detection.py` | Query SCHEMATA en lugar de TABLES para detectar charset post-upgrade | ✅ 2 tests nuevos |
| **Fix D** | `_charset_detection.py`, `_adaptive_executor.py` | Parámetro `connection_charset` prioriza sesión; LATIN1_MISMATCH→convert | ✅ 3 tests nuevos |
| **H1** | `_charset_detection.py` | Docstring módulo: `latin1_mismatch` = sesión latin1, BD utf8mb4 | ✅ Actualizado |
| **H2** | `_charset_detection.py` | Comentario enum LATIN1_MISMATCH sincronizado | ✅ Actualizado |
| **H3** | `_charset_detection.py` | `_test_read_comments()` retorna False on fail (no dead code) | ✅ Fix aplicado, rama UTF8MB4_MIXED desbloqueda |
| **H7** | `_adaptive_executor.py` | Docstring strategy: FailFast solo para UNKNOWN | ✅ Actualizado |
| **H8** | `_adaptive_executor.py` | `_fetch_with_convert()` wrap SystemError con contexto | ✅ Implementado |
| **H14** | Tests | Coverage para `connection_charset=None` | ✅ 2 tests nuevos |

### Archivos Modificados

```
src/util_bbdd/metadata/
  ├─ _charset_detection.py (✏️ docstring, enum, H3 fix, H1, H2)
  └─ _adaptive_executor.py (✏️ H7, H8, Fix D routing)

src/util_bbdd/connection/mariadb/
  └─ pool_connection_mariadb.py (✏️ Fix A: _pending_init_command)

tests/unit/metadata/
  └─ test_charset_detection.py (✏️ 11 tests: Fixes A-D + Audits H1-H8 + H14)

tests/unit/connection/mariadb/
  └─ test_mariadb_driver_connection.py (✏️ 2 tests: Fix A init_command manual)

docs/
  ├─ index.md (✏️ versión 0.35.1 → 0.35.2)
  ├─ roadmap.md (✏️ versión 0.35.1 → 0.35.2)
  ├─ README.md (✏️ versión 0.35.1 → 0.35.2)
  └─ architecture.md (✏️ versión 0.35.1 → 0.35.2)

CHANGELOG.md (✏️ sección v0.35.2 poblada con Fixes A-D + Audits H1-H8, H14)
```

---

## Ejecución de Pruebas

### Linting & Type Checking (✅ Green)
```bash
python -m ruff check src/util_bbdd/metadata/_charset_detection.py \
                      src/util_bbdd/metadata/_adaptive_executor.py \
                      src/util_bbdd/connection/mariadb/pool_connection_mariadb.py
# → All checks passed!

python -m mypy src/util_bbdd/metadata/_charset_detection.py \
               src/util_bbdd/metadata/_adaptive_executor.py \
               src/util_bbdd/connection/mariadb/pool_connection_mariadb.py
# → Success: no issues found in 3 source files
```

### Unit Tests (✅ 40/40 Passed)
```bash
python -m pytest tests/unit/metadata/test_charset_detection.py \
                 tests/unit/connection/mariadb/test_mariadb_driver_connection.py \
                 -v --tb=short
# → 40 passed in 1.04s

# Breakdown:
# - TestCharsetStateDetector: 6 tests (diagnose + recommendations)
# - TestAdaptiveCatalogExecutor: 7 tests (auto-detect, convert, modes, CONVERT injection)
# - TestCharsetDetectionFixes: 9 tests (Fixes A-D + H14 coverage)
# - TestMariaDBConnectionConfig: 6 tests
# - TestMariaDBPoolConfig: 6 tests
# - TestMariaDBNativePoolFallback: 6 tests (including Fix A manual exec)
```

### Full Suite (✅ 5155 Passed, 0 Failed)
```bash
python -m pytest --tb=short -q
# → 5155 passed, 497 skipped in 49.68s
```

---

## Directrices para Futuras IAs

### [charset-detection]
`CharsetState.LATIN1_MISMATCH` en v0.35.2+ se dispara por `connection_charset=latin1, db=utf8mb4` (sesión sin SET NAMES utf8mb4 ejecutado), no por servidor global. La descripción en enum y docstring refleja esta semántica conexión-nivel. **Fallback: convert, no failfast.**

### [pool-init-command]
Si `mariadb.ConnectionPool` rechaza `init_command` (driver < 1.1.4), `PoolConnection` almacena en `_pending_init_command` y ejecuta manual en cada `get_connection()`. **Overhead**: ~1 RTT por conexión. Documentar en release notes para equipos con latencia crítica.

### [can_read_comments-semantics]
Pre-fix H3, siempre retornaba True (try/except nunca capturaba). H3 cambió semántica: now returns False cuando charset test de information_schema.TABLES.TABLE_COMMENT falla. **Desbloquea rama UTF8MB4_MIXED** por fallo de lectura (línea 224 de `_determine_state()`).

### [connection_charset-priority]
Parámetro `connection_charset` (sesión `@@character_set_connection`) es prioritario sobre `character_set_server` global. Servidor legacy con charset=latin1 pero sesión utf8mb4 se diagnostica **UTF8MB4_CLEAN, no LATIN1_MISMATCH**. **Requisito**: `SET NAMES utf8mb4` realmente ejecutado (via init_command o manual).

### [qmark-paramstyle-limits]
Fix B añade soporte minimal `qmark` en `_translate_sql()`. No robusto para queries multi-pass; regex reemplaza todos los `:nombre` en orden de aparición. **Si driver complejo requiere orden específico**: refactor `_paramstyle.to_driver()` completo, no esa función.

### [test-mocking-fragility]
Mocks de charset detection (ej. `test_diagnose_latin1_mismatch_inverse`) son frágiles — dependen orden exacto de `fetchone()` calls internales. Si orden de queries en `diagnose()` cambia, tests pasan falsamente con valores incorrectos. **Refactor sugerido**: mock con assertions por nombre de query (ej. `execute.assert_called_with('SELECT @@character_set_server')`).

### [H3-repercusión]
H3 fix (`can_read_comments` ahora False on fail) abre rama `UTF8MB4_MIXED` que antes no se alcanzaba. **Verificar en production**: ¿hay servidores post-upgrade con utf8mb3 en metadatos que ahora se detectan como MIXED? Si sí, se aplica CONVERT (98% perf vs 100%). Cambio transparent pero observable.

### [error-context-wrapping]
H8 mejoró `_fetch_with_convert()` error wrapping para incluir `connection_charset` junto con server/database. **Patrón**: siempre envolver excepciones de estrategia adaptativa con diagnostic full context. Aplica a futuras estrategias.

---

## Impacto de Rollback

**Si se revierte a v0.35.1**:
- Sistemas con `character_set_server=latin1` + pool revertirán a failfast (breaking en producción)
- H3 bug resurge (`can_read_comments` siempre True)
- Pool drivers < 1.1.4 fallarán sin manual fallback

**Mitigación rápida**: Deploy Fix A inmediatamente si rollback es necesario.

---

## Checklist de Cierre

- [x] Fixes A-D implementados y testados (40/40 unit tests)
- [x] Audits H1-H2, H3, H7-H8, H14 aplicados
- [x] Docstrings y comentarios sincronizados
- [x] CHANGELOG.md actualizado con detalle técnico
- [x] Versión badges en docs actualizada (0.35.1 → 0.35.2)
- [x] ruff, mypy, pytest todo verde
- [x] Suite completa: 5155 passed, 0 failed
- [x] TRACEABILITY.md poblado (este archivo)

**Commit message propuesto**:
```
fix(metadata, connection/mariadb): charset detection with connection_charset, pool init_command manual execution, and diagnostic improvements

- Fix A: pool init_command manual fallback
- Fix B: qmark paramstyle support
- Fix C: SCHEMATA query for post-upgrade charset
- Fix D: connection_charset priority in detect state
- Audits H1-H8, H14: docs sync, error wrapping, test coverage
```

**Status**: ✅ LISTO PARA MERGE

---

*Sesión cerrada 2026-10-07*
