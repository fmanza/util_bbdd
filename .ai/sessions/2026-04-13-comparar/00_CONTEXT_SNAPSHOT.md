# CONTEXT SNAPSHOT

## Contexto del repositorio revisado

- `.ai/architecture.md` — arquitectura v0.6.7, jerarquía 3 niveles
- `.ai/sessions/INDEX.md` — inventario de sesiones previas
- `src/util_bbdd/comparar/comparator.py` — 800 LOC, SchemaComparator
- `src/util_bbdd/comparar/contracts.py` — SchemaComparatorProtocol, DiffReporterProtocol
- `src/util_bbdd/comparar/models.py` — frozen dataclasses
- `src/util_bbdd/comparar/__init__.py` — exports públicos
- `src/util_bbdd/connection/params.py` — ConnectionParamsManager, _BUILD_SUPPORTED_TYPES
- `src/util_bbdd/_drivers/validator.py` — DatabaseTypeValidator, database_types.json
- `src/util_bbdd/data/database_types.json` — supported_db_types: [mariadb, oracle, postgresql, hsqldb, sqlserver, sqlite]
- `src/util_bbdd/factory/sqlalchemy_engine_factory.py` — mapeo db_type → dialect URL
- `tests/comparar/test_comparator.py` — 750+ LOC, mocks + SQLite real

## Estado actual observado

- Tests: 1703 passed / 1 skipped (post-sesión 2026-04-13)
- Lint / mypy: limpios
- Cambios pre-existentes: fix `_core/capabilities.py` aplicado en sesión anterior del mismo día

## Estado Git relevante

- Rama activa: develop
- Cambios locales pre-existentes: connection/factory.py + factory/pool_factory.py (sesión 2026-04-13)
- Último tag / versión publicada: v0.6.7

## Clasificación metodológica

- Tipo principal: tech-debt
- Estado real de alcance: acotado (módulo comparar/ con análisis de cobertura multimotor)
- Consecuencia: solo análisis; IMPLEMENT requiere nueva sesión con aprobación

## Gate G0 · Context Ready

Veredicto: GO
Condiciones pendientes: ninguna para la fase de análisis.
