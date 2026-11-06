# AUDIT_CODE — Grupo E (`changes.md` / `changes.json`) y E0 (`fix(comparar)`)

Revisión contra `PLAN_GRUPO_E.md`. Decisiones del usuario:

- E-A: renderer propio;
- E-B: corregir el escape de `comparar` antes del grupo (E0, commit `98248a46`);
- E-C: schemas distintos con aviso.

## Puertas

| Comando | Resultado |
|---|---|
| `ruff format` / `ruff check src tests` | Limpio |
| `mypy src tests/unit/test_protocol_conformance.py` | Sin errores (371 ficheros) |
| `pytest` (shell sin variables del banco) | **7061 passed, 618 skipped** (`build/logs/grupo_e_pytest.txt`) |
| `scripts/gen_arquitectura_capas.py` | Arista nueva `doc → comparar` (capa 7 → 6) añadida a `DRAWN` y dibujada (`M{c[3]} 83 H{c[2] + NODE_W}`); figura regenerada. El pie de figura de `docs/architecture.md` (versión, fecha y ficheros) se actualiza en el cierre (grupo F) |
| `zensical build --strict` con `changes.md` | Sin incidencias (`test_zensical_strict_build_with_changes`, `integration`) |

## E0 · `fix(comparar)`

- `_core/markdown.py` (`code_span`, `escape_html`), común a `comparar` y `doc`. `_trace.py` usa ya el de `_core`
  (sin duplicado).
- `MarkdownDiffReporter`: 12 *code spans* pasan por `_cell` (dentro de tabla, con `|` escapado) o por `_code`
  (títulos). Una celda vacía queda vacía, en lugar de dos backticks literales.
- `escape_markdown_table_cell` escapa también `&`, `<` y `>`.
- Tests `tests/comparar/test_markdown_reporter_escape.py`. Los 391 tests de `comparar` siguen en verde.
- Fuera de alcance: los bloques `<details>` del informe siguen necesitando `md_in_html` para verse bien en Zensical.
  Es un tema de presentación, no de seguridad.

## Hallazgos del grupo E

| # | Tipo | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|
| E-1 | Límite del modelo | `_changes.py` `_table_diff` | `TableDiff` no recoge restricciones únicas, identidad ni columnas calculadas. Si una tabla cambia solo en eso (hash distinto), no aparece | Aceptado; documentar en la guía (F) |
| E-2 | Límite del modelo | `_changes.py` `_fk_diffs` | Un cambio solo de `ON DELETE`/`ON UPDATE` aparece como FK `modified` con las mismas columnas: `ForeignKeyDiff` no tiene campos de acciones | Aceptado; documentar |
| E-3 | Límite del modelo | `RoutineDiff.routine_type` | `PACKAGE` y otros tipos no caben en el modelo: van a `changes.md` (sección propia) y no a `changes.json` | Conforme al plan (ET2) |
| E-4 | Determinismo | `PreviousCatalog.label` | La etiqueta usa base de datos, schema y `generated_at` del manifiesto anterior, sin rutas: dos generaciones contra la misma anterior dan `changes.*` idénticos (test) | Conforme |
| E-5 | Seguridad | `changes_page` | Nombres del catálogo anterior escapados (`md_text`, `code_span`); los eliminados no se enlazan (test con `"vieja <b>"`) | Conforme |

## Veredicto

**APROBADO.**
