# TRACEABILITY — 2026-05-24-hotfix-oracle-routine-exact-copy

## Resumen

**Fase**: HOTFIX
**Rama**: develop
**Fecha**: 2026-05-24
**Skill**: hotfix
**Estado**: CLOSED ✅

---

## Solicitud

Las operaciones PROCEDURE y FUNCTION del módulo `migrate` deben copiarse **tal cual**
se obtienen del motor de origen al script de salida (copia exacta).
El aviso de revisión manual y la notificación de rutinas inaccesibles deben mantenerse.

---

## Root Cause Analysis

`_emit_create_routine()` en el emitter Oracle anteponía `CREATE OR REPLACE` al body:

```python
lines.append(f"CREATE OR REPLACE {routine.body}")
```

Sin embargo, `ALL_SOURCE` en Oracle devuelve las líneas de la rutina **sin** ese prefijo
(la primera línea es `PROCEDURE name (...)` o `FUNCTION name (...)`).
El resultado era un cuerpo modificado, no una copia exacta del origen.

Los emitters de SQL Server, PostgreSQL y MariaDB ya emitían `routine.body` sin modificación,
por lo que el bug era exclusivo del emitter Oracle.

---

## Fix aplicado

Eliminado el prefijo `CREATE OR REPLACE` en `_emit_create_routine()` del emitter Oracle:

```python
# Antes
lines.append(f"CREATE OR REPLACE {routine.body}")

# Después
lines.append(routine.body)
```

Todos los emitters (Oracle, SQL Server, PostgreSQL, MariaDB) emiten ahora el body
**verbatim** tal como lo provee el motor de origen, de forma consistente.

El aviso de revisión manual (`-- NOTE: requires manual review`) y el stub de body
no disponible (`-- TODO: ... body not available`) permanecen intactos.

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `src/util_bbdd/migrate/emitters/oracle.py` | Eliminado prefijo `CREATE OR REPLACE` en `_emit_create_routine()` |
| `tests/unit/migrate/test_routines_oracle_emitter.py` | Tests actualizados: `prepends_create_or_replace` → `body_exact_copy`; aserciones ajustadas |

---

## Validación

- `ruff check src tests` — sin errores ✅
- `mypy src` — sin errores ✅
- `pytest tests/unit/migrate/` — 1302 passed, 0 failures ✅
- `test_emit_procedure_body_exact_copy`: body exacto en output, sin `CREATE OR REPLACE` ✅
- `test_stub_when_no_body`: stub TODO cuando body vacío ✅
- `test_package_member_emits_comment_only`: package members sin DDL ejecutable ✅
- `test_emit_statements_includes_routine`: body completo en emit_statements ✅
- `test_multiple_routines_emitted`: múltiples rutinas emitidas correctamente ✅

---

## Commit message

```
fix(migrate/emitters): Oracle emite body de rutinas verbatim sin CREATE OR REPLACE

ALL_SOURCE devuelve el cuerpo de PROCEDURE/FUNCTION sin prefijo CREATE OR REPLACE.
El emitter Oracle lo añadía artificialmente, produciendo una copia no exacta del origen.

Alineado con SQL Server, PostgreSQL y MariaDB: todos los emitters emiten routine.body
tal cual, sin modificación. El aviso de revisión manual y el stub de body no
disponible se mantienen sin cambios.

Tests: test_emit_procedure_prepends_create_or_replace → test_emit_procedure_body_exact_copy.
1302/1302 passed.
```

---

## Directrices para Futuras IAs

- El body de rutinas extraído de `ALL_SOURCE` (Oracle) comienza con `PROCEDURE`/`FUNCTION`,
  **no** incluye `CREATE OR REPLACE`. El emitter no debe añadirlo.
- El contrato de `_emit_create_routine()` en todos los emitters es emitir `routine.body`
  verbatim. Si se necesita un prefijo específico por dialecto, debe añadirse en el extractor
  o en una capa de transformación explícita, no en el emitter.
- Los avisos de revisión manual (`-- NOTE:`) y stubs de body no disponible (`-- TODO:`)
  son parte del contrato de revisión y deben mantenerse en todos los emitters.
