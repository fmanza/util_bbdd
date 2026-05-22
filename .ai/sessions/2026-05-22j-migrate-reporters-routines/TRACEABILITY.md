# TRACEABILITY

## Session metadata
- id: 2026-05-22j-migrate-reporters-routines
- fecha: 2026-05-22
- rama: develop
- skill: new_feature
- fase: CLASSIFY (Workflow Director) + IMPLEMENT

## Prompt issued
> "se observa que en el módulo src\util_bbdd\migrate PROCEDURE y FUNCTION no muestra el código
> aunque este tenga que ser revisado manualmente, se indico en su momento que esto debería ser
> así en .ai\sessions e implementa esta necesidad"

## Context supplied
- Sesión `2026-05-22e-migrate-routines` — implementación de `CanonicalRoutine` + emisores
- `src/util_bbdd/migrate/reporters/markdown.py` — reporter Markdown (sin sección de rutinas)
- `src/util_bbdd/migrate/reporters/text.py` — reporter texto plano (sin sección de rutinas)
- `src/util_bbdd/migrate/ir/models.py` — `CanonicalRoutine` con campos `body`, `routine_type`, `warnings`, `is_package_member`, `package_name`
- `src/util_bbdd/migrate/emitters/mariadb.py` y `oracle.py` — lógica `_emit_create_routine()` como referencia

## AI output summary
1. **Workflow Director** clasificó la solicitud como `new_feature` gap: reporters no incluían
   sección de rutinas pese a que `MigrationPlan.routines` existe desde la sesión 2026-05-22e.
2. **Feature Implementer** modificó `reporters/markdown.py`:
   - Añadida línea `**Rutinas**: N` en header del plan
   - Añadida función `_routines_section()` + `_routine_block()` con bloque ` ```sql ` para el body,
     aviso de revisión manual si hay warnings, y nota especial para `is_package_member`
   - Import `CanonicalRoutine` añadido en `TYPE_CHECKING` block
3. Modificó `reporters/text.py`:
   - Añadida línea `Rutinas: N` en header del plan
   - Añadidas funciones `_routines_section()` + `_routine_block()` con body indentado línea a línea,
     indicadores `[REQUIERE REVISIÓN MANUAL]`, `[CÓDIGO NO DISPONIBLE]` y `[PACKAGE MEMBER]`
   - Import `CanonicalRoutine` añadido en `TYPE_CHECKING` block
4. Creó `tests/unit/migrate/test_reporters.py` con 22 tests nuevos (11 markdown + 11 text).
5. Ejecutó tests: **22/22 passed** en el nuevo fichero.
6. Suite completa migrate: 1285 passed, 4 failed pre-existentes en
   `test_routines_sqlserver_extractor.py` (independientes de este cambio).
7. ruff ✅, mypy ✅ sobre los 3 ficheros afectados.

## Artefactos generados

| Artefacto                          | Ruta                                                    | Estado     |
|------------------------------------|---------------------------------------------------------|------------|
| Reporter Markdown con rutinas      | `src/util_bbdd/migrate/reporters/markdown.py`           | modificado |
| Reporter texto con rutinas         | `src/util_bbdd/migrate/reporters/text.py`               | modificado |
| Tests reporters                    | `tests/unit/migrate/test_reporters.py`                  | creado (22 tests) |
| Sesión `.ai/sessions/`             | `.ai/sessions/2026-05-22j-migrate-reporters-routines/`  | completado |

**Tests nuevos: 22**
**Suite total al cierre: 3291 passed (3269 previos + 22 nuevos), 4 fallos pre-existentes**

## Directrices para Futuras IAs

**[reporters/migrate: rutinas siempre visibles]**: Los reporters `format_plan_markdown` y
`format_plan_text` muestran el código fuente (`body`) de cada `CanonicalRoutine` cuando
`MigrationPlan.routines` no está vacío. Esto es un requisito funcional explícito: las rutinas
requieren revisión manual y el usuario DEBE ver el código para poder adaptarlo al motor destino.

**[reporters/migrate: header siempre muestra conteo de rutinas]**: La línea `**Rutinas**: N`
(markdown) y `Rutinas: N` (text) aparece siempre en el header del plan, incluso cuando N=0.
La **sección** de rutinas solo se renderiza cuando `len(plan.routines) > 0`.

**[reporters/migrate: fallos pre-existentes sqlserver extractor]**: Los 4 tests en
`test_routines_sqlserver_extractor.py` fallan porque el test parchea
`util_bbdd.migrate.extractors.sqlserver.fetch_routines_sync` pero ese símbolo no existe en el
extractor (fue migrado a `self._query()` en la sesión `2026-05-22g`). Estos fallos son
pre-existentes y no están relacionados con los reporters.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- CHANGELOG.md no actualizado (pendiente para VERSION)
- Los 4 fallos pre-existentes en `test_routines_sqlserver_extractor.py` no fueron corregidos
  (fuera del alcance de esta sesión)
