# TRACEABILITY

## Session metadata
- id: 2026-10-10-exceptions-module-name
- fecha: 2026-10-10
- rama: develop (base v0.43.0, `f8ba6edc`)
- skill: refactor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (v0.44.0, local)

## Prompt issued
«Qué recomiendas para decidir si las excepciones deben mostrar util_bbdd.exceptions como módulo en vez de _core» →
recomendación (hacerlo antes de 1.0.0, en `_core/exceptions.py`) → «Si» (prepararlo como 0.44.0).

## Context supplied
- `../2026-10-10-api-1-0/02_AUDIT_CODE.md` (pendiente «1.0.0»), `src/util_bbdd/_core/exceptions.py`,
  `src/util_bbdd/exceptions.py`, `tests/unit/bulk/test_audit_exception_hierarchy.py`

## AI output summary
- Simulación previa: con `__module__` público, los pickles con la ruta `_core` se cargan; trazas con la ruta pública;
  `src/` sin `pickle` ni `multiprocessing`; ningún test comprobaba el `__module__` de las excepciones.
- Corrección de lo dicho al cierre de v0.43.0: el riesgo con pickle no es para los pickles antiguos (se cargan), sino
  para leer pickles nuevos con ≤ 0.42.
- Hipótesis descartada al verificarla: pickle **sí** conserva `operation`/`db_type`/`details` (restaura `__dict__`).
- `016ad5fc` — bucle final en `_core/exceptions.py` (patrón `set_module`); `test_exceptions_public_module.py` (85 casos)
  con un pickle generado con el código del tag `v0.43.0` (`git archive` en el scratchpad); una línea de
  `docs/architecture.md`. Los bytes del pickle se escribieron primero a mano y no coincidían con los reales: se
  sustituyeron por los generados.
- AUDIT_CODE: sin regresiones; las 40 anclas del autodoc siguen en `util_bbdd.exceptions.*`; ruff, ruff format y mypy
  (332 ficheros) limpios; `zensical build --strict` sin incidencias; `python -m build` → `util_bbdd-0.44.0`.
- Puerta: pytest sin banco 5679 passed, 523 skipped; con banco + `JAVA_HOME` 6195 passed, 7 skipped.
- VERSION: 0.44.0 en `pyproject.toml`, CHANGELOG (`Changed`), README, `docs/index.md`, `docs/roadmap.md`, pie de
  `docs/architecture.md` (mismo commit que `pyproject.toml`), `.ai/CURRENT_STATE.md`, `SESSIONS_DIGEST.md`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-10-exceptions-module-name/01_PLAN.md` | aprobado |
| Código | `src/util_bbdd/_core/exceptions.py` | completado |
| Tests | `tests/unit/test_exceptions_public_module.py` | completado |
| Logs | `build/logs/exc_mod_*` | emitido |

## Directrices para Futuras IAs
- **[exceptions]**: las clases se definen en `_core/exceptions.py` y su `__module__` es `util_bbdd.exceptions` (bucle al
  final del fichero). Una excepción nueva debe heredar de `DatabaseException` y definirse en ese fichero; el bucle y
  `test_exceptions_public_module` la cubren solos. Añádela también a `__all__` de `_core/exceptions.py` y de
  `exceptions.py` (`test_public_exceptions_module_is_the_full_hierarchy` lo exige).
- **[pickle]**: `PICKLE_FROM_0_43` en el test son bytes reales del tag `v0.43.0`; no los regeneres con el código actual
  (perderían la ruta `_core` que prueban).
- **[tests]**: para generar artefactos de una versión anterior, `git archive <tag> src/util_bbdd | tar -x` en el
  scratchpad y `python -I` con ese `src` al principio de `sys.path`.

## Veredicto final
Veredicto: CLOSED (v0.44.0 en local)
Pendientes al cierre:
- Push de `develop` y tag `v0.44.0`: solo con autorización explícita del usuario.
