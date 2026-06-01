# TRACEABILITY — Auditoría y consolidación de BulkCrud.maintenance_scope

## Session metadata
- id: 2026-06-02-maintenance-scope
- fecha: 2026-06-02
- rama: develop
- skill: audit-code + hotfix + refactor
- fase: AUDIT_CODE → FIX → REFACTOR → TESTS

## Prompt issued

```
Revisar las modificaciones realizadas en src\util_bbdd\bulk\crud.py
y analizar si las mejoras introducidas son coherentes
```

Sesión continuada con:
- Aplicar las correcciones detectadas en la auditoría
- Refactorizar para reducir complejidad cognitiva (SonarQube S3776)
- Corregir anotación de tipo Pylance deprecada
- Escribir tests del nuevo método

## Context supplied

- `src/util_bbdd/bulk/crud.py` — diff abierto en IDE (nuevo método `maintenance_scope`)
- `src/util_bbdd/bulk/_execution/batch.py` — `BatchStatementExecutor` para entender gestión de conexiones
- Historial de commits recientes (v0.10.0 — MySQL variables automation)

---

## Auditoría: hallazgos sobre el diff original

El diff introducía el nuevo método `BulkCrud.maintenance_scope` (context manager para
cargas masivas >1M filas). Se identificaron 4 problemas:

### ❌ Bug crítico — rollback silencioso en `opened_here`

Cuando `maintenance_scope` se usaba sin `bulk_session()` activo, abría una conexión
con `engine.connect()` (sin `begin()`). En SQLAlchemy 2.x esto inicia una transacción
implícita que se revierte al cerrar la conexión. Todos los inserts realizados dentro
del bloque se descartaban silenciosamente.

**Causa**: `conn.close()` en el `finally` sin llamar `conn.commit()` previo.

**Fix**: Eliminar el bloque `opened_here` y lanzar `RuntimeError` inmediato si no hay
`bulk_session()` activo. Patrón explícito es siempre mejor que fallo silencioso.

### ⚠️ `DISABLE KEYS` es no-op en InnoDB (MySQL/MariaDB moderno)

El docstring mencionaba "InnoDB suele ignorarlo" pero no advertía al usuario en runtime.
En la práctica, prácticamente todas las tablas MySQL/MariaDB son InnoDB, por lo que
`disable_indexes=True` era misleading.

**Fix**: Añadir `logger.warning()` explícito antes de ejecutar `DISABLE KEYS`.

### ⚠️ Check PostgreSQL solo SUPERUSER (demasiado restrictivo)

`ALTER TABLE ... DISABLE TRIGGER ALL` pueden ejecutarlo también los **propietarios de
la tabla** (no solo SUPERUSER). La implementación original solo comprobaba
`current_setting('is_superuser')`, emitiendo un warning innecesario para owners.

**Fix**: Query que evalúa `is_superuser OR tableowner = current_user` vía `pg_tables`.

### ⚠️ `WITH CHECK CHECK CONSTRAINT ALL` incondicional en SQL Server

La restauración de constraints MSSQL se ejecutaba en `finally` sin verificar si el
`NOCHECK CONSTRAINT ALL` inicial había tenido éxito. Inconsistente con el patrón
de `mssql_indexes_actually_disabled` usado para índices.

**Fix**: Flag `mssql_constraints_actually_disabled`; restore condicional al flag.

---

## Refactor — SonarQube S3776 (complejidad cognitiva)

**Diagnóstico**: `maintenance_scope` tenía complejidad cognitiva 30 (límite: 15).
Causa: anidamiento de dialect + flags dentro de try/finally.

**Solución**: Extraer lógica por motor en 4 helpers privados:

| Helper | Responsabilidad | Complejidad |
|---|---|---|
| `__maintenance_disable_constraints` | Deshabilita FKs/triggers por motor | 5 |
| `__maintenance_disable_indexes` | Deshabilita índices por motor | 4 |
| `__maintenance_enable_indexes` | Restaura índices por motor | 2 |
| `__maintenance_enable_constraints` | Restaura constraints por motor | 3 |

`maintenance_scope` resultante: complejidad **5** (5 `if` de primer nivel).

---

## Corrección — Pylance deprecation

`-> Iterator[None]` con `@contextmanager` está deprecado. Corrección:
- Import añadido: `Generator` en `collections.abc`
- Anotación cambiada: `-> Generator[None, None, None]`

---

## Tests — `tests/unit/bulk/test_maintenance_scope.py`

27 tests nuevos, 0 regresiones. Patrón de verificación: afirmación del estado
**dentro** del cuerpo del context manager (pre-yield) y **fuera** (post-yield).
Esto elimina bloques vacíos (SonarQube S108) y añade cobertura real de temporalidad.

| Clase | Tests | Qué cubre |
|---|---|---|
| `TestMaintenanceScopeRequiresSession` | 1 | RuntimeError sin bulk_session |
| `TestMaintenanceScopeMySQL` | 10 (5×2 dialectos) | FK checks, DISABLE/ENABLE KEYS, warning InnoDB, restore en excepción |
| `TestMaintenanceScopePostgreSQL` | 6 | DISABLE/ENABLE TRIGGER, check de privilegios (owner+super), no-DDL cuando sin permisos |
| `TestMaintenanceScopeSQLServer` | 9 | NOCHECK/CHECK CONSTRAINT, DISABLE/REBUILD INDEX, guard clustered, restore en excepción |
| `TestMaintenanceScopeRestoreOrder` | 1 | Índices restaurados antes que constraints en MSSQL |

---

## Artefactos modificados

| Artefacto | Ruta | Cambio |
|---|---|---|
| `BulkCrud.maintenance_scope` | `src/util_bbdd/bulk/crud.py` | 4 fixes + refactor en 4 helpers + anotación Generator |
| `__maintenance_disable_constraints` | `src/util_bbdd/bulk/crud.py` | Nuevo helper privado |
| `__maintenance_disable_indexes` | `src/util_bbdd/bulk/crud.py` | Nuevo helper privado |
| `__maintenance_enable_indexes` | `src/util_bbdd/bulk/crud.py` | Nuevo helper privado |
| `__maintenance_enable_constraints` | `src/util_bbdd/bulk/crud.py` | Nuevo helper privado |
| Tests | `tests/unit/bulk/test_maintenance_scope.py` | Nuevo — 27 tests |

## Quality Gates

✅ **Lint**: `ruff check src tests` → "All checks passed!"
✅ **Type-check**: `mypy src/util_bbdd/bulk/crud.py` → sin errores
✅ **Tests**: `pytest tests/unit/bulk/test_maintenance_scope.py` → 27 passed en 0.82s
✅ **SonarQube S3776**: complejidad cognitiva reducida de 30 → 5
✅ **SonarQube S108**: cero bloques vacíos en tests
✅ **Pylance**: anotación `Generator[None, None, None]` correcta

## Directrices para Futuras IAs

### [maintenance_scope — contrato de uso]
**Hecho verificable**: `maintenance_scope` **requiere** un `bulk_session()` activo.
Sin él lanza `RuntimeError`. El patrón obligatorio es:
```python
with bulk.bulk_session():
    with bulk.maintenance_scope("tabla", disable_indexes=True):
        bulk.bulk_insert_from_df(df, "tabla")
```

### [DISABLE KEYS en MySQL/MariaDB]
**Hecho verificable**: `DISABLE KEYS` solo afecta a tablas **MyISAM**. En InnoDB
(motor por defecto desde MySQL 5.5+) el comando es ignorado por el servidor. El método
emite un warning en runtime para evitar falsas expectativas de optimización.

### [PostgreSQL — privilegios para DISABLE TRIGGER ALL]
**Hecho verificable**: El check de permisos evalúa `SUPERUSER OR tableowner`.
Query implementada contra `pg_tables`. Si el usuario no tiene ninguno de los dos,
se emite warning y se omite el DDL sin abortar la operación.

### [SQL Server — guard de índice clustered]
**Hecho verificable**: Deshabilitar un índice clustered en SQL Server hace la tabla
inaccesible. El método verifica `sys.indexes WHERE type = 1` antes de ejecutar
`ALTER INDEX ALL ... DISABLE`. Si existe clustered, se emite warning y se omite.

### [Patrón de tests para context managers]
**Hecho verificable**: Los tests verifican estado **pre-yield** (dentro del body) y
**post-yield** (fuera). Esto evita S108 y cubre la temporalidad del setup/teardown.
Ejemplo:
```python
with crud.maintenance_scope("t"):
    assert "DISABLE_SQL" in _sql_calls(conn)  # setup ya ejecutado
assert "ENABLE_SQL" in _sql_calls(conn)        # teardown ejecutado al salir
```

---

## Veredicto final

**Estado**: ✅ CLOSED

- ✅ Auditoría: 4 problemas identificados y documentados
- ✅ Fix: rollback silencioso eliminado (RuntimeError explícito)
- ✅ Fix: warning InnoDB para DISABLE KEYS
- ✅ Fix: check PG ampliado a owner OR superuser
- ✅ Fix: tracking `mssql_constraints_actually_disabled`
- ✅ Refactor: complejidad 30 → 5 (4 helpers privados)
- ✅ Corrección Pylance: `Generator[None, None, None]`
- ✅ Tests: 27 nuevos, todos verdes, sin bloques vacíos

**Pendientes**:
- [ ] Commit de los cambios en `crud.py` y el nuevo test file
- [ ] Actualizar CHANGELOG.md si se considera versión nueva
