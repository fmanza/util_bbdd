# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (hallazgos P-01…P-16 y estrategia de benchmark)
- `tests/integration/conftest.py` y `tests/integration/test_update_auto_increment_mariadb.py` (convención `UTIL_BBDD_TEST_<MOTOR>_URL` + `skipif`)
- `docker-compose.yml` (solo PostgreSQL, contenedor `postgres_db`)
- `scripts/gen_arquitectura_capas.py` y `tests/unit/test_architecture_import_rules.py` (patrón para testear scripts cargándolos con importlib)
- `docs/guides/benchmarks.md`, `mkdocs.yml`, `pyproject.toml`, `pytest.ini`, `.github/workflows/tests.yml`
- `src/util_bbdd/bulk/crud.py`, `_execution/batch.py`, `_support/validation.py`

## Estado actual observado
- Árbol limpio en `develop` (último commit `e8551d0`).
- Suite al cerrar la sesión: 4457 passed / 19 skipped (incluye 25 unitarios y 3 de integración SQLite nuevos; 15 de los skips son motores de servidor sin URL).
- Docker 29.6.1 disponible; contenedor `postgres_db` (PostgreSQL 18.3) en marcha en el puerto 5432.
- ODBC en este equipo: solo el driver antiguo `SQL Server`; `fast_executemany` (P-01) requiere ODBC Driver 17/18.
- Problemas previos, ajenos a esta sesión:
  - `mkdocs build --strict` aborta con 13 avisos: git registra `docs/INSTALLATION.md` y `docs/ROADMAP.md` en mayúsculas, pero `mkdocs.yml` y los enlaces usan `installation.md` / `roadmap.md`.
  - `ruff format --check` señala `src/util_bbdd/bulk/_execution/range_partitioner.py` y `tests/unit/bulk/test_maintenance_scope.py` (CI solo ejecuta `ruff check`).

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: v0.10.0 (release 0.11.0 en `CHANGELOG.md`)

## Clasificación metodológica
- Tipo principal: new_feature (herramienta de desarrollo; sin cambios en `src/`)
- Estado real de alcance: acotado
- Consecuencia: se procede sin tocar la API pública.

## Gate G0 · Context Ready
Veredicto: GO
