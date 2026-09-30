# TRACEABILITY

## Session metadata
- id: 2026-09-30b-migrate-d2-source-type
- fecha: 2026-09-30
- rama: develop
- skill: refactor (D2 de la deuda de `migrate/`, con cambio de API pública decidido por el usuario)
- fase: IMPLEMENT → AUDIT_CODE → VERSION (commit sin push); PLAN/AUDIT_PLAN aprobados en `2026-09-29d-migrate-audit`

## Prompt issued
- «Sube lo que hay y sigue con D2». Decisiones previas del usuario: opción B con (c) — separar el campo de los avisos
  en categoría y tipo —, corte directo con guía de migración, `target_type` fuera, 9 categorías.

## Context supplied
- PLAN/AUDIT_PLAN de D2 e inventario (`2026-09-29d-migrate-audit/d2_warning_inventory.py`);
  `.github/prompts/refactor.prompt.md`.

## AI output summary
- Clasificación de los 99 `MigrationWarning(...)` de `src/` con el AST (`d2_inventory.py`): `col.oracle_type` y tipos
  construidos → `TYPE` (+ `source_type`); `pk_col.oracle_type` → `AUTO_INCREMENT` (+ tipo de la PK);
  `SEQUENCE(x)` → `AUTO_INCREMENT`; `_default_fallback` → `DEFAULT`; tipos de rutina → `ROUTINE`; construcciones del
  reescritor antiguo y `VIEW_DEFINITION` → `VIEW`; el resto por su literal. Todas las construcciones y nombres de
  secuencia que salen del campo ya estaban en el mensaje (no se pierde información).
- `d2_other_uses.py`: separa los usos del IR (`col`, `column`, `pk_col`, `CanonicalColumn(oracle_type=)`) de los
  legítimos de Oracle, que no se tocan: `mapping.oracle_type` (tipo Oracle de destino del mapa de tipos),
  `metadata/oracle`, parámetros y funciones `resolve_oracle_type*`.
- `ir/models.py` a mano (`WarningCategory` documentado, campos y docstrings); `d2_transform.py` (AST, falla ante un
  caso sin clasificar): 152 ediciones en 30 ficheros de `src/`; comentarios y docstrings que citaban el campo;
  cabecera del informe Markdown; `WarningCategory` exportado en `util_bbdd.migrate` y `migrate.ir`.
- Tests: `d2_transform_tests.py` (AST; construcciones por literal, comparaciones por literal; lecturas de posibles
  avisos a revisión). Revisión manual: tests del reescritor antiguo pasan a buscar la construcción en `w.message`;
  FK por `category == "FOREIGN_KEY"`; helpers `_make_column(source_type=…)`. Se restauraron los tests de los mapas de
  tipos hacia Oracle, cuyo `resultado.oracle_type` es legítimo.
- Guía §4 con la tabla de categorías; CHANGELOG `[Unreleased] › Changed (incompatible)` con guía de migración.
- Validación: ruff, format, mypy (385), pytest y integración (ver commit).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Inventarios y transformaciones | `d2_inventory.py`, `d2_other_uses.py`, `d2_transform.py`, `d2_transform_tests.py` | completado |
| Modelo | `src/util_bbdd/migrate/ir/models.py`, `src/util_bbdd/migrate/__init__.py`, `src/util_bbdd/migrate/ir/__init__.py` | completado |
| Resto de `src/` | extractores, transformadores, emisores, planner, reporters, vistas | completado |
| Tests | `tests/unit/migrate/*` | completado |
| Docs | `docs/guides/ddl_migration_guide.md` §4, `CHANGELOG.md` | completado |

## Directrices para Futuras IAs
- **[migrate/ir]**: `CanonicalColumn.source_type` es el tipo en el motor origen; `MigrationWarning.category`
  (`WarningCategory`) dice qué clase de aviso es y `source_type` el tipo del origen si aplica. `oracle_type` solo sigue
  existiendo con su sentido literal: el tipo **Oracle** que devuelven los mapas de tipos hacia Oracle
  (`mapping.oracle_type`) y en `metadata/oracle`.
- **[migrate/avisos]**: al crear un aviso nuevo, elegir la categoría de `WarningCategory` y poner en el mensaje el
  objeto concreto (construcción SQL, secuencia, tipo de rutina): no hay campo para ello. `target_type` sigue mezclando
  tipo destino, nombre adaptado y etiqueta (`VIEW (reescrita)`…); separarlo sería otro corte incompatible.
- **[herramientas]**: para renombrar un campo con usos homónimos legítimos, transformar con el AST y fallar ante casos
  sin clasificar (`d2_transform.py`); en tests, dejar a revisión manual las lecturas cuyo objeto no se puede inferir.

## Veredicto final
Veredicto: GO — D2 implementado (corte directo con guía de migración), commit sin push. Pendiente de la 0.21.0: D3.
