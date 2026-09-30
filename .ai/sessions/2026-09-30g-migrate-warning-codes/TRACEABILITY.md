# TRACEABILITY

## Session metadata
- id: 2026-09-30g-migrate-warning-codes
- fecha: 2026-09-30
- rama: develop
- skill: new_feature (deuda E1 de la 0.21.0)
- fase: PLAN + AUDIT_PLAN («Plan y Audit de las deudas», opción C + A) → IMPLEMENT → AUDIT_CODE → VERSION (commit sin
  push)

## Prompt issued
- «Plan y Audit de las deudas» → «IMPLEMENT» → «Adelante» (orden E3 → E2 → E1).

## Context supplied
- `migrate/ir/models.py` (`MigrationWarning`, `WarningCategory`), los 24 avisos con etiqueta literal en `target_type`
  (inventario AST) y los 5 de `views/transpiler._warning`.

## AI output summary
- `WarningCode` (`Literal` de 20 códigos, documentado) y `MigrationWarning.code: WarningCode | None = None` como
  **último** campo: compatible con las construcciones posicionales y con palabras clave existentes. Exportado en
  `util_bbdd.migrate` y `util_bbdd.migrate.ir`.
- `code` en los 24 avisos con etiqueta (script AST que inserta `code="…"` tras `target_type=`) y en los 5 de
  `transpiler._warning` (parámetro `code` obligatorio). Los avisos de tipos (`CLOB`, `SERIAL`, `IDENTITY(1,1)`…) e
  identificadores quedan con `code=None`: su `target_type` ya es el tipo o el nombre destino.
- `transpiler` reconoce la cabecera de columnas por `w.code == "VIEW_HEADER_COLUMNS"` en lugar de la etiqueta.
- `target_type` sin cambios; su docstring dice qué guarda en cada caso y que para filtrar se usa `category` + `code`.
- Test guardián `test_warning_codes.py`: todo `MigrationWarning`/`_warning` con etiqueta (no un tipo SQL) lleva `code`;
  todos los códigos usados existen y todos los de `WarningCode` se usan; `code` es el último campo y vale `None` por
  defecto; los avisos del transpilador llevan código.
- Docs: guía de migración DDL (tabla de códigos y ejemplo), `docs/api/migrate_views.md` (columna `code`), CHANGELOG.

## Verificación
- ruff, mypy (386 ficheros): sin errores. `pytest`: 5717 passed, 227 skipped. `tests/integration`: 366 passed.

## AUDIT_CODE
- API: aditiva (nuevo campo con valor por defecto al final, nuevo alias exportado). La igualdad de `MigrationWarning`
  (dataclass congelada) incluye `code`: dos avisos iguales salvo el código ya no son iguales, pero todos los sitios que
  construyen un aviso concreto le dan siempre el mismo código, así que la deduplicación (`if w not in ...`) no cambia.
- Un test antiguo construía el aviso de cabecera con la categoría inexistente `"VIEW_DEFINITION"` (previa a D2; los
  tests no pasan por mypy); corregido a `"VIEW"` + `code`.
- Veredicto: APROBADO.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Modelo | `src/util_bbdd/migrate/ir/models.py`, `migrate/__init__.py`, `migrate/ir/__init__.py` | completado |
| Códigos | 18 ficheros de `migrate/` (extractors, transformers, emitters, planner, views/transpiler) | completado |
| Tests | `tests/unit/migrate/test_warning_codes.py`, `test_view_transpiler.py` | completado |
| Docs | `docs/guides/ddl_migration_guide.md`, `docs/api/migrate_views.md`, `CHANGELOG.md` | completado |

## Directrices para Futuras IAs
- **[migrate/avisos]**: un aviso nuevo cuyo `target_type` sea una etiqueta (no un tipo SQL ni un nombre) necesita un
  `code` nuevo en `WarningCode` (con su línea en el docstring y en la tabla de la guía); `test_warning_codes.py` falla
  si falta o si un código queda sin uso.
- **[migrate/avisos]**: filtrar avisos en código por `category` + `code`, nunca por el texto de `target_type`.
- **[herramientas]**: para editar muchas llamadas iguales, un script que localiza la llamada con `ast` e inserta una
  línea tras el argumento (de abajo arriba) es más seguro que regex sobre el texto; comprobar el total contra el
  inventario.

## Veredicto final
Veredicto: CLOSED — E1 implementado y verificado. Deuda E1–E3 cerrada; la 0.22.0 queda lista para `/version-closure`.
