# TRACEABILITY

## Session metadata
- id: 2026-10-01u-feat-dump-isolate
- fecha: 2026-10-01
- rama: develop (base `d065e38`)
- skill: new-feature (PLAN + AUDIT_PLAN `PLAN_AUDIT_PLAN.md`, GO_CONDICIONAL → «Si» con D-1 a y D-2 a → IMPLEMENT → VERSION)

## Prompt issued
«Fase 4» → PLAN/AUDIT_PLAN → «Si».

## AI output summary
- `dump/_models.py`: `DumpConfig.on_error`, `rejects_csv_path`, `max_rejects` (validados en `__post_init__` con
  `validate_isolation`); `TableDumpResult.rows_rejected`; `DumpResult.rows_rejected` (propiedad).
- `dump/orchestrator.py`: `_bulk_options()` pasa las tres opciones a `BulkCrud`/`ParallelBulkLoader`; rechazos por
  tabla por diferencia de `crud.rows_rejected` (la `BulkCrud` se reutiliza entre tablas del hilo) o de
  `ParallelLoadResult.rows_rejected` (rangos; `_load_in_pk_ranges` devuelve `(errores, rechazados)`); WARNING por tabla.
- `dump/reporters.py`: columna «Filas Rechazadas» tras «Filas Destino Después» (D-2); D-1: la tabla sigue `success`.
- Tests: `tests/unit/dump/test_dump_isolate.py` (8, SQLite → SQLite: NOT NULL, PK duplicada sin truncar, `max_rejects`
  con el volcado continuando, `raise` sin cambios, validación, columna del informe); 4 tests existentes adaptados al
  nuevo retorno y a las columnas del informe; integración `test_dump_isolate_not_null` (6 destinos × tabla entera/rangos)
  y `test_dump_isolate_narrower_target_column` (5 destinos sin SQL Server), también con pymssql.
- Docs: `docs/api/dump.md`; CHANGELOG *Added* y *Changed* (columna del informe).

## Validación
`ruff`/`mypy` limpios (391); `pytest` 5978 passed, 367 skipped; `tests/integration` 513 passed (5 servidores, pyodbc) +
`isolate and mssql` de dump con pymssql 2 passed; `zensical build --strict` sin avisos.

## VERSION — v0.27.0 (`/version-closure`)
- Alcance (`6eb9392..HEAD`): docs del escalado (`90b58e3`), spike S-5 (`2760e10`), planes (`5fefcc7`, `d065e38`),
  `batcherrors` en Oracle (`909df1c`), `ParallelBulkLoader` (`6e7d9be`), `dump` (`5a9b774`).
- SemVer MINOR: API nueva opt-in (`ParallelBulkLoader`/`DumpConfig`: `on_error`, `rejects_csv_path`, `max_rejects`;
  `rows_rejected` en resultados). Cambios de formato sin API rota: columna `particion` del CSV de rechazos (los CSV de la
  0.26.0 se apartan solos) y columna «Filas Rechazadas» del Excel de `dump` (desplaza tres columnas). Sin migraciones.
  Python `>=3.12` sin cambios; los 6 motores.
- Versión `0.27.0` en `pyproject.toml`, `README.md`, `docs/index.md`, `docs/roadmap.md` y pie de `docs/architecture.md`;
  `CHANGELOG.md` `[Unreleased]` → `[0.27.0] - 2026-10-01`; `.ai/CURRENT_STATE.md` y `SESSIONS_DIGEST.md`.
- Checklist: `ruff`/`format --check`, `mypy` (391), `pytest` 5978 passed / 367 skipped, `tests/integration` 513 passed,
  `python -m build` → `util_bbdd-0.27.0`, `zensical build --strict` sin avisos.
- Rollback: volver al tag `v0.26.0` o revertir los commits de la versión en orden inverso; quien use las opciones nuevas
  recibe `TypeError`; un CSV de rechazos con `particion` escrito por la 0.27.0 sería apartado por la 0.26.0 (cabecera
  distinta), sin mezclarse.
- Limitaciones: SQL Server no aísla el demasiado largo; Oracle tampoco en UPDATE con LOB; `dump` no aísla FK/CHECK
  (constraints desactivadas); sin lock entre procesos para los CSV.
- Handoff: push de `develop` y tag `v0.27.0`; reportar el ORA-03106 a python-oracledb; S-1 sigue NO_GO.

## Directrices para Futuras IAs
- **[release]**: en esta serie de sesiones la versión se toca en 5 sitios (`pyproject.toml`, README ×2, `docs/index.md`, `docs/roadmap.md`) más el pie de `docs/architecture.md`.
- **[dump]**: `dump` desactiva las constraints del destino durante la carga; con `isolate` solo se apartan PK, NOT NULL
  y errores de tipo; las FK huérfanas aparecen al rehabilitar (`constraint_results`).
- **[dump]**: la `BulkCrud` de cada hilo se reutiliza entre tablas: cualquier contador por tabla se calcula por
  diferencia antes/después de `bulk_insert_from_chunks`.

## Veredicto final
Veredicto: CLOSED
