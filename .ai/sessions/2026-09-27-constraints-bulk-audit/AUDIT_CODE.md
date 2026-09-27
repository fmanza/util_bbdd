# AUDIT_CODE — Hallazgos Técnicos: `BulkCrud.maintenance_scope`

**Sesión**: 2026-09-27-constraints-bulk-audit
**Fuente**: `src/util_bbdd/bulk/crud.py` (lines 1095–1305), `src/util_bbdd/bulk/_support/dialect.py`, `src/util_bbdd/dump/_constraints.py`
**Referencia baseline**: bench_results/20260924_p03_despues (tabla plana, 1M filas)

---

## Hallazgo H-01 — Divergencia crítica: PostgreSQL no valida FK tras re-habilitar

**Severidad**: 🔴 CRÍTICA
**Tipo de Constraint**: FOREIGN KEY
**Tabla/Constraint**: `orders.user_id → users.id`
**Descripción**:
`DISABLE TRIGGER ALL` en PostgreSQL NO marca las FK como `NOT VALID`. Al ejecutar `ENABLE TRIGGER ALL` (la restauración de `maintenance_scope`), PostgreSQL da los triggers por válidos **sin comprobar ninguna fila**. Filas huérfanas cargadas durante el bulk load quedarán en base de datos violando la integridad referencial, y `VALIDATE CONSTRAINT` posterior no las detecta tampoco.

El mismo problema fue documentado y corregido en `dump._constraints.py` (comentario PD-04, línea ~355):
```
PD-04: DISABLE TRIGGER ALL no marca la FK como NOT VALID, así que VALIDATE CONSTRAINT
no comprueba nada y una fila huérfana cargada con los triggers desactivados pasaba como
"enabled".
```
La corrección en `dump` añade una query de orphan check explícita (`_find_fk_orphan_pg`).
`BulkCrud.maintenance_scope` **no tiene esa corrección**.

**Impacto estimado**: Silencioso — no falla, no avisa. Riesgo de corrupción latente.
**BBDD específica**: PostgreSQL únicamente
**Confirmación**: CONFIRMADA (código fuente y comentario PD-04)

### Evidencia
```python
# crud.py ~1297 — re-habilitación sin validación
elif dialect == "postgresql" and pg_disabled:
    conn.execute(text(enable_table_integrity_sql(dialect, quoted_name)))
    # → ALTER TABLE orders ENABLE TRIGGER ALL
    # NO llama VALIDATE CONSTRAINT ni verifica huérfanos
```
```python
# dump/_constraints.py ~330 — versión correcta (con orphan check)
conn.execute(text(f"ALTER TABLE {self._qt(table)} VALIDATE CONSTRAINT {fk_name}"))
orphan_msg = self._find_fk_orphan_pg(conn, table, fk_name)  # ← esto falta en BulkCrud
```

### Estrategia de mitigación
Añadir query post-enable en `__maintenance_enable_constraints` para PostgreSQL:
```python
# Opción A: usar el mismo _find_fk_orphan_pg que tiene dump._constraints
# Opción B: validación simple
SELECT COUNT(*) FROM orders o
WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = o.user_id)
```

### Recomendación
**BLOCKER** antes de usar `maintenance_scope` en producción con PostgreSQL y datos no pre-validados.
Añadir parámetro `validate_after: bool = True` que ejecute las queries de verificación antes de confirmar el re-enable.

---

## Hallazgo H-02 — Oracle: sin soporte en `maintenance_scope`

**Severidad**: 🟠 ALTA
**Tipo de Constraint**: FK, UK, CHECK
**Tabla/Constraint**: Todas las constraints de Oracle
**Descripción**:
`__maintenance_disable_constraints` retorna `(False, False)` para Oracle sin ejecutar ningún SQL. El usuario invoca `maintenance_scope("orders")` en Oracle creyendo que los constraints se desactivan — no ocurre nada y la carga es tan lenta como sin `maintenance_scope`.

`dump.ConstraintManager` sí implementa Oracle completo (`_disable_oracle`, `_enable_oracle`) con `ALTER TABLE DISABLE CONSTRAINT` individual por constraint y re-habilitación con `ENABLE VALIDATE`.

**Impacto estimado**: 20–35% pérdida de rendimiento que el usuario esperaría recuperar.
**BBDD específica**: Oracle
**Confirmación**: CONFIRMADA

### Evidencia
```python
# crud.py ~1213 — __maintenance_disable_constraints
if dialect == "mssql":
    conn.execute(text(disable_table_integrity_sql(dialect, quoted_name)))
    return False, True
return False, False   # ← Oracle y SQLite caen aquí silenciosamente
```
```python
# dump/_constraints.py ~390 — Oracle sí implementado
for name in names:  # FK + CHECK (no SYS_C) + UNIQUE
    conn.execute(text(f"ALTER TABLE {table} DISABLE CONSTRAINT {name}"))
```

### Recomendación
Reutilizar o adaptar la lógica de `dump.ConstraintManager._disable_oracle` en `maintenance_scope`.
Impacto de implementación: BAJO (el código ya existe en el mismo repositorio).

---

## Hallazgo H-03 — MySQL InnoDB: DISABLE KEYS = no-op documentado, sin alternativa

**Severidad**: 🟡 MEDIA
**Tipo de Constraint**: FOREIGN KEY, ÍNDICE
**Tabla/Constraint**: FK + índices secundarios en MySQL/InnoDB
**Descripción**:
`maintenance_scope(disable_indexes=True)` en MySQL solo ejecuta `DISABLE KEYS` si el storage engine es MyISAM o Aria. En InnoDB (default desde MySQL 5.5+) se omite con un log INFO. El usuario no recibe error; simplemente los índices secundarios siguen activos durante la carga.

La desactivación de FK (`FOREIGN_KEY_CHECKS=0`) sí funciona y es la optimización más impactante en MySQL.

**Impacto estimado**: `disable_indexes=True` en MySQL InnoDB = 0% mejora adicional sobre FK desactivado.
**BBDD específica**: MySQL, MariaDB (InnoDB)
**Confirmación**: CONFIRMADA

### Evidencia
```python
# crud.py ~1242
storage_engine = conn.execute(text(fetch_table_storage_engine_sql()), ...).scalar()
if str(storage_engine or "").upper() in ("MYISAM", "ARIA"):
    conn.execute(text(f"ALTER TABLE {quoted_name} DISABLE KEYS"))
    return True
self.logger.info(f"ℹ️ Se omite DISABLE KEYS en {tabla_destino}: motor {storage_engine}...")
return False  # → indexes_disabled = False → no se restaura nada
```

### Alternativa documentada
Para MySQL InnoDB con alto volumen, la alternativa es:
1. FK desactivadas (`maintenance_scope` con `disable_constraints=True`) — ya funciona → ~20–25% mejora
2. `INSERT DELAYED` o `LOAD DATA INFILE` fuera del scope de `BulkCrud`
3. No hay alternativa dentro de `BulkCrud` para deshabilitar índices InnoDB

### Recomendación
Documentar explícitamente el comportamiento en docstring. Añadir advertencia `logger.info` al inicio de `maintenance_scope` si el usuario pide `disable_indexes=True` en MySQL/InnoDB.

---

## Hallazgo H-04 — SQL Server: índices no deshabilitados si hay CLUSTERED index

**Severidad**: 🟡 MEDIA
**Tipo de Constraint**: ÍNDICE CLUSTERED
**Tabla/Constraint**: Índice clustered de PK (típico en todas las tablas SQL Server)
**Descripción**:
`maintenance_scope(disable_indexes=True)` en SQL Server ejecuta `ALTER INDEX ALL ON table DISABLE` SOLO si la tabla no tiene índice CLUSTERED. Como prácticamente toda tabla de producción en SQL Server tiene una PK que genera un índice CLUSTERED, `disable_indexes=True` **nunca tiene efecto** en tablas de producción normales.

**Impacto estimado**: El usuario espera mejora de ~25–35% con `disable_indexes=True`; obtiene 0%.
**BBDD específica**: SQL Server
**Confirmación**: CONFIRMADA

### Evidencia
```python
# crud.py ~1258
has_clustered = conn.execute(text(fetch_clustered_index_count_sql()), {"tbl": tabla_destino}).scalar()
if has_clustered == 0:
    conn.execute(text(f"ALTER INDEX ALL ON {quoted_name} DISABLE"))
    return True
self.logger.warning(f"⚠️ La tabla {tabla_destino} tiene un índice CLUSTERED. Se omite la desactivación masiva...")
```

### Contexto
En SQL Server, deshabilitar un índice CLUSTERED hace la tabla ilegible (heap). La restricción es correcta como safety guard. Pero el usuario no sabe que `disable_indexes=True` es dead code para su tabla.

### Recomendación
- El comportamiento actual es correcto por seguridad.
- Mejorar la visibilidad: elevar el `logger.warning` a nivel de inicio del `maintenance_scope`, no al momento de deshabilitar.
- Documentar en docstring: `disable_indexes=True` only effective en tablas SQL Server sin PK CLUSTERED.

---

## Hallazgo H-05 — PostgreSQL: privilegios silenciosos — falla sin aviso claro

**Severidad**: 🟡 MEDIA
**Tipo de Constraint**: FK (via TRIGGER ALL)
**Tabla/Constraint**: `orders` (y cualquier tabla)
**Descripción**:
Si el usuario de BBDD no es `SUPERUSER` ni propietario de la tabla, `maintenance_scope` registra un `logger.warning` y continúa **sin desactivar los triggers**. La carga procede normalmente (con constraints activos), pero el usuario puede creer que los constraints están desactivados.

**Impacto estimado**: La operación pierde la optimización sin notificación clara al usuario final.
**BBDD específica**: PostgreSQL
**Confirmación**: CONFIRMADA

### Evidencia
```python
# crud.py ~1218
if can_disable_pg_triggers(conn, tabla):
    conn.execute(text(disable_table_integrity_sql(dialect, quoted_name)))
    return True, False
self.logger.warning(
    f"⚠️ El usuario actual no tiene privilegios suficientes en PostgreSQL "
    f"(requiere SUPERUSER o ser propietario de la tabla). "
    f"Se omite DISABLE TRIGGER en {tabla_destino}."
)
return False, False  # ← sin optimización, sin error
```

### Recomendación
Añadir parámetro `require_optimization: bool = False`. Si `True`, lanzar `RuntimeError` si no es posible desactivar. Si `False` (default), mantener el comportamiento actual pero con log más visible (quizás un segundo warning al salir del scope indicando que la optimización NO fue aplicada).

---

## Hallazgo H-06 — SQLite: sin soporte, sin documentar

**Severidad**: 🟢 BAJA
**Tipo de Constraint**: FOREIGN KEY
**Tabla/Constraint**: FK en SQLite
**Descripción**:
`maintenance_scope` en SQLite es silencioso (no desactiva nada). `PRAGMA foreign_keys = OFF` sería equivalente y trivial de implementar. Sin embargo, SQLite no tiene mecanismo de re-validación automática, por lo que el riesgo de corrupción es ALTO si se insertan datos inválidos.

**Impacto estimado**: 0% mejora (constraints no desactivados); SQLite ya es el motor más rápido en el benchmark (74K filas/s para tabla plana).
**BBDD específica**: SQLite
**Confirmación**: CONFIRMADA

### Recomendación
Para SQLite, el caso de uso de `maintenance_scope` es poco relevante (SQLite no es para producción de alto volumen). Documentar explícitamente que SQLite no está soportado.

---

## Hallazgo H-07 — Ausencia de `ConstraintResult` en `maintenance_scope`

**Severidad**: 🟢 BAJA / INFO
**Tipo**: API Design
**Descripción**:
`dump.ConstraintManager.enable_all()` retorna una lista de `ConstraintResult` con el estado de cada constraint re-habilitada (enabled / failed / unverified). `BulkCrud.maintenance_scope` no retorna nada; los errores de re-habilitación solo se logean.

Esto dificulta la detección de violaciones de constraints post-carga desde el código llamador.

**Recomendación**:
- Opción A: `maintenance_scope` acepta un callback `on_restore_result: Callable[[list[ConstraintResult]], None]`
- Opción B: `maintenance_scope` es un dataclass con campo `results` accesible después del `with`
- Opción C (mínimo): Que `maintenance_scope` emita log de nivel ERROR si algún constraint falla al restaurar

---

## Resumen de hallazgos

| ID | Severidad | Motor | Área | Estado |
|----|-----------|-------|------|--------|
| H-01 | 🔴 CRÍTICA | PostgreSQL | No validación FK post-enable | CONFIRMADA |
| H-02 | 🟠 ALTA | Oracle | Sin soporte en `maintenance_scope` | CONFIRMADA |
| H-03 | 🟡 MEDIA | MySQL InnoDB | `disable_indexes` = no-op | CONFIRMADA |
| H-04 | 🟡 MEDIA | SQL Server | `disable_indexes` muerto con CLUSTERED PK | CONFIRMADA |
| H-05 | 🟡 MEDIA | PostgreSQL | Fallo silencioso si sin privilegios | CONFIRMADA |
| H-06 | 🟢 BAJA | SQLite | Sin soporte, sin documentar | CONFIRMADA |
| H-07 | 🟢 BAJA/INFO | Todos | Sin ConstraintResult en BulkCrud | CONFIRMADA |

---

*AUDIT_CODE v1.0 · 2026-09-27*
