# TRACEABILITY

## Session metadata
- id: 2026-09-26zf-version-closure-v0.17.1
- fecha: 2026-09-26
- rama: develop
- skill: version-closure
- origen: el usuario aceptó publicar como v0.17.1 el fix de `DumpConfig` y el refactor de reutilización

## Versión
- **v0.17.1** (PATCH): un fix de comportamiento (`DumpConfig` rechaza al construirse `chunk_size` o
  `commit_every_n_chunks` inválidos, que antes vaciaban el destino) y un refactor sin cambios funcionales. Sin API nueva
  ni cambios incompatibles.

## Contenido (sobre v0.17.0)
- Sesión `2026-09-26ze-code-reusability-bulk-dump`: `62908b1`, `e513db1`, `34aee9f`, `825f025`, `9ef505e`, `f5ca1b6`,
  `acbb342`.
- `3056c69` docs(dump): correspondencia entre las 5 fases del orquestador y las 7 de la documentación. Incluye
  también, sin mencionarlo en el mensaje, el renombrado de la carpeta de sesión `2026-09-26zd-code-reusability-…` →
  `2026-09-26ze-…` (estaba en el índice de git por un `git mv` previo; no se reescribió para no mover el tag).
- `5113380` release: CHANGELOG `[0.17.1] - 2026-09-26`; cabeceras `[Unreleased]` históricas corregidas (`[0.4.0] -
  2026-03-10` y «Hoja de ruta histórica»); `pyproject.toml` → `0.17.1`.

## Checklist (`.github/instructions/sync.instructions.md`)
- [x] `ruff check` y `ruff format --check`: limpios.
- [x] `mypy src tests/unit/test_protocol_conformance.py`: sin errores (355 ficheros).
- [x] `pytest` sin URLs de servidor: **5089 passed / 199 skipped**.
- [x] `pytest tests/integration` con las URLs del banco (5 servidores): **338 passed** (tras R5; el cambio posterior es
  solo un docstring).
- [x] `python -m build`: `util_bbdd-0.17.1` (wheel con los 13 módulos nuevos).
- [x] `pyproject.toml` → `0.17.1`; `CHANGELOG.md` `[0.17.1]` con *Changed* y *Fixed*; `[Unreleased]` vacío y único.
- [x] `mkdocs build --strict`: sin avisos. No hay `docs/CHANGELOG.md`.

## Impacto en API pública
- Ninguna firma cambia. `DumpConfig(...)` con `chunk_size` < 1 o no entero, o `commit_every_n_chunks` < 1, lanza
  `ValueError` al construirse (antes fallaba en `run()` después de vaciar el destino). Sin deprecaciones ni migraciones.

## Commits y push
- `5113380` `release: v0.17.1 - …` y tag anotado `v0.17.1`; después, este `docs(ai)`.
- Push de `develop` y del tag `v0.17.1` a `origin`; `main` no se toca.

## Rollback
- Quitar el tag remoto si nadie lo ha consumido: `git push origin :refs/tags/v0.17.1`.
- Revertir el fix por separado: `git revert 9ef505e`. El refactor: `git revert f5ca1b6 62908b1` (sin cambios de datos
  ni de API; los tests de `batch`/`orchestrator` siguen importando por las fachadas).

## Directrices para Futuras IAs
- **[changelog]**: `CHANGELOG.md` tenía dos `## [Unreleased]` antiguos (líneas ~2374 y ~2800); una edición que busque
  `## [Unreleased]` sin más contexto falla o toca el bloque equivocado. Ya corregidos; queda uno solo, arriba.
- **[sesiones]**: otra sesión puede estar cerrando versiones en paralelo en el mismo repositorio. Antes de nombrar una
  carpeta de sesión, mira el último prefijo usado en `.ai/sessions/`; antes de commit, `git log origin/develop..HEAD`.

## Veredicto final
Veredicto: CLOSED
