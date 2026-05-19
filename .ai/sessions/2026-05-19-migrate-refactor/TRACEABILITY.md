# TRACEABILITY

## Session metadata
- id: 2026-05-19-migrate-refactor
- fecha: 2026-05-19
- rama: develop
- skill: refactor (cambios funcionales tras primera ejecución en producción)
- fase: PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
/refactor

Se ha realizado la primera ejecución del módulo migrate y se observa lo siguiente:
- Se necesita poner un valor por defecto al tipo de dato INT en MariaDB que será 11
  - INT(11), este valor se debe permitir su cambio, siendo 0 sin valor solo INT
- Las referencias a tabla fuera del schema migrado tienen que generar DDL se informará
  de ello y se generarán al final del archivo con un comentario.
- El campo de las PRIMARY KEY tiene que ser AUTO_INCREMENT
```

## Context supplied
- `src/util_bbdd/migrate/` — módulo completo implementado en sesión 2026-05-18
- `tests/unit/migrate/` — suite de 82 tests heredada

## AI output summary

### Cambio 1 — INT display width (`int_display_width`)
1. Añadido `_INT_TYPES_AUTOINCREMENT` frozenset en `transformers/oracle_to_mariadb.py`
2. Añadido parámetro `int_display_width: int = 11` a `OracleToMariaDBTransformer.__init__`
3. Añadido método privado `_with_int_width(type_str)` en el transformer
4. Aplicado `_with_int_width` en `_build_target_type` (tipos fijos: `INTEGER`/`INT`)
5. Aplicado `_with_int_width` tras `resolve_number_type` (cubre `NUMBER(5..9,0)` → `INT(11)`)
6. Añadido parámetro `int_display_width: int = 11` a `MigrationPlanner.__init__`
7. `MigrationPlanner.plan` pasa `int_display_width` al transformer

### Cambio 2 — FK externas como ALTER TABLE al final
8. `MariaDBDDLEmitter.emit_statements`: recopila `external_fk_pairs` de todas las tablas
9. Después de los ALTER TABLE circulares, emite un ALTER TABLE por FK externa
10. Cada sentencia lleva un comentario prefijo:
    `-- FK externa: \`FK_EXT\` en \`TABLA\` referencia \`TABLA_EXTERNA\` (fuera del schema migrado) — verificar que existe`
11. Actualizado mensaje de aviso en transformer: `"(omitida)"` → `"ALTER TABLE (al final)"`
    y texto del mensaje actualizado acorde

### Cambio 3 — PK → AUTO_INCREMENT automático
12. Añadido método `_handle_pk_auto_increment(table)` en `OracleToMariaDBTransformer`
    - Solo actúa si `len(primary_key) == 1` (PK compuesta excluida)
    - Solo actúa si el `target_type` es entero (`BIGINT`, `INT`, `SMALLINT`, etc.)
    - No actúa si `auto_increment` ya es True (NEXTVAL ya lo marcó)
    - Setea `auto_increment = True` y `nullable = False`
    - Emite aviso `INFO`
13. `_handle_pk_auto_increment` llamado en `_transform_table` tras `_handle_sequence_columns`

### Documentación
14. Actualizado `docs/api/migrate-oracle-mariadb.md`:
    - Tabla API: firma de `MigrationPlanner` incluye `int_display_width`
    - Tabla de parámetros: nuevo `int_display_width` con restricciones
    - Tabla errores/casos especiales: FK externas → ALTER TABLE (no omitidas)

### Tests
15. `tests/unit/migrate/test_emitter.py`:
    - `test_external_fk_omitted_from_create` → renombrado `test_external_fk_not_inline_in_create_table` (comportamiento cambiado)
    - Añadido `test_external_fk_alter_table_has_comment`
16. `tests/unit/migrate/test_transformer.py`:
    - Añadida clase `TestIntDisplayWidth` (5 tests)
    - Añadida clase `TestPKAutoIncrement` (6 tests)

## Artefactos modificados

| Artefacto | Ruta | Cambio |
|---|---|---|
| Transformer | `src/util_bbdd/migrate/transformers/oracle_to_mariadb.py` | `int_display_width`, `_with_int_width`, `_handle_pk_auto_increment`, warning FK externa |
| Emitter | `src/util_bbdd/migrate/emitters/mariadb.py` | FK externas como ALTER TABLE al final |
| Planner | `src/util_bbdd/migrate/planner.py` | `int_display_width` pasado al transformer |
| Doc API | `docs/api/migrate-oracle-mariadb.md` | Nuevo parámetro + comportamiento FK externas |
| Tests emitter | `tests/unit/migrate/test_emitter.py` | 1 test actualizado + 1 nuevo |
| Tests transformer | `tests/unit/migrate/test_transformer.py` | 11 tests nuevos (2 clases nuevas) |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests migrate | 82 | 94 |
| Tests totales | 2060 | 2072 |
| ruff | ✅ | ✅ |
| mypy | ✅ | ✅ |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre: Ninguno. Cambios funcionales implementados, tests verdes, docs actualizadas.
