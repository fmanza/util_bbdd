# TRACEABILITY

## Session metadata
- id: 2026-09-27-version-closure-v0.17.3
- fecha: 2026-09-27
- rama: develop
- skills: refactor (R15, R16) → version-closure
- origen: el usuario pidió R15 y R16 del plan de reutilización y cerrarlos como v0.17.3

## Versión
- **v0.17.3** (PATCH): refactor sin cambios funcionales. Sin API nueva ni cambios incompatibles.

## Contenido (sobre v0.17.2)
- `99f49b4` R15 (acotado): `DumpOrchestrator._bulk_options()`; sin `_BulkLoadOptions` ni Protocol `DumpWriter`.
  R16: `logger: ClassVar[logging.Logger]` en 6 clases, usado como `self.logger` (49 usos reescritos por AST).
- `c7c9ada` docs: CHANGELOG `[Unreleased]` e IMPLEMENT.md.
- `acf16f7` release: CHANGELOG `[0.17.3] - 2026-09-27`; `pyproject.toml` → `0.17.3`.

## Checklist (`.github/instructions/sync.instructions.md`)
- [x] `ruff check` y `ruff format --check`: limpios.
- [x] `mypy src tests/unit/test_protocol_conformance.py`: sin errores (356 ficheros).
- [x] `pytest` sin URLs de servidor: **5095 passed / 199 skipped**.
- [x] `pytest tests/integration` con las URLs del banco (5 servidores): **338 passed** (sobre `99f49b4`; la release solo
  cambia CHANGELOG y pyproject).
- [x] `python -m build`: `util_bbdd-0.17.3`.
- [x] `pyproject.toml` → `0.17.3`; `CHANGELOG.md` `[0.17.3]` con *Changed*; `[Unreleased]` vacío y único.
- [x] `mkdocs build --strict`: sin avisos. Diagrama de capas sin cambios (sin imports nuevos).

## Impacto en API pública
- Ninguno. Las 6 clases ganan el atributo de clase `logger` (mismo logger que antes a nivel de módulo).

## Commits y push
- `acf16f7` `release: v0.17.3 - …` y tag anotado `v0.17.3`; después, este `docs(ai)`.
- Push de `develop` y del tag `v0.17.3` a `origin`; `main` no se toca.

## Rollback
- Quitar el tag remoto si nadie lo ha consumido: `git push origin :refs/tags/v0.17.3`.
- Revertir el refactor: `git revert 99f49b4` (sin cambios de datos ni de API).

## Estado del plan de reutilización (`2026-09-26ze-code-reusability-bulk-dump`)
- Completo: R1–R12, R14, R15 (acotado), R16. R13 descartado. Hotfixes derivados: `9ef505e` (v0.17.1), `bb91612` (v0.17.2).
- Fuera de alcance (cambios de comportamiento, `/new-feature` si hacen falta): regla única de capacidad del pool,
  `rows_committed` con DELETE, jerarquía de `AuditError` bajo `_core/exceptions.py`, destino de `BulkInserter`.

## Directrices para Futuras IAs
- **[logging]**: en este repositorio el logger de clase se declara como `logger: ClassVar[logging.Logger] =
  logging.getLogger(__name__)` cuando los tests crean instancias con `__new__` (`DumpOrchestrator`: 29 tests); asignarlo
  en `__init__` rompería esos tests.
- **[dump]**: las opciones de las `BulkCrud`/`ParallelBulkLoader` del volcado salen de `DumpOrchestrator._bulk_options()`;
  una opción nueva de `BulkCrud` que el volcado deba fijar se añade ahí.

## Veredicto final
Veredicto: CLOSED
