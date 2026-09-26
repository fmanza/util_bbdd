# TRACEABILITY

## Session metadata
- id: 2026-09-26zg-version-closure-v0.17.2
- fecha: 2026-09-26
- rama: develop
- skills: refactor (R11, R12, R14) → hotfix (rows_committed) → version-closure
- origen: el usuario pidió continuar el plan de reutilización tras v0.17.1 y cerrar como v0.17.2 con el hotfix

## Versión
- **v0.17.2** (PATCH): un fix de comportamiento en `BulkCrud.rows_committed` y refactor sin cambios funcionales. Sin API
  nueva ni cambios incompatibles.

## Contenido (sobre v0.17.1)
- `85373af` R11: 10 consultas de catálogo de `bulk/` y `dump/` a `metadata/<motor>/` (mismo texto, comprobado por AST);
  import `bulk → metadata` dibujado en el diagrama de capas. `3f95f02` CHANGELOG.
- `c121d72` R12: DDL de integridad por motor (`bulk/_support/dialect.py`). R13 descartado (ver IMPLEMENT.md).
- `ca48fb4`, `b6b0269` tests de caracterización de la cadencia de commit (válidos contra el código anterior).
- `ce00675` R14: `SessionScope` + `CommitCadence` (`bulk/_execution/session.py`). `0136904` docs.
- `bb91612` fix(bulk): `rows_committed` descarta las filas pendientes de una `bulk_session` fallida.
- `ce1314b` release: CHANGELOG `[0.17.2] - 2026-09-26`; `pyproject.toml` → `0.17.2`.

## Checklist (`.github/instructions/sync.instructions.md`)
- [x] `ruff check` y `ruff format --check`: limpios.
- [x] `mypy src tests/unit/test_protocol_conformance.py`: sin errores (356 ficheros).
- [x] `pytest` sin URLs de servidor: **5095 passed / 199 skipped**.
- [x] `pytest tests/integration` con las URLs del banco (5 servidores): **338 passed** (tras el fix).
- [x] `python -m build`: `util_bbdd-0.17.2` (wheel con `bulk/_execution/session.py`).
- [x] `pyproject.toml` → `0.17.2`; `CHANGELOG.md` `[0.17.2]` con *Changed* y *Fixed*; `[Unreleased]` vacío y único.
- [x] `mkdocs build --strict`: sin avisos; pie de figura del diagrama de capas: 356 ficheros.

## Impacto en API pública
- Ninguna firma cambia. `BulkCrud.rows_committed` (y `PartitionResult.rows` en fallos) ya no incluye filas de una
  sesión anterior que falló. Los ejecutores internos (`bulk/_execution/`) cambian sus atributos privados por
  `session`/`cadence`; no son API pública.

## Commits y push
- `ce1314b` `release: v0.17.2 - …` y tag anotado `v0.17.2`; después, este `docs(ai)`.
- Push de `develop` y del tag `v0.17.2` a `origin`; `main` no se toca.

## Rollback
- Quitar el tag remoto si nadie lo ha consumido: `git push origin :refs/tags/v0.17.2`.
- Revertir el fix por separado: `git revert bb91612`. Refactors: `git revert ce00675 c121d72 85373af` (en ese orden);
  los tests de caracterización (`ca48fb4`, `b6b0269`) pueden quedarse, pasan con y sin R14.

## Directrices para Futuras IAs
- **[tests/caracterización]**: un test de caracterización solo vale si pasa contra el código **anterior** al cambio
  (`git stash` de `src/`) y si un sabotaje de cada pieza lo hace fallar. En R14 dos sabotajes pasaban al principio: el
  commit final de sesión no emite evento `commit` si un commit periódico acaba de confirmar todo, así que una sola
  inserción no distingue si hubo commit periódico.
- **[bulk]**: la cadencia vive en `BatchStatementExecutor.cadence` (arrastra el contador en la sesión y cuenta filas); el
  DELETE crea una `CommitCadence` por llamada y no cuenta filas. La conexión de la sesión es `BulkCrud._session`
  (`SessionScope`), compartida por los dos ejecutores.
- **[shell]**: en este entorno, un heredoc de bash con ciertos scripts de Python (comillas triples, comillas invertidas)
  falla con `unexpected EOF`; escribir el script a un fichero del scratchpad y ejecutarlo.

## Veredicto final
Veredicto: CLOSED
