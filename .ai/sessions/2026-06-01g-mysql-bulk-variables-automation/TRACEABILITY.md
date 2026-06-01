# TRACEABILITY — MySQL/MariaDB Variables Automation for Bulk Operations

## Session metadata
- id: 2026-06-01g
- fecha: 2026-06-01
- rama: develop
- skill: tech_debt + performance optimization
- fase: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION

## Prompt issued

**Usuario** (Copilot Chat):

> "revisar el módulo src\util_bbdd\bulk y ver cual es la mejor estrategia para automatizar las siguientes variables... SHOW VARIABLES LIKE 'max_allowed_packet'; SET GLOBAL max_allowed_packet = 67108864; SHOW VARIABLES LIKE 'innodb_buffer_pool_size'; SET GLOBAL innodb_buffer_pool_size = 1073741824;"

**Evolución de requisitos**:
1. Inicial: Soporte para configuración manual de variables MySQL (lectura via SHOW VARIABLES)
2. Intermedio: Automatizar lectura + detectar discrepancias vs. mínimos requeridos
3. Final (Autorizado con "Si"): Implementar 4 capas (Validator + Config + Strategy enhancement + BulkCrud logging)

## Context supplied

### Pre-sesión (de SHARED_INSTRUCTIONS.md y bulk/crud.py)
- Arquitectura TIMELOG: modularidad, SOLID, contratos claros
- BulkCrud existente: soporte para commit_every_n_chunks (Phase 1 de performance)
- MySQLMultiRowInsertStrategy: existing `execute()` method con sub-lotes
- Problemas conocidos: error 2013 ("Lost connection"), degradación exponencial sin tuning

### Contexto aportado durante sesión
- .github/SHARED_INSTRUCTIONS.md: flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
- .github/instructions/python.instructions.md: typing, docstring requirements
- .github/instructions/architecture.instructions.md: module organization
- tests/: estructura pytest con mocks, parametrización, fixtures
- pyproject.toml: Python 3.12+, SQLAlchemy >= 2.0.46, pytest 9.0+

## AI output summary

### Fase 1: PLAN (Contexto y Análisis)
- Analicé BulkCrud.__init__ y MySQLMultiRowInsertStrategy para identificar dónde integrar validación
- Identificué problema: sin variables MySQL adecuadas, bulk inserts fallan silenciosamente en producción
- Propuse 4-capa strategy: validator (read-only) → config (recommendations) → calculator (packet size) → integration (logging)

### Fase 2: AUDIT_PLAN
- Revisé pyproject.toml: Python 3.12+, SQLAlchemy 2.0.46+, pytest 9.0+
- Verificé que MySQLVariableValidator + MySQLOptimalConfig NO modificarían BD (solo lectura)
- Validé que __validate_mysql_config() sería logging-only (sin breaking changes)
- Confirmó: no hay expansion de alcance, riesgos manejables, usuario autorizó implementación

### Fase 3: IMPLEMENT
1. **Creé MySQLVariableValidator** (`src/util_bbdd/connection/mariadb/_variables.py`, 160 líneas):
   - read_variables(): Ejecuta `SHOW VARIABLES LIKE 'variable'` para cada variable crítica
   - validate(): Compara actuales vs. requeridos, retorna dict[str, bool]
   - log_summary(): Loguea estado actual + recomendaciones en niveles INFO/WARNING
   - format_bytes(): Convierte bytes → "64 MB", "1 GB" format
   - _CRITICAL_VARIABLES: frozenset({"max_allowed_packet", "innodb_buffer_pool_size"})

2. **Creé MySQLOptimalConfig** (`src/util_bbdd/connection/mariadb/_config.py`, 115 líneas):
   - Dataclass congelada con campos: innodb_buffer_pool_size, max_allowed_packet (en bytes)
   - dev(): 256 MB buffer, 16 MB packet
   - production(): 1 GB buffer, 64 MB packet
   - high_volume(): 4 GB buffer, 128 MB packet
   - suggest(num_rows): Heurística (≤100K → dev, ≤1M → production, >1M → high_volume)
   - format_bytes(), __str__()

3. **Actualicé MySQLMultiRowInsertStrategy** (`src/util_bbdd/bulk/_execution/batch.py`):
   - Nuevo método get_min_max_allowed_packet(avg_row_bytes=2000):
   - Fórmula: estimated_size = max_rows × avg_row_bytes × 1.5
   - Retorna 64–256 MB (potencias de 2), sin modificar execute() existente

4. **Integré en BulkCrud** (`src/util_bbdd/bulk/crud.py`):
   - Nuevo método __validate_mysql_config() (40 líneas)
   - Llamada en __init__ línea ~178 (después de __detectar_sqlserver_driver())
   - Solo ejecuta para dialect mysql/mariadb
   - Lee variables actuales, loguea recomendaciones, graceful error handling

5. **Actualicé Exportes** (`src/util_bbdd/connection/mariadb/__init__.py`):
   - Lazy-loaded: MySQLVariableValidator, MySQLOptimalConfig
   - __all__ expandido con ambas clases
   - Backward compatible (existing imports sin cambios)

### Fase 4: AUDIT_CODE
- Ejecuté `ruff check src tests`: All checks passed ✅
- Ejecuté `mypy src`: Success, 336 source files, 0 errors ✅
- Ejecuté `pytest` (primera pasada): 2 failures en test_mysql_min_packet_calculation.py
  - Causa: get_min_max_allowed_packet() retornaba 32 MB en lugar de 64 MB (mínimo estándar)
  - Fix: Ajusté lógica para retornar 64 MB mínimo para todos los bulk operations
  - Reason: 32 MB muy apretado, 64 MB es power-of-2 standard para MySQL/MariaDB
- Ejecuté `pytest` (segunda pasada): 3728 passed, 1 skipped ✅

### Fase 5: VERSION
- Actualicé CHANGELOG.md con entrada en [Unreleased]:
  - Sección "Added": Documentación técnica de 3 nuevas clases
  - Detalles: módulos, métodos, cambios, backward compatibility
  - Referencia a test files
- Creé PR #18: "feat(connection/bulk): automatización de variables MySQL/MariaDB para bulk operations"
  - Base: main, Head: develop
  - Descripción completa con ejemplos de uso, validaciones, riesgos mitigados
  - Estado: OPEN

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| **MySQLVariableValidator** | `src/util_bbdd/connection/mariadb/_variables.py` | ✅ 160 líneas, tested |
| **MySQLOptimalConfig** | `src/util_bbdd/connection/mariadb/_config.py` | ✅ 115 líneas, tested |
| **MySQLMultiRowInsertStrategy enhancement** | `src/util_bbdd/bulk/_execution/batch.py` | ✅ New method, integrated |
| **BulkCrud.__validate_mysql_config()** | `src/util_bbdd/bulk/crud.py` | ✅ 40 líneas, integrated |
| **mariadb/__init__.py updates** | `src/util_bbdd/connection/mariadb/__init__.py` | ✅ Lazy-loaded exports |
| **Unit tests (MySQLVariableValidator)** | `tests/unit/connection/mariadb/test_mysql_variables_config.py` | ✅ 18 tests, all pass |
| **Unit tests (min packet calc)** | `tests/unit/bulk/test_mysql_min_packet_calculation.py` | ✅ 8 tests, all pass |
| **CHANGELOG.md** | `CHANGELOG.md` [Unreleased] → Added | ✅ Updated |
| **GitHub PR #18** | https://github.com/fmanza/util_bbdd/pull/18 | ✅ OPEN |
| **Traceability** | `.ai/sessions/2026-06-01g-mysql-bulk-variables-automation/` | ✅ This file |

## Quality Gates Passed

✅ **Lint**: ruff check src tests → "All checks passed!"
✅ **Type-check**: mypy src → "Success: no issues found in 336 source files"
✅ **Tests**: pytest → "3728 passed, 1 skipped in 14.64s"
✅ **Backward Compatibility**: 0 breaking changes (new modules + methods, logging-only integration)
✅ **Documentation**: CHANGELOG.md updated with technical details
✅ **Exports**: Lazy-loaded via __getattr__ (existing pattern preserved)

## Directrices para Futuras IAs

### [MySQL/MariaDB Configuration]
**Hecho verificable**: Dos variables **críticas** determinan éxito de bulk inserts en MySQL/MariaDB:
- `innodb_buffer_pool_size` (default 128–256 MB): Insuficiente para cargas masivas; mínimo 1 GB en producción
- `max_allowed_packet` (default 16 MB): Puede ser insuficiente para multi-row INSERT statements; mínimo 32–64 MB

**Riesgo si ignorados**: Error 2013 ("Lost connection to server...") + degradación exponencial (5–10× más lento)

**Mitigación implementada**: MySQLVariableValidator + log_summary() detecta en __init__ de BulkCrud y loguea recomendaciones (READ-ONLY, sin SUPER requerido)

### [Automated Variable Detection Best Practice]
**Hecho verificable**: Validación de SHOW VARIABLES debe ser:
1. **Read-only** (sin SET GLOBAL; usuario elige si aplicar recomendaciones)
2. **Graceful** (exception handling en caso de fallo; no bloquea BulkCrud)
3. **Logged** (INFO para valores actuales, WARNING si debajo de mínimos)
4. **Heuristic** (MySQLOptimalConfig.suggest() es aproximado, no exacto)

**Pattern**: Capas separadas — validator (read-only) → config (recommend) → strategy (calc) → integration (log)

### [MySQL Packet Size Calculation]
**Hecho verificable**: get_min_max_allowed_packet() para multi-row INSERT debe:
- Estimar: max_rows × avg_row_bytes × 1.5 (buffer para overhead)
- Retornar: Valor >= 64 MB (standard power-of-2), <= 256 MB (límite práctico)
- Nunca retornar < 64 MB para bulk operations (demasiado restrictivo)

**Formula**: Implementada en MySQLMultiRowInsertStrategy, reutilizable para otras estrategias

### [Integration Pattern in Existing Code]
**Hecho verificable**: Al integrar validación en BulkCrud.__init__:
- No modificar signature existente (parámetro new → error; parámetro renamed → breaking)
- Llamar __validate_mysql_config() DESPUÉS de __detectar_sqlserver_driver() (orden importa para dialect detection)
- Usar try/except para SQLAlchemyError + ImportError (graceful fallback)
- Logging level: INFO para estado, WARNING para discrepancias, DEBUG para técnico

**Versión actual**: 0.10.0 (SemVer: MINOR bump por nuevas clases públicas sin breaking changes)

### [Testing Strategy for Variable Validation]
**Hecho verificable**: Unit tests de MySQLVariableValidator deben:
- Mock `connection.execute()` para simular `SHOW VARIABLES` (no BD real required)
- Test success path (valores leídos correctamente)
- Test error paths (excepción en query, parsing failure, empty result)
- Test log output (assert via caplog mock)
- Test format_bytes() con edge cases (0, 1024, 1M, 1G bytes)

**Coverage**: 18 tests en test_mysql_variables_config.py, todos pasando

### [Future Enhancement Opportunities]
**No Bloqueado**: Las siguientes mejoras NO están en scope actual pero son candidatas para próximas sesiones:
1. Soporte SET GLOBAL automático (requiere SUPER privilege; user authorization workflow)
2. Dashboard en time de monitoreo (variables trending)
3. ML/Heurística mejorada (aprender de workloads reales)
4. Integración con DumpConfig (auto-recommend commit_every_n_chunks basado en innodb_buffer_pool_size)
5. Validación para otros BBDD (PostgreSQL, Oracle, SQL Server — formatos diferentes)

---

## Veredicto final

**Estado**: ✅ **CLOSED** (GO)

**Completado**:
- ✅ Fase PLAN: Estrategia validada, sin expansion de alcance
- ✅ Fase AUDIT_PLAN: Riesgos identificados y mitigados
- ✅ Fase IMPLEMENT: 4 capas integradas (Validator + Config + Strategy + BulkCrud)
- ✅ Fase AUDIT_CODE: Lint, type-check, pytest, backward compatibility validadas
- ✅ Fase VERSION: CHANGELOG actualizado, PR #18 creada y OPEN

**Pendientes (NO blockeantes para merge)**:
- [ ] Review + approval de PR #18 por maintainers
- [ ] Merge a main branch
- [ ] Tag + release (ej: v0.10.0)
- [ ] PyPI publish (manual step si aplica)

**Handoff para Futuras IAs**:
- Referir a `.github/SHARED_INSTRUCTIONS.md` para contexto arquitectónico
- Referir a `CHANGELOG.md` [Unreleased] → Added para documentación técnica completa
- Referir a esta TRACEABILITY.md para hechos verificables y directrices
- Pattern replicable para otras validaciones BD (PostgreSQL SHOW, Oracle v$parameter, etc.)

---

**PR**: https://github.com/fmanza/util_bbdd/pull/18
**Rama**: develop → main
**Sesión ID**: 2026-06-01g
**Fecha**: 2026-06-01
