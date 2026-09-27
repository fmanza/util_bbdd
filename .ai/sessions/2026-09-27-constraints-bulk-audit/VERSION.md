# VERSION — Veredicto y Cierre de Sesión

**Sesión**: 2026-09-27-constraints-bulk-audit
**Módulo**: `BulkCrud.maintenance_scope`
**Fecha**: 2026-09-27
**Estado**: ✅ CERRADA

---

## 🏁 Veredicto final

### **APROBADO**

Todas las fases completadas y auditadas. `BulkCrud.maintenance_scope` es seguro para
producción en todos los motores soportados.

---

## 📦 Commits de la sesión

| Commit | Tipo | Descripción |
|--------|------|-------------|
| `13576b5` | fix | Fase 0 (H-01) + Fase 1 (H-02): orphan-check PG + soporte Oracle |
| `35d238f` | feat | Fase 2 (H-05/H-07): `MaintenanceScopeResult` + `require_optimization` |
| `bbed32a` | fix | AUDIT_CODE: A-01/A-02/A-03/A-04 |
| `d64f791` | fix | AUDIT_CODE: A-05/A-06 (informativos) |

**Archivos modificados**: `bulk/crud.py`, `bulk/_models.py`, `bulk/__init__.py`, `tests/unit/bulk/test_maintenance_scope.py`

---

## 📊 Estado final por hallazgo

| ID | Hallazgo | Severidad | Estado |
|----|----------|-----------|--------|
| H-01 | PostgreSQL no valida FK tras ENABLE TRIGGER ALL | 🔴 CRÍTICA | ✅ Corregido |
| H-02 | Oracle sin soporte en `maintenance_scope` | 🟠 ALTA | ✅ Implementado |
| H-03 | MySQL InnoDB: `disable_indexes` = no-op | 🟡 MEDIA | ℹ️ Documentado (comportamiento correcto) |
| H-04 | SQL Server: `disable_indexes` con CLUSTERED PK | 🟡 MEDIA | ℹ️ Documentado (safety guard correcto) |
| H-05 | PostgreSQL: fallo silencioso sin privilegios | 🟡 MEDIA | ✅ `require_optimization` + A-05 |
| H-06 | SQLite sin soporte, sin documentar | 🟢 BAJA | ✅ Documentado en docstring |
| H-07 | Sin `ConstraintResult` en `maintenance_scope` | 🟢 INFO | ✅ `MaintenanceScopeResult` |
| A-01 | Warning duplicado antes de RuntimeError | 🟡 MEDIA | ✅ Corregido |
| A-02 | `zip(strict=True)` sin guarda `ValueError` | 🟡 MEDIA | ✅ Corregido (length guard) |
| A-03 | `inspect()` falla sin log en producción | 🟢 BAJA | ✅ `logger.debug` añadido |
| A-04 | Tipos no exportados en `__init__.py` | 🟢 INFO | ✅ Exportados |
| A-05 | `require_optimization` ignorado en SQLite | 🟢 INFO | ✅ Corregido |
| A-06 | `constraint_results=[]` ambiguo con `optimization_applied=True` | 🟢 INFO | ✅ `unverified` entry |

---

## 🧪 Cobertura de tests

**`tests/unit/bulk/test_maintenance_scope.py`**: 31 tests antes → 59 tests al cierre (+28)

| Clase nueva | Tests |
|-------------|-------|
| `TestMaintenanceScopeOracle` | 8 |
| `TestMaintenanceScopePostgreSQLOrphanCheck` | 4 |
| `TestMaintenanceScopeResult` | 9 |
| `TestMaintenanceScopeRequireOptimization` | 7 |

**Suite completa `tests/unit/bulk/`**: 677 tests, 0 fallos.

---

## 📐 Nuevas APIs públicas

```python
from util_bbdd.bulk import (
    BulkCrud,
    MaintenanceScopeResult,          # nuevo
    MaintenanceScopeConstraintResult, # nuevo
)

# Uso típico
with bulk.bulk_session():
    with bulk.maintenance_scope(
        "orders",
        require_optimization=True,  # nuevo: lanza si no se puede optimizar
    ) as ms:
        bulk.bulk_insert_from_df(df, "orders")

# Resultados disponibles tras el bloque
print(ms.optimization_applied)      # True si se desactivaron constraints
for r in ms.constraint_results:
    print(r.constraint_name, r.status, r.error_msg)
# PostgreSQL: una entrada por FK (enabled | failed si hay huérfanos)
# SQL Server: [ALL, enabled]
# MySQL: [FOREIGN_KEY_CHECKS, unverified]
# Oracle: una entrada por constraint individual
```

---

## 🔗 Directrices para futuras IAs

- `dump._constraints.ConstraintManager` y `BulkCrud.maintenance_scope` comparten
  `disable_table_integrity_sql` / `enable_table_integrity_sql` de `bulk/_support/dialect.py`.
  Cualquier cambio en el SQL de desactivación debe propagarse a ambos.
- El orphan-check de PostgreSQL usa `inspect(self.engine)` (no `inspect(conn)`) para
  obtener FK metadata; fallará silenciosamente con engines mock. Tests que necesiten
  testear el orphan-check deben patchear `util_bbdd.bulk.crud.inspect`.
- `require_optimization=True` lanza para dialectos no soportados; si se añade soporte
  a un nuevo dialecto, actualizar `__maintenance_disable_constraints` antes de que
  llegue al `return False, False, []` final.

---

*VERSION cerrada: 2026-09-27 | Commits: 13576b5 → d64f791*

**Sesión**: 2026-09-27-constraints-bulk-audit
**Módulo**: `BulkCrud.maintenance_scope`
**Fecha**: 2026-09-27

---

## 🏁 Veredicto

### **APROBADO CON CONDICIONES**

`BulkCrud.maintenance_scope` es funcional y aporta mejora real en MySQL, PostgreSQL y SQL Server. El uso en producción con PostgreSQL tiene un **riesgo de integridad latente** (H-01) que debe resolverse antes de considerar el módulo maduro para cargas no pre-validadas.

---

## 📊 Impacto estimado actual vs. potencial

### Con `maintenance_scope` tal como está hoy (tabla `orders`, 100K INSERT)

| Motor | Baseline con FK (est.) | Con `maintenance_scope` | Mejora real | Riesgo |
|-------|------------------------|-------------------------|-------------|--------|
| PostgreSQL | ~2.6 s | ~2.0–2.2 s | **~15–20%** | 🔴 H-01 activo |
| MySQL/MariaDB | ~3.4 s | ~2.6–2.8 s | **~18–23%** | ✅ Seguro |
| SQL Server | ~3.5 s | ~2.1–2.3 s | **~34–40%** | ✅ `WITH CHECK` valida |
| Oracle | ~3.2 s | ~3.2 s (sin efecto) | **0%** | ⚠️ No implementado |
| SQLite | ~1.6 s | ~1.6 s (sin efecto) | **0%** | ⚠️ No implementado |

### Potencial tras correcciones (H-01 + H-02)

| Motor | Con mejoras | Mejora potencial |
|-------|-------------|-----------------|
| PostgreSQL | ~2.0 s | ~23%  + validación segura |
| Oracle | ~2.2–2.6 s | **~19–31%** (implementando H-02) |

---

## 🚀 Roadmap de mejoras

### Fase 0 — Quick wins (< 1 día, blocker para producción PostgreSQL)

| Tarea | Hallazgo | Impacto seguridad | Esfuerzo |
|-------|----------|-------------------|---------|
| Añadir orphan-check FK en PostgreSQL tras `ENABLE TRIGGER ALL` | H-01 | 🔴 CRÍTICO | ~2h |
| Documentar `maintenance_scope` con limitaciones por motor | H-03, H-04, H-05, H-06 | Claridad | ~1h |

**SQL de orphan-check a añadir** (reutilizar patrón de `dump._constraints._find_fk_orphan_pg`):
```python
# En __maintenance_enable_constraints, rama postgresql:
conn.execute(text(enable_table_integrity_sql(dialect, quoted_name)))
# Verificar huérfanos usando get_foreign_keys(tabla)
for fk in insp.get_foreign_keys(tabla_name):
    orphan = _find_fk_orphan_pg(conn, tabla_name, fk)
    if orphan:
        raise IntegrityError(f"FK violation tras maintenance_scope: {orphan}")
```

---

### Fase 1 — Oracle support (1–3 días, ALTA prioridad)

| Tarea | Hallazgo | Impacto rendimiento | Esfuerzo |
|-------|----------|---------------------|---------|
| Implementar `_disable_oracle` / `_enable_oracle` en `maintenance_scope` | H-02 | 19–31% mejora | ~4h |
| Tests de integración Oracle `maintenance_scope` | H-02 | Cobertura | ~2h |

**Implementación sugerida** (ya existe en `dump._constraints`):
```python
# En __maintenance_disable_constraints, añadir rama Oracle
if dialect == "oracle":
    for constraint_name in _fetch_oracle_constraints(conn, tabla):
        conn.execute(text(f"ALTER TABLE {quoted_name} DISABLE CONSTRAINT {constraint_name}"))
    return False, False  # no usa los flags pg/mssql
```

---

### Fase 2 — API y observabilidad (1 semana, MEDIA prioridad)

| Tarea | Hallazgo | Impacto | Esfuerzo |
|-------|----------|---------|---------|
| `maintenance_scope` retorna `list[ConstraintResult]` al salir | H-07 | Observabilidad | ~3h |
| Parámetro `require_optimization: bool = False` | H-05 | Ergonomía | ~1h |
| Warning explícito "optimización no aplicada" (sin privilegios PostgreSQL) | H-05 | UX | ~30min |

---

## 📋 Checklist de uso seguro (hasta que Fase 0 se aplique)

### PostgreSQL
```bash
# Pre-requisito: verificar que el usuario es owner de la tabla
SELECT tableowner FROM pg_tables WHERE tablename = 'orders';

# Pre-requisito: pre-validar datos ANTES de la carga
SELECT COUNT(*) FROM df WHERE user_id NOT IN (SELECT id FROM users);
# → debe ser 0

# Usar maintenance_scope
with bulk.bulk_session():
    with bulk.maintenance_scope("orders"):
        bulk.bulk_insert_from_df(df, "orders")

# Post-carga: validar manualmente
SELECT COUNT(*) FROM orders o
WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = o.user_id);
# → debe ser 0
```

### MySQL / MariaDB
```bash
# maintenance_scope seguro: FK_CHECKS=1 se restaura automáticamente
# No requiere validación adicional si los datos son confiables

with bulk.bulk_session():
    with bulk.maintenance_scope("orders"):
        bulk.bulk_insert_from_df(df, "orders")
```

### SQL Server
```bash
# maintenance_scope más seguro: WITH CHECK CHECK CONSTRAINT valida al restaurar
# Si hay violaciones, lanza excepción en el re-enable

with bulk.bulk_session():
    with bulk.maintenance_scope("orders", disable_indexes=False):  # PK CLUSTERED → disable_indexes no tiene efecto
        bulk.bulk_insert_from_df(df, "orders")
```

### Oracle (hasta H-02 implementado)
```bash
# maintenance_scope no tiene efecto en Oracle
# Alternativa: pre-validar datos + carga directa
# O: usar dump.ConstraintManager si aplica al caso
bulk.bulk_insert_from_df(df, "orders")  # sin maintenance_scope
```

---

## 📊 Métricas esperadas

| Escenario | Hoy | Post-Fase 0 | Post-Fase 1 |
|-----------|-----|------------|------------|
| PostgreSQL 100K INSERT con FK | ~2.6 s | ~2.0 s (+23%) | ~2.0 s (+23%) |
| Oracle 100K INSERT con FK | ~3.2 s | ~3.2 s (sin cambio) | ~2.2 s (+31%) |
| MySQL 100K INSERT con FK | ~3.4 s | ~2.7 s (+21%) | ~2.7 s |
| SQL Server 100K INSERT con FK | ~3.5 s | ~2.2 s (+37%) | ~2.2 s |
| **Mejora total (promedio)** | — | **+25%** | **+28%** |

---

## 🔗 Referencias de código

| Archivo | Líneas | Relevancia |
|---------|--------|-----------|
| `src/util_bbdd/bulk/crud.py` | 1095–1305 | `maintenance_scope` completo |
| `src/util_bbdd/bulk/_support/dialect.py` | 1–47 | SQL de desactivación por motor |
| `src/util_bbdd/dump/_constraints.py` | 1–430 | Implementación de referencia (Oracle + PG validation) |
| `tests/integration/conftest.py` | ~1–80 | DDL con FK y UNIQUE (tabla `orders`, `users`) |
| `bench_results/20260924_p03_despues/` | — | Baseline de rendimiento sin constraints |

---

*VERSION v1.0 · 2026-09-27 · Veredicto: APROBADO CON CONDICIONES*
