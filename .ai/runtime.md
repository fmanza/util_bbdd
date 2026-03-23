# ⚙️ Runtime & Environment - util_bbdd

## Development Environment

### Prerequisites
- Python 3.11+
- pip, virtualenv (or conda)
- Git

### Setup

```bash
git clone <repo>
cd util_bbdd
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

### Project Root

- **Source code:** `src/util_bbdd/` (namespace package)
- **Tests:** `tests/` (pytest discovery)
- **Build output:** `build/`, `dist/`
- **Cache:** `.pytest_cache/`, `.ruff_cache/`, `venv/`

## Essential Commands

```bash
# Run tests
pytest -v --cov=src/util_bbdd --cov-report=html

# Type check
mypy src/util_bbdd --strict

# Lint & format
ruff check src/util_bbdd
black src/util_bbdd
isort src/util_bbdd

# Build
python -m build

# Clean
rm -rf build dist *.egg-info .pytest_cache htmlcov
```

## Database Testing

- **SQLite in-memory:** Default test DB (`:memory:`)
- **Docker Compose:** `docker-compose.yml` con MariaDB, PostgreSQL (optional para full integration)
- **Test Isolation:** Each test gets fresh connection; no shared state

## Async Runtime

- **Event Loop Policy:** `asyncio.new_event_loop()` (per-test isolation)
- **Marker:** `@pytest.mark.asyncio` para test async
- **Timeout:** 30s default (configurable vía pytest.ini)

## CI/CD

- **.github/workflows:** GitHub Actions (test, lint, coverage on PR)
- **branches:** main (stable), develop (integration), feature/* (work in progress)
- **Gate:** ≥90% coverage + all checks pass before merge to main

## Configuration Files

- **pyproject.toml:** Metadata, dependencies, tool config
- **pytest.ini:** Test discovery, markers, timeout
- **docker-compose.yml:** Test infrastructure (DB containers)
