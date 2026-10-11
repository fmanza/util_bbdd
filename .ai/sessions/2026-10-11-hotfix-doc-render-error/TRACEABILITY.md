# TRACEABILITY

## Session metadata
- id: 2026-10-11-hotfix-doc-render-error
- fecha: 2026-10-11
- rama: develop
- skill: hotfix
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Decisión D3.2 del usuario (sesión `2026-10-10-docs-review-nivel-2`, pendiente D3): «Envolverlo en 1.1.1» — el
`OSError` crudo de `DatabaseDocumentation.generate()` al preparar la carpeta de salida.

## Context supplied
- `.ai/sessions/2026-10-10-docs-review-nivel-2/02_DOC_REVIEW.md` § Fuera de alcance
- `src/util_bbdd/doc/application/use_cases/documentation_orchestrator.py`, `src/util_bbdd/doc/database_documentation.py`

## AI output summary
- RCA: `DocumentationOrchestrator.generate_documents()` traduce a `DocumentationRenderError` solo las excepciones de
  los renderers (`_dispatch_plan`). Las carpetas de salida se crean antes, en `DocumentationOutputPlanner.build_plans()`
  (`resolve_output_path` → `get_format_output_dir` → `mkdir`), fuera de esa frontera: su `OSError` escapaba crudo,
  contra el contrato documentado de `generate()`.
- Test primero: `directorio_salida` que es un fichero → `FileExistsError` (`build/logs/hotfix_docoserror_before.txt`);
  después, `DocumentationRenderError` con el `OSError` en `__cause__` (`hotfix_docoserror_after.txt`).
- Fix: `try/except OSError` alrededor de `build_plans()` en `generate_documents()`. Docstring de `generate()`, fila de
  errores de `docs/api/database_documentation.md` y CHANGELOG `[Unreleased]`.
- AUDIT_CODE: solo cambia la clase de la excepción en ese caso (antes `OSError`, ahora `DocumentationRenderError`,
  que no hereda de `OSError`): quien capturase `OSError` debe capturar la nueva (anotado en el CHANGELOG). Los
  `DatabaseException` del catálogo no pasan por ahí (se leen antes, en `bootstrap.build`).
- Puerta: ruff, ruff format, mypy, pytest completo sin URLs del banco (`hotfix_docoserror_pytest_full.txt`); la
  puerta con banco y `build` se pasan en el cierre de 1.1.1.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Fix | `src/util_bbdd/doc/application/use_cases/documentation_orchestrator.py` | completado |
| Test | `tests/unit/test_documentation_runtime.py` | completado |
| Docs | `src/util_bbdd/doc/database_documentation.py` (docstring), `docs/api/database_documentation.md` | completado |

## Directrices para Futuras IAs
- **[doc]**: la frontera de traducción a `DocumentationRenderError` cubre ya la preparación de la salida
  (`build_plans`) y cada renderer (`_dispatch_plan`); los errores del catálogo llegan con su propia clase.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Rollback: `git revert <commit>` (un commit; sin migraciones).
