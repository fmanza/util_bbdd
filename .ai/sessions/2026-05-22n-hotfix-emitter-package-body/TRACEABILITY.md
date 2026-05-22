# TRACEABILITY — 2026-05-22n-hotfix-emitter-package-body

## Resumen

**Fase**: HOTFIX
**Rama**: develop
**Fecha**: 2026-05-22
**Skill**: hotfix
**Estado**: CLOSED ✅

---

## Solicitud

Al migrar de Oracle al resto de motores (MariaDB, SQL Server, PostgreSQL),
los package members mostraban el comentario de cabecera:

```
-- PACKAGE MEMBER: ADD_DAYS.ADD_DAYS (PROCEDURE)
-- No direct equivalent in MariaDB; manual migration required
```

…pero el cuerpo (body) de la rutina NO aparecía en el DDL generado.

---

## Root Cause Analysis

`_emit_create_routine()` en los 3 emisores no-Oracle hacía `return` anticipado
cuando `routine.is_package_member` era `True`:

```python
if routine.is_package_member:
    pkg = routine.package_name or routine.name
    return (
        f"-- PACKAGE MEMBER: {pkg}.{routine.name} ({routine.routine_type})\n"
        f"-- No direct equivalent in MariaDB; manual migration required"
    )
```

El `return` evitaba que el flujo llegase a `lines.append(routine.body)`.

El mismo patrón afectaba a los emitters de los 3 motores:
- `migrate/emitters/mariadb.py`
- `migrate/emitters/sqlserver.py`
- `migrate/emitters/postgresql.py`

---

## Fix aplicado

Reemplazado `return (...)` por `lines.append(...)` para que la cabecera se
añada como línea de comentario y el flujo continúe a la lógica de body/stub:

```python
if routine.is_package_member:
    pkg = routine.package_name or routine.name
    lines.append(
        f"-- PACKAGE MEMBER: {pkg}.{routine.name} ({routine.routine_type})\n"
        f"-- No direct equivalent in MariaDB; manual migration required"
    )
# <-- flujo continúa: warnings, comment, body o stub TODO
```

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `src/util_bbdd/migrate/emitters/mariadb.py` | `return` → `lines.append` |
| `src/util_bbdd/migrate/emitters/sqlserver.py` | `return` → `lines.append` |
| `src/util_bbdd/migrate/emitters/postgresql.py` | `return` → `lines.append` |
| `tests/unit/migrate/test_routines_mariadb_emitter.py` | Renombraron test + 2 tests nuevos |
| `tests/unit/migrate/test_routines_sqlserver_emitter.py` | Renombraron test + 2 tests nuevos |
| `tests/unit/migrate/test_routines_postgresql_emitter.py` | Renombraron test + 2 tests nuevos |

---

## Validación

- 3317 tests pasando, 0 fallos (vs 3311 antes)
- `test_package_member_body_included_after_header`: body aparece tras cabecera ✅
- `test_package_member_stub_when_no_body`: stub TODO cuando body vacío ✅
- `test_package_member_includes_header_comment`: cabecera + texto "manual migration" ✅
- Oracle emitter no afectado ✅

---

## Commit message

```
fix(migrate): emitters no-Oracle ahora incluyen body de package members Oracle

_emit_create_routine() en MariaDB/SQLServer/PostgreSQL hacía return anticipado
para is_package_member=True, omitiendo el cuerpo de la rutina en el DDL generado.

Cambiado return(...) por lines.append(...) para que el comentario de cabecera
se emita y el flujo continúe a la lógica de body/stub.

Tests: renombrados _comment_only → _includes_header_comment; 2 tests nuevos
por emitter (body_included_after_header, stub_when_no_body). 3317/3317 passed.
```

---

## Directrices para Futuras IAs

- En `_emit_create_routine()`, el patrón correcto para metadata de cabecera es
  `lines.append(...)` nunca `return` — el `return` corta el flujo antes del body.
- Comprobar siempre que el flujo de un emitter "cae hasta el body" para todos
  los casos especiales (`is_package_member`, warnings, etc.).
