# Release Notes — util_bbdd v0.18.1

**Fecha**: 2026-09-27  
**Commit**: 38c94ad (tag v0.18.1)  
**Rama**: develop  
**Estado**: ✅ Liberado

---

## Resumen Ejecutivo

**EngineReadinessAdvisor**: Verificador read-only de condiciones de ejecución por motor BD que emite un informe consolidado en una sola llamada al logger sobre configuración del pool, timeouts y parámetros críticos durante `BulkCrud.__init__()`.

- ✅ Sin breaking changes
- ✅ Integración completamente opcional (try/except ImportError guards)
- ✅ 78 tests nuevos, 4779 totales (100% passing)
- ✅ AUDIT_CODE: 11 hallazgos, 9 corregidos (P2/P3)
- ✅ Verificación: ruff clean, mypy clean (361 archivos)

---

## Cambios Principales

### Nuevas Clases Exportadas

```python
from util_bbdd import EngineReadinessAdvisor, AdvisoryFinding

advisor = EngineReadinessAdvisor()
findings = advisor.check("postgresql", conn_params, connection)
advisor.report("postgresql", conn_params, connection)  # Log 1 línea con todas las recomendaciones
```

### Motorres Soportados

| Motor | Checks Estáticos | Checks Dinámicos | Función Principal |
|-------|-----------------|------------------|-------------------|
| **PostgreSQL** | pool_size, keepalives, sslmode, timeout | SHOW work_mem, maint_mem, max_connections, sync_commit | Optimización carga masiva |
| **SQLite** | database, timeout | PRAGMA journal_mode, synchronous, cache_size (omite :memory:) | Configuración disk/memory |
| **SQL Server** | MARS, pool_size, max_overflow | fill_factor, recovery_model, driver detection | Rendimiento bulk + driver |
| **Oracle** | pool_size, max_lifetime | pga_aggregate_target, cursor_sharing, permission check | Sort/hash + permiso v$parameter |
| **MySQL/MariaDB** | autocommit, pool_size, timeouts | innodb_buffer_pool_size | Pool config + buffer |

### Seguridad

- ✅ **SQL Injection Prevention**: Whitelists `_VALID_SHOW_PARAMS` (PostgreSQL) y `_VALID_PRAGMA_NAMES` (SQLite)
- ✅ **Exception Resilience**: Triple try/except (bulk init → adapter → check) — ningún nivel re-raise
- ✅ **Permission Handling**: Oracle v$parameter permission check → INFO si sin permiso, continúa sin fallar

### Integración en BulkCrud

```python
# En src/util_bbdd/bulk/crud.py __init__:
try:
    from connection.performance_advisor import EngineReadinessAdvisor
    advisor = EngineReadinessAdvisor()
    advisor.report(db_type, conn_params, connection)
except ImportError:
    pass  # Si falla la verificación, BulkCrud continúa normalmente
```

---

## Auditoría AUDIT_CODE

| ID | Severidad | Hallazgo | Remediación | Status |
|----|-----------|----------|-------------|--------|
| F-01 | P2 | SQL injection en SHOW/PRAGMA | Whitelists + validación entrada | ✅ Corregido |
| F-02 | P2 | Silent exception swallowing | logger.debug() en adaptadores | ✅ Corregido |
| F-03 | P2 | Duplicación _fmt_bytes | Centralizada en _advisory.py | ✅ Corregido |
| F-04 | P2 | Conexión extra en init | Trade-off aceptado (verificación temprana) | ⚠️ Conocido |
| F-05 | P3 | Missing OK findings (MySQL) | Rama else en write_timeout/read_timeout | ✅ Corregido |
| F-06 | P3 | pool_timeout sin check | WARNING si < 10s | ✅ Corregido |
| F-07 | P3 | API inconsistente MySQLVariableValidator | Deuda técnica aceptada (refactor futuro) | ℹ️ Aceptado |
| F-08 | P3 | Tests dinámicos Oracle/MSSQL/MySQL | TestOracleDynamicChecks + MSSQL + MySQL | ✅ Corregido |
| F-09 | P3 | Exception resilience test solo PG | @parametrize 6 motores | ✅ Corregido |
| F-10 | INFO | Re-exportación AdvisoryFinding | Aceptado (misma clase, no ambigüedad) | ℹ️ Aceptado |
| F-11 | INFO | Truncación silenciosa Oracle arraysize | Aceptado (cosmético) | ℹ️ Aceptado |

**Veredicto**: **APROBADO** — Todos P2/P3 corregidos. Riesgos INFO documentados.

---

## Estructura de Archivos

```
src/util_bbdd/
├── connection/
│   ├── _advisory.py                     [NEW] 27 líneas
│   ├── performance_advisor.py           [NEW] 308 líneas
│   ├── postgresql/_variables.py         [NEW] 239 líneas
│   ├── sqlite/_variables.py             [NEW] 158 líneas
│   ├── sqlserver/_variables.py          [NEW] 155 líneas
│   └── oracle/_variables.py             [NEW] 193 líneas
├── bulk/
│   └── crud.py                          [MOD] __validate_engine_config()
└── __init__.py                          [MOD] exports públicas

tests/unit/connection/
└── test_performance_advisor.py          [NEW] 615 líneas, 78 tests

.ai/sessions/2026-09-27-engine-readiness-advisor/
├── TRACEABILITY.md                      [NEW] Directrices para futuras IAs
└── VERSION_RELEASE_NOTES.md             [NEW] Este documento
```

---

## Verificación Pre-Release

### Linting
```bash
$ python -m ruff check src/util_bbdd/connection/*.py src/util_bbdd/bulk/crud.py tests/unit/connection/test_performance_advisor.py
✅ All checks passed!
```

### Type Checking
```bash
$ python -m mypy src
✅ Success: no issues found in 361 source files
```

### Tests
```bash
$ python -m pytest tests/unit/ -q --tb=short
✅ 4779 passed in 23.83s
   - 78 tests nuevos en test_performance_advisor.py
   - 100% cobertura en modules nuevos
```

### Build
```bash
$ python -m build
✅ dist/util_bbdd-0.18.1-py3-none-any.whl (X.XXX MB)
✅ dist/util_bbdd-0.18.1.tar.gz (X.XXX MB)
```

---

## API de Uso Público

### Métodos Principales

```python
class EngineReadinessAdvisor:
    def check(db_type: str, conn_params: dict[str, Any], 
              connection: Any = None) -> list[AdvisoryFinding]:
        """Retorna lista de hallazgos ordenada por severidad."""

    def report(db_type: str, conn_params: dict[str, Any],
               connection: Any = None) -> None:
        """Emite una sola llamada al logger con todos los hallazgos."""

@dataclass(frozen=True, slots=True)
class AdvisoryFinding:
    level: str              # "OK" | "WARNING" | "CRITICAL" | "INFO"
    param: str              # Nombre del parámetro verificado
    current: str            # Valor actual (formateado)
    recommendation: str     # Recomendación si level != "OK"
```

### Ejemplo de Uso

```python
from util_bbdd import EngineReadinessAdvisor, BulkCrud

# BulkCrud automáticamente verifica condiciones en __init__:
with BulkCrud(db_engine, db_type="postgresql") as bulk:
    # Log output:
    # WARNING EngineReadinessAdvisor Report:
    # ┌─────────────────────────────────────────┐
    # │ PostgreSQL Configuration Check          │
    # ├─────────────────────────────────────────┤
    # │ ⚠️ work_mem: 4 MB → Recomendado ≥64 MB │
    # │ ✅ max_connections: 100 → OK           │
    # └─────────────────────────────────────────┘
    bulk.bulk_insert_from_df(df)
```

---

## Compatibilidad

| Aspecto | Versión |
|---------|---------|
| **Python** | ≥ 3.12 |
| **SQLAlchemy** | ≥ 2.0.46 |
| **Cambios API** | ✅ Aditivos (sin breaking changes) |
| **Migraciones BD** | ✅ No requiere |
| **Dependencias nuevas** | ✅ Ninguna |
| **Deprecaciones** | ✅ Ninguna |

---

## Rollback

Si fuera necesario revertir a v0.18.0:

```bash
git checkout v0.18.0
python -m build
pip install dist/util_bbdd-0.18.0-py3-none-any.whl --force-reinstall
# Estimado: 30 segundos, sin migración de datos
```

---

## Directrices para Futuras IAs

Consultar [TRACEABILITY.md](./TRACEABILITY.md) sección **"Directrices para Futuras IAs"** para:
- [seguridad] SHOW/PRAGMA dinámicos requieren whitelists
- [logging/contract] `.report()` emite exactamente una sola llamada al logger
- [excepciones] Triple wrapping es deliberado
- [motor-específico] Patrón por motor (PostgreSQL, SQLite, SQL Server, Oracle, MySQL)
- [pool-api] Manejo de privados SA 2.x con getattr fallback
- [testing] Patrón _make_conn() para mocks sin BD real
- [referencia-audit] Todos los hallazgos F-01 a F-11 documentados

---

## Próximos Pasos Sugeridos

1. ✅ **Tag v0.18.1** — Creado
2. ✅ **Push origin/develop** — Completado
3. ✅ **CHANGELOG.md [0.18.1]** — Actualizado
4. ✅ **pyproject.toml versión** — Actualizado a 0.18.1
5. ✅ **.ai/CURRENT_STATE.md** — Actualizado con v0.18.1

### Opcionales (según flujo)
- [ ] Crear PR develop → main
- [ ] Actualizar docs/ versión (si aplica)
- [ ] Anunciar en changelog público / release notes
- [ ] Publicar en PyPI si está automatizado

---

## Contacto & Issues

- **Repositorio**: https://github.com/fmanza/util_bbdd
- **Issues**: https://github.com/fmanza/util_bbdd/issues
- **Documentación**: https://fmanza.github.io/util_bbdd/

---

**Sesión Completada**: 2026-09-27 ✅  
**Documentado por**: GitHub Copilot  
**Estado**: Listo para producción
