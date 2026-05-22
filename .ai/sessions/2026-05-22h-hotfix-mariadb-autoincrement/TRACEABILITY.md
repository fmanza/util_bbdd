# TRACEABILITY

## Session metadata
- id: 2026-05-22h-hotfix-mariadb-autoincrement
- fecha: 2026-05-22
- rama: develop
- skill: hotfix
- fase: AUDIT_CODE (Workflow Director) + IMPLEMENT (Hotfix Responder)

## Prompt issued
> Bug: al migrar hacia MariaDB, columnas AUTO_INCREMENT no siempre emiten INT(11).
> Alcance: emitters/mariadb.py + tests/unit/migrate/test_emitter.py.
> Restricciones: fix mínimo, sin refactorizar transformers; BIGINT AUTO_INCREMENT
> también debe emitirse como INT(11); no cambiar columnas que NO son AUTO_INCREMENT.

## Context supplied
- `src/util_bbdd/migrate/emitters/mariadb.py` — método `_emit_column()`
- `src/util_bbdd/migrate/transformers/sqlserver_to_mariadb.py` — mapea `INT` IDENTITY → `"INT"`
- `src/util_bbdd/migrate/transformers/postgresql_to_mariadb.py` — mapea `INTEGER` SERIAL → `"INT"`
- `src/util_bbdd/migrate/transformers/oracle_to_mariadb.py` — `_with_int_width` condicional
- `tests/unit/migrate/test_emitter.py` — test `test_auto_increment_column` existente
- `_compat/type_map_sqlserver_to_mariadb.py` y `type_map_postgresql_to_mariadb.py`

## AI output summary
- **RCA confirmado (Workflow Director)**: `_emit_column()` usa `col.target_type` sin normalizar; regla "AUTO_INCREMENT → INT(11)" ausente en el emitter.
- **Archivos candidatos identificados**: `emitters/mariadb.py` como punto único de corrección (afecta todos los flujos → MariaDB).
- **Fix aplicado** en `emitters/mariadb.py` → `_emit_column()`: `col_type = "INT(11)" if col.auto_increment else col.target_type` (1 línea + comentario).
- **Tests actualizados** en `tests/unit/migrate/test_emitter.py`:
  - `test_auto_increment_column`: ahora valida `INT(11) NOT NULL AUTO_INCREMENT` (antes sólo `AUTO_INCREMENT`).
  - `test_auto_increment_always_emits_int11` (nuevo, `@pytest.mark.parametrize` ×5): cubre `INT`, `BIGINT`, `SMALLINT`, `INT(11)`, `BIGINT(20)` como tipos fuente.
  - `test_non_auto_increment_preserves_original_type` (nuevo): garantiza columnas sin AUTO_INCREMENT no se ven afectadas.
- **import pytest** añadido al archivo de tests.
- **Resultados**: 25/25 tests en `test_emitter.py` ✓; 65/65 en planner tests ✓; 0 regresiones.

## Artefactos generados

| Artefacto           | Ruta                                               | Estado     |
|---------------------|----------------------------------------------------|------------|
| FIX                 | `src/util_bbdd/migrate/emitters/mariadb.py`        | completado |
| TESTS               | `tests/unit/migrate/test_emitter.py`               | completado |
| TRACEABILITY        | `.ai/sessions/2026-05-22h-hotfix-mariadb-autoincrement/TRACEABILITY.md` | completado |

## Directrices para Futuras IAs

- **[migrate/emitter/mariadb]**: La regla "columna AUTO_INCREMENT → tipo `INT(11)`" vive en `_emit_column()` del emitter, NO en los transformers. Los transformers preservan `auto_increment=True` en el IR; el emitter aplica la convención de tipo al emitir DDL. No mover esta lógica a los transformers.
- **[migrate/mariadb/auto_increment]**: `BIGINT`, `SMALLINT` y cualquier otro entero con `auto_increment=True` se emiten como `INT(11)`. El display width `(11)` es convencional en MariaDB/MySQL para PKs de 32 bits. Si en el futuro se requiere soporte explícito para `BIGINT AUTO_INCREMENT`, se deberá añadir un campo `auto_increment_type: str` al IR o un parámetro en el emitter.
- **[migrate/tests/emitter]**: El test `test_auto_increment_always_emits_int11` es parametrizado con los tipos fuente más comunes. Si se añaden nuevos motores fuente con tipos enteros distintos, añadir un nuevo parámetro al test.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. Fix mínimo, sin deuda residual.
