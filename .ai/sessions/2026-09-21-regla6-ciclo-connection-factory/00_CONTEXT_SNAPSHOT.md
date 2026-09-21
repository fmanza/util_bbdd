# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`
- `.ai/architecture.md`, `.ai/DECISIONS_LOG.md`, `.ai/CURRENT_STATE.md`, `.ai/sessions/INDEX.md`, `.ai/sessions/SESSIONS_DIGEST.md`, `.ai/sessions/TEMPLATE/`
- `.github/instructions/architecture.instructions.md` (Reglas #1–#6), `.github/instructions/sync.instructions.md`
- `src/util_bbdd/connection/` y `src/util_bbdd/factory/` completos; `src/util_bbdd/__init__.py`
- `src/util_bbdd/bulk/_support/pk_sync.py`, `bulk/crud.py`, `dump/orchestrator.py`
- `src/util_bbdd/metadata/` (`contracts.py`, `normalizer.py`, `adapters/base_adapter.py`, `mariadb/tables.py`)
- `src/util_bbdd/analysis/` y `src/util_bbdd/doc/` (imports de `managers`, puertos, adaptador)
- `docs/architecture.md`, `docs/guides/architecture_diagram_guide.md`, `scripts/gen_arquitectura_capas.py`
- `README.md` (sección de arquitectura), `docs/guides/onboarding_dev.md`, `CHANGELOG.md`, `mkdocs.yml`
- `pytest.ini`, `tests/conftest.py`, `tests/integration/conftest.py`, `docker-compose.yml`

## Estado actual observado
- Tests: 3826 passed / 1 skipped (primera medición, tras el primer cambio).
- Lint: `ruff check src tests` limpio. `ruff format --check` ya señalaba 5 ficheros previos sin formatear: `bulk/crud.py`, `bulk/_execution/parallel_loader.py`, `bulk/_execution/range_partitioner.py`, `tests/unit/bulk/test_maintenance_scope.py` y `tests/unit/bulk/test_parallel_loader.py`.
- `mypy src`: 2 errores previos en `docs_build_plugin.py:25,27` (`var-annotated`, `unused-ignore`).
- `mkdocs build --strict`: 13 warnings previos (faltan `installation.md` y `roadmap.md`).
- El trabajo del diagrama de capas (`docs/architecture.md`, `mkdocs.yml`, `docs/assets/…`, `scripts/gen_arquitectura_capas.py`) estaba sin commitear al empezar; el usuario lo commiteó durante la sesión (`712c91b`, `485ab8e`).

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: los del diagrama de capas descritos arriba (ya commiteados por el usuario a mitad de sesión).
- Último tag / versión publicada: `v0.10.0` según `.ai/architecture.md` (no se verificó `git tag`).
- HEAD al empezar: `802a264`. Commit de esta sesión: `92e6c7c` (local, sin push).

## Clasificación metodológica
- Tipo principal: audit_code → refactor (+ new_feature al reincorporar la utilidad)
- Estado real de alcance: acotado por fases; cada una con instrucción explícita del usuario
- Consecuencia: el endurecimiento a capas estrictas (pasos 1–3) queda como fase posterior, con PLAN y AUDIT_PLAN ya emitidos (`01_PLAN_capas_estrictas.md`)

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes (si aplica):
- Ninguna al inicio. La verificación contra un MariaDB real dependió de que el usuario aportara el servidor de pruebas.
