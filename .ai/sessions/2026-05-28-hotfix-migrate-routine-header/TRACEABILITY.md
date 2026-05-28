# TRACEABILITY

## Session metadata
- id: 2026-05-28-hotfix-migrate-routine-header
- fecha: 2026-05-28
- rama: develop
- skill: hotfix
- fase: FIX → AUDIT_CODE → TESTS

## Prompt issued

```
Actualmente el módulo src\util_bbdd\doc documenta correctamente las DDL de
Procedures y Funciones en MariaDB, el módulo src\util_bbdd\migrate, cuando
va de MariaDB a otro motor no saca el nombre de la Procedure o Funcion, no
se puede saber si es una u otra. La nota
"-- NOTE: requires manual review (see migration warnings)" debe seguir saliendo.
Restricciones: el módulo src\util_bbdd\doc no se toca
```

## Context supplied
- `src/util_bbdd/migrate/emitters/` — 4 emitters (mariadb, postgresql, sqlserver, oracle)
- `src/util_bbdd/migrate/ir/models.py` — `CanonicalRoutine` con campos `name`, `routine_type`, `body`
- `src/util_bbdd/migrate/extractors/mariadb.py` — `ROUTINE_DEFINITION` de MariaDB
- `src/util_bbdd/migrate/transformers/_base_transformer.py` — `_transform_routine` siempre añade warning
- `tests/unit/migrate/test_routines_*_emitter.py` — tests previos de los 4 emitters

## Root cause

`INFORMATION_SCHEMA.ROUTINES.ROUTINE_DEFINITION` en MariaDB contiene solo el cuerpo
(BEGIN...END), NO la cabecera `CREATE PROCEDURE/FUNCTION nombre`. El método
`_emit_create_routine()` en los 4 emitters volcaba el body directamente sin ningún
comentario previo que identificara el nombre ni el tipo de la rutina. El resultado era:

```sql
-- NOTE: requires manual review (see migration warnings)
BEGIN
  -- body aquí
END
```

Sin ninguna indicación de si es PROCEDURE o FUNCTION, ni del nombre.

## Fix aplicado

En los 4 emitters, en `_emit_create_routine()`, se añade la línea:

```python
lines.append(f"-- {routine.routine_type}: {quote_fn(routine.name)}")
```

Inmediatamente después del bloque `is_package_member` y antes de `if routine.warnings`.
La función de quoting es específica de cada motor:

| Emitter | Quoting | Ejemplo |
|---|---|---|
| `mariadb.py` | `` _bt `` (backtick) | `` -- PROCEDURE: `SP_TEST` `` |
| `postgresql.py` | `_dq` (double-quote) | `-- PROCEDURE: "sp_test"` |
| `sqlserver.py` | `_br` (bracket) | `-- PROCEDURE: [SP_TEST]` |
| `oracle.py` | `_dq` (double-quote uppercase) | `-- PROCEDURE: "SP_TEST"` |

**Nota Oracle**: el bloque `is_package_member` hace `return` temprano en Oracle, por lo
que la línea de cabecera solo aparece para rutinas no-package, evitando redundancia.
El comportamiento del NOTE (`-- NOTE: requires manual review (see migration warnings)`)
se mantiene inalterado: aparece cuando `routine.warnings` es no vacío (siempre tras
`_transform_routine` en `_base_transformer.py`).

## Artefactos generados

| Artefacto | Ruta | Cambio |
|---|---|---|
| Fix emitter MariaDB | `src/util_bbdd/migrate/emitters/mariadb.py` | +1 línea `-- {type}: {name}` |
| Fix emitter PostgreSQL | `src/util_bbdd/migrate/emitters/postgresql.py` | +1 línea |
| Fix emitter SQL Server | `src/util_bbdd/migrate/emitters/sqlserver.py` | +1 línea |
| Fix emitter Oracle | `src/util_bbdd/migrate/emitters/oracle.py` | +1 línea |
| Tests MariaDB emitter | `tests/unit/migrate/test_routines_mariadb_emitter.py` | +3 tests |
| Tests PostgreSQL emitter | `tests/unit/migrate/test_routines_postgresql_emitter.py` | +3 tests |
| Tests SQL Server emitter | `tests/unit/migrate/test_routines_sqlserver_emitter.py` | +3 tests |
| Tests Oracle emitter | `tests/unit/migrate/test_routines_oracle_emitter.py` | +3 tests |

**Tests resultado**: 44/44 passed (los 4 ficheros de test, incluidos los 12 nuevos).

## Directrices para Futuras IAs

- **[migrate/emitters] cabecera de rutina**: toda rutina emitida por cualquier emitter
  incluye `-- {PROCEDURE|FUNCTION}: {quoted_name}` como primera línea (tras PACKAGE MEMBER
  si aplica). Es parte del contrato de salida: el usuario debe poder identificar la rutina
  sin leer el body. No eliminar esta línea en refactors.

- **[migrate/emitters] NOTE vs header**: el `-- NOTE: requires manual review` es condicional
  a `routine.warnings`; el header de tipo/nombre es INCONDICIONAL. Son dos responsabilidades
  distintas: el NOTE informa del estado de transformación; el header identifica la rutina.

- **[migrate/extractors/mariadb.py] ROUTINE_DEFINITION**: MariaDB devuelve solo el body
  (BEGIN...END), NO el DDL completo. La cabecera `CREATE PROCEDURE/FUNCTION nombre(...)` no
  está en el body. Por eso el emitter debe añadirla como comentario.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre: Ninguno. 44 tests verdes, ruff y mypy no regresionan.
