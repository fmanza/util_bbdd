# TRACEABILITY

## Session metadata
- id: 2026-10-11-hotfix-doc-auto-filename
- fecha: 2026-10-11
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
`/hotfix` abierto desde la sesión `2026-10-10-docs-review-nivel-2` (tanda 3) por decisión del usuario: al ejecutar el
fragmento mínimo de `docs/examples/database_documentation_generation.md` (SQLite `:memory:` sin `fichero_salida`),
`DatabaseDocumentation.generate()` falla en Windows con `OSError` [WinError 123].

## Context supplied
- `.github/prompts/hotfix.prompt.md`, `.github/agents/hotfix-responder.agent.md`
- `src/util_bbdd/doc/infrastructure/runtime/output_runtime.py`, `tests/unit/test_documentation_runtime.py`

## AI output summary
- RCA: `generate_auto_output_filename` (`output_runtime.py`) construye `<identificador>-<fecha>` y solo sustituía
  espacio, `/` y `\`. En SQLite el identificador es el nombre del fichero (`normalize_sqlite_identifier`), y `:memory:`
  pasa tal cual: `ensure_execution_root` hace `mkdir` de `…\:memory:-<fecha>` → WinError 123. En Oracle el
  identificador es el `user`, así que el ejemplo de un DSN con `:` no aplica; sí cualquier `database` con `<>:"|?*`.
- Test primero: 4 casos (3 parametrizados + `DatabaseDocumentation` real sobre SQLite `:memory:`) fallaban antes
  (`build/logs/hotfix_docname_before.txt`) y pasan después (`hotfix_docname_after.txt`).
- Fix: `_UNSAFE_NAME_CHARS = [ /\\<>:"|?*\x00-\x1f]` sustituido por `_`. Sin otros cambios.
- Puerta: ruff, ruff format, mypy (334 ficheros), pytest completo sin URLs del banco (5734 passed, 531 skipped;
  `hotfix_docname_pytest_full.txt`), `python -m build`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fix | `src/util_bbdd/doc/infrastructure/runtime/output_runtime.py` | completado |
| Tests | `tests/unit/test_documentation_runtime.py` | completado |
| CHANGELOG | `CHANGELOG.md` `[Unreleased]` › Fixed | completado |

## Directrices para Futuras IAs
- **[doc]**: el nombre automático de salida (`DocumentationOutputRuntime.generate_auto_output_filename`) se sanea con
  `_UNSAFE_NAME_CHARS`; cualquier otro nombre de carpeta/fichero derivado de datos del catálogo debe pasar por la
  misma regla para ser portable a Windows.
- **[doc]**: un fallo al crear la carpeta de salida en `generate()` llega como `OSError` crudo, no como
  `DocumentationRenderError` (la traducción solo cubre los renderers). Pendiente fuera del hotfix.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Envolver los `OSError` de preparación de la salida en `DocumentationRenderError` (cambio de contrato; decidir).
- Rollback: `git revert <commit>` (un commit; sin migraciones).
