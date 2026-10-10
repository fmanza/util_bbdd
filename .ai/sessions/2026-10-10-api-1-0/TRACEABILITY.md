# TRACEABILITY

## Session metadata
- id: 2026-10-10-api-1-0
- fecha: 2026-10-10
- rama: develop (base v0.42.1, `676ee482`)
- skill: refactor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (v0.43.0, local)

## Prompt issued
`/refactor` — API pública 1.0, fase 0.43.0 (ver `00_REQUEST.md`).

## Context supplied
- `.github/prompts/refactor.prompt.md`, `.github/agents/plan-architect.agent.md`, `.github/instructions/sync.instructions.md`
- `../2026-10-10-plan-pendientes-global/Q6_PLAN_API_1_0.md`, `api_inventory.tsv`
- `src/util_bbdd/__init__.py`, `_core/exceptions.py`, `__init__.py` de `analysis`, `audit`, `bulk`, `comparar`,
  `connection`, `doc`, `dump`, `factory`, `metadata`, `migrate`; `managers/sync_mgr.py`, `async_mgr.py`,
  `_manager_session.py`; `scripts/gen_arquitectura_capas.py`; `pytest.ini`; `pyproject.toml`

## AI output summary
- PLAN + AUDIT_PLAN (`01_PLAN.md`): GO_CONDICIONAL con D1–D5; el usuario aprobó D1–D5 («si»).
- Línea base `import util_bbdd`: 1,08–1,10 s en caliente; 80 % en `util_bbdd.comparar` (pandas/openpyxl/docx).
- `e9690f45` — `util_bbdd.exceptions` (40 excepciones); `QueryParameterError` añadida a `_core.exceptions.__all__`;
  `exceptions` excluido del diagrama de capas (fachada de reexportación).
- `4a929ec9` — raíz con 13 símbolos, `_LAZY` (10), `_DEPRECATED` (46), `_SUBMODULES`, `__dir__`; `async_utils.__all__`;
  31 ficheros de tests y 6 de docs con imports nuevos; guía `docs/guides/api_1_0_migration.md`; autodoc de
  `util_bbdd.exceptions`; SHARED_INSTRUCTIONS, `.ai/architecture.md`, README; pie del diagrama.
- `1f8bd47b` — `SyncDatabaseManager.init()`/`release_connection()`, `close_connection()` deprecado; estáticos de tipo en
  el async; `test_manager_symmetry.py`; test de integración TLS con `release_connection()`.
- Primera puerta: 1 fallo esperado (`test_docs_version`: pie a 0.43.0 con `pyproject` a 0.42.1) y 5 avisos de alias en
  `test_audit_exception_hierarchy.py` (`getattr(util_bbdd, name)`, no visto por grep) → corregido antes del commit 2.
- `import util_bbdd` después: 0,305–0,321 s.
- AUDIT_CODE (`02_AUDIT_CODE.md`): GO.
- VERSION: 0.43.0 en `pyproject.toml`, CHANGELOG (Added/Changed/Deprecated/Fixed), README, `docs/index.md`,
  `docs/roadmap.md`, `docs/architecture.md`, `.ai/CURRENT_STATE.md`, `SESSIONS_DIGEST.md`.
- Puerta final: ruff y ruff format limpios; mypy sin errores (332 ficheros); pytest sin banco 5594 passed, 523 skipped;
  con banco + `JAVA_HOME` 6110 passed, 7 skipped; 0 avisos de alias de `util_bbdd` en ambas; `zensical build --strict`
  sin incidencias; `python -m build` → `util_bbdd-0.43.0`; `gen_arquitectura_capas.py` en verde.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-10-10-api-1-0/00_REQUEST.md` | emitido |
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-10-api-1-0/01_PLAN.md` | aprobado |
| AUDIT_CODE | `.ai/sessions/2026-10-10-api-1-0/02_AUDIT_CODE.md` | GO |
| Módulo público | `src/util_bbdd/exceptions.py` | completado |
| Raíz | `src/util_bbdd/__init__.py` | completado |
| Guía | `docs/guides/api_1_0_migration.md` | completado |
| Logs | `build/logs/api10_*` (importtime, capas, pytest ×2 ×2, zensical, build, lint) | emitido |

## Directrices para Futuras IAs
- **[api]**: la raíz `util_bbdd` exporta 13 símbolos; `_LAZY`, `_DEPRECATED` y `_SUBMODULES` de `src/util_bbdd/__init__.py`
  son la única tabla de la superficie. Un símbolo nuevo de primer nivel se añade a `__all__` + `_LAZY` + el bloque
  `TYPE_CHECKING`, y a `ROOT_API` de `tests/unit/test_top_level_exports.py`.
- **[api]**: no importes desde la raíz en `src/`, tests ni docs nada que no esté en `__all__`; los alias avisan y se
  retiran en 1.0.0. Las excepciones se importan desde `util_bbdd.exceptions` (en `src/`, desde `_core.exceptions`).
- **[import]**: `import util_bbdd` no debe cargar pandas/openpyxl/docx/jinja2 (lo fija
  `test_import_does_not_load_heavy_dependencies`); un import directo nuevo en la raíz puede romperlo.
- **[tests]**: el grep de `from util_bbdd import` no ve `getattr(util_bbdd, name)`; la suite completa con el resumen de
  avisos (`grep obsoleto` en el log) sí.
- **[capas]**: `connection` es nivel 4 y `factory` nivel 5: `PoolFactory` vive en `util_bbdd.factory`, no en
  `connection`. `exceptions.py` está en `EXCLUDED` del script de capas (fachada como `__init__.py`).
- **[versión]**: `test_docs_version` compara el pie de `docs/architecture.md` con `pyproject.toml`: cambia ambos en el
  mismo commit (aquí el pie se adelantó un commit y la puerta intermedia falló por eso).
- **[1.0.0]**: retirar `_DEPRECATED`, `SyncDatabaseManager.close_connection()` y sus tests; valorar
  `__module__ = "util_bbdd.exceptions"` en las excepciones (afecta a `pickle`).

## Veredicto final
Veredicto: CLOSED (v0.43.0 en local)
Pendientes al cierre:
- Push de `develop` y tag `v0.43.0`: solo con autorización explícita del usuario.
- 1.0.0: retirar los alias tras al menos una versión con avisos.
