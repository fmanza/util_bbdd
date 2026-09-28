# 🎯 Standards & Quality Gate - util_bbdd

## Code Style

- **Formatter:** `ruff format` (line length: 120, quote-style: double)
- **Linter:** `ruff check` (extend-select: E, W, F, I, B, C4, UP; ignore: E501)
- **Type Checker:** `mypy` (check_untyped_defs=true; no_implicit_optional=true)
- **Import Sort:** `ruff` isort (known-first-party: util_bbdd; combine-as-imports: true)
- **Python:** `>=3.12` (target), tested on 3.12, 3.13, 3.14

## Type Safety

- **All public APIs** must have full type hints
- **Type aliases** in `_core/types.py` (RowOrNone, Rows, QueryParams, etc.)
- **Protocols** in `_core/contracts.py` for interface definition
- **No `Any` without rationale** (document with `# type: ignore` reason)
- **`py.typed`** marker presente → librería tipada conforme a PEP 561

## Testing Standards

- **Framework:** pytest ≥9.0
- **Async Testing:** pytest-asyncio
- **Coverage:** ≥90% on public APIs (actual: ~94%)
- **No external services:** All tests must be isolated (SQLite in-memory, fixtures, mocks)
- **Fixtures:** In `tests/conftest.py` (shared state)
- **Naming:** `test_<module>_<scenario>.py`
- **Total tests:** ver `.ai/CURRENT_STATE.md` (se actualiza en cada cierre de versión)

## Documentation

- **Docstrings:** Google-style (module, class, function)
- **Zensical:** generador por defecto (CI; `zensical build` / `zensical serve`)
- **MkDocs Material:** generador recíprocamente compatible (mismo `mkdocs.yml`)
- **CHANGELOG.md:** Semver ([major.minor.patch]) con Conventional Commits
- **Arquitectura:** `.ai/architecture.md` actualizado con cambios estructurales
- **Build limpio:** `zensical build --strict` (o `mkdocs build --strict`) sin errores ni warnings antes de publicar

## Commits & Versioning

- **Commits:** `<type>(<scope>): <message>` (conventional commits)
- **Types:** los de `.github/SHARED_INSTRUCTIONS.md` § «Formato de commits» (`feat`, `fix`, `hotfix`, `security`, `perf`, `refactor`, `test`, `docs`, `chore`, `release`)
- **Scopes:** `managers`, `query`, `metadata`, `connection`, `async`, `bulk`, `audit`, `migrate`, `dump`, `comparar`, `analysis`, `doc`
- **Tags:** `v0.x.y` (semver)
- **No direct main:** Merge via PR (develop → main)

## API Stability

- **Breaking Changes:** Permitidos cuando exista PLAN + AUDIT + GO explícito y guía de migración actualizada
- **Deprecation**: Issue warning + 1 minor release before removal
- **Wrappers legacy:** Mantener solo entry points cuyo coste de soporte siga siendo razonable

## Security

- **SQL Injection:** Always use parameterized queries (SQLAlchemy Core)
- **Credentials:** Never log passwords; use connection pools; `masked_pass` never enviado al servidor
- **Audit Trail:** All mutations logged with user/timestamp
- **Thread-safety:** AuditManager usa lock por ruta en modo paralelo

## Quality Gate

- Comandos: `.github/SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo» (todos en verde antes de cerrar IMPLEMENT).
- Estado medido (tests, versión): `.ai/CURRENT_STATE.md`.
- Complejidad cognitiva: reporters ≤4; emitters ≤15.
