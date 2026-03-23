# 🎯 Standards & Quality Gate - util_bbdd

## Code Style

- **Formatter:** `black` (line length: 88)
- **Linter:** `ruff` (default config)
- **Type Checker:** `mypy` (strict mode)
- **Import Sort:** `isort` (profile: black)
- **Python:** 3.11+ (target), tested on 3.13, 3.14

## Type Safety

- **All public APIs** must have full type hints
- **Type aliases** in `_core/types.py` (RowOrNone, Rows, QueryParams, etc.)
- **Protocols** in `_core/contracts.py` for interface definition
- **No `Any` without rationale** (document with `# type: ignore` reason)

## Testing Standards

- **Framework:** pytest ≥9.0
- **Async Testing:** pytest-asyncio
- **Coverage:** ≥90% on public APIs (✅ current: 94%)
- **No external services:** All tests must be isolated (use fixtures, mocks)
- **Fixtures:** In `tests/conftest.py` (shared state)
- **Naming:** `test_<function>_<scenario>.py`

## Documentation

- **Docstrings:** Google-style (module, class, function)
- **README.md:** Ejemplos de uso por motor
- **CHANGELOG.md:** Semver ([major.minor.patch])
- **Architecture:** `.ai/architecture.md` actualizado con cambios estructurales

## Commits & Versioning

- **Commits:** `<type>(<scope>): <message>` (conventional commits)
- **Types:** `feat`, `fix`, `refactor`, `docs`, `test`, `perf`, `chore`
- **Scopes:** `managers`, `query`, `metadata`, `connection`, `async`, `bulk`, `audit`
- **Tags:** `v0.x.y` (semver)
- **No direct main:** Merge via PR (develop → main)

## API Stability

- **Breaking Changes:** Permitidos cuando exista PLAN + AUDIT + GO explícito y guía de migración actualizada
- **Deprecation**: Issue warning + 1 minor release before removal
- **Wrappers:** Mantener solo entry points legacy cuyo coste de soporte siga siendo razonable

## Security

- **SQL Injection:** Always use parameterized queries (SQLAlchemy Core)
- **Credentials:** Never log passwords; use connection pools
- **Audit Trail:** All mutations logged with user/timestamp
