# PLAN — Auditoría de Rendimiento: Desactivación de Constraints en Carga Masiva

**Sesión**: 2026-09-27-constraints-bulk-audit
**Módulo auditado**: `src/util_bbdd/bulk/crud.py` — `BulkCrud.maintenance_scope`
**Complemento**: `src/util_bbdd/dump/_constraints.py` — `ConstraintManager`
**Fecha**: 2026-09-27

---

## 🎯 Escenario elegido

**Tabla**: `orders`
```sql
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    total       DECIMAL(10, 2),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```
Tabla padre:
```sql
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre     TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,            -- ← UNIQUE
    edad       INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Operación**: INSERT masivo de 100K órdenes nuevas con `BulkCrud.bulk_insert_from_df(df, "orders")`
**BBDD**: PostgreSQL · MySQL · Oracle · SQL Server · SQLite
**Baseline referencia** (tabla plana sin constraints, bench_results/20260924_p03_despues):

| Motor      | Tabla plana (filas/s) | 100K → tiempo est. |
|------------|----------------------|-------------------|
| SQLite     | 74 958               | ~1.3 s            |
| PostgreSQL | 50 815               | ~2.0 s            |
| Oracle     | 41 156               | ~2.4 s            |
| MySQL      | 36 589               | ~2.7 s            |
| SQL Server | N/D (no medido)      | ~2.5 s estimado   |

**Estimación con constraints FK + UNIQUE activos** (+25–40% overhead medio):

| Motor      | Con constraints (est.) | Overhead teórico |
|------------|------------------------|------------------|
| SQLite     | ~1.6 s                 | ~25%             |
| PostgreSQL | ~2.6 s                 | ~30%             |
| Oracle     | ~3.2 s                 | ~35%             |
| MySQL      | ~3.4 s                 | ~25%             |
| SQL Server | ~3.5 s                 | ~40%             |

---

## 📋 Inventario de constraints — tabla `orders`

| # | Constraint | Tipo | Tabla | Columna | Acción | Crítico |
|---|-----------|------|-------|---------|--------|---------|
| C1 | PK `orders.id` | PRIMARY KEY | orders | id | AUTOINCREMENT | ✅ Sí |
| C2 | FK `orders.user_id → users.id` | FOREIGN KEY | orders | user_id | ON DELETE CASCADE | ✅ Sí |
| C3 | NOT NULL `orders.user_id` | NOT NULL | orders | user_id | — | ⚠️ Medio |
| C4 | UNIQUE `users.email` | UNIQUE KEY | users | email | — | ⚠️ Medio |
| C5 | PK `users.id` | PRIMARY KEY | users | id | AUTOINCREMENT | ✅ Sí |

**Triggers implícitos en ON DELETE CASCADE**: Al INSERT en `orders`, PostgreSQL crea un trigger interno para validar `user_id → users.id`. Al desactivar triggers con `DISABLE TRIGGER ALL`, este trigger también queda desactivado.

---

## 📊 Matriz de impacto teórico por constraint

| Constraint | Costo operación | Impacto estimado | ¿Desactivable? | Riesgo |
|-----------|----------------|-----------------|----------------|--------|
| C2 — FK CASCADE | Lookup en `users` por cada fila | 15–30% overhead | ✅ Sí | 🔴 ALTO |
| C4 — UNIQUE email | Scan de índice B-tree en `users` | 5–10% en UPDATE/INSERT en `users` | ✅ Sí | ⚠️ MEDIO |
| C3 — NOT NULL | Validación de predicado simple | 1–2% | ⚠️ Solo a nivel app | MUY BAJO |
| C1/C5 — PK | Índice único; mantiene orden en heap | 10–20% | ❌ No recomendado | CRÍTICO |

**Costo dominante**: FK C2 (lookup parent por cada INSERT).
**Estrategia**: Desactivar C2 durante bulk load → re-habilitar y validar.

---

## 🔍 Estado actual: `BulkCrud.maintenance_scope` ya implementado

**Hallazgo fundamental**: `BulkCrud` ya tiene un API de desactivación de constraints:

```python
with bulk.bulk_session():
    with bulk.maintenance_scope("orders", disable_indexes=False):
        bulk.bulk_insert_from_df(df, "orders")
```

Implementación por motor (src/util_bbdd/bulk/crud.py lines 1205–1300):

| Motor | Qué desactiva | Qué re-habilita | Post-validación FK |
|-------|--------------|----------------|-------------------|
| MySQL/MariaDB | `SET SESSION FOREIGN_KEY_CHECKS=0` | `SET SESSION FOREIGN_KEY_CHECKS=1` | ❌ No |
| PostgreSQL | `ALTER TABLE ... DISABLE TRIGGER ALL` | `ALTER TABLE ... ENABLE TRIGGER ALL` | ❌ No |
| SQL Server | `ALTER TABLE ... NOCHECK CONSTRAINT ALL` | `WITH CHECK CHECK CONSTRAINT ALL` | ✅ Sí |
| **Oracle** | **❌ No implementado** | **❌ No implementado** | **❌ N/A** |
| **SQLite** | **❌ No implementado** | **❌ No implementado** | **❌ N/A** |

**Comparativa con `dump.ConstraintManager`**:

| Feature | `BulkCrud.maintenance_scope` | `dump.ConstraintManager` |
|---------|------------------------------|--------------------------|
| MySQL FK | ✅ (sesión) | ✅ (pool events, thread-safe) |
| PostgreSQL triggers | ✅ (requiere owner) | ✅ (best-effort por tabla) |
| PostgreSQL VALIDATE CONSTRAINT | ❌ No | ✅ + orphan check (PD-04) |
| SQL Server NOCHECK | ✅ | ✅ |
| Oracle DISABLE CONSTRAINT | ❌ No | ✅ (FK + CHECK + UK) |
| SQLite PRAGMA | ❌ No | ❌ No |
| Structured results (ConstraintResult) | ❌ Solo logs | ✅ |

---

## 📐 Estrategia de desactivación recomendada

### Orden de operaciones
```
1. Backup / snapshot pre-carga (si entorno productivo)
2. Iniciar bulk_session()
3. Llamar maintenance_scope("orders", disable_constraints=True)
4. bulk_insert_from_df(df, "orders")
5. Al salir del with: restore() automático
6. Validación post-carga: queries de integridad
7. Commit o Rollback según resultado de validación
```

### Queries de validación post-carga (por BBDD)
```sql
-- Validar FK: ¿hay user_id en orders sin fila en users?
-- PostgreSQL
SELECT COUNT(*) FROM orders o
WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = o.user_id);

-- SQL Server / MySQL
SELECT COUNT(*) FROM orders o
LEFT JOIN users u ON u.id = o.user_id
WHERE u.id IS NULL AND o.user_id IS NOT NULL;

-- Oracle
SELECT COUNT(*) FROM orders o
WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = o.user_id);
```

---

## ⏱️ Timeline estimado

| Fase | Tarea | Duración |
|------|-------|---------|
| Pre-carga | Snapshot / backup | 5–30 min |
| Desactivación | maintenance_scope auto | < 1 s |
| Carga masiva | 100K INSERT | 2–4 s |
| Re-habilitación | maintenance_scope auto | < 1 s |
| Validación FK | Query post-carga | < 5 s |
| **Total** | | **~10–35 min** |

---

*PLAN v1.0 · 2026-09-27 · Estado: ✅ APROBADO para AUDIT*
