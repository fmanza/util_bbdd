# TRACEABILITY

## Session metadata
- id: 2026-10-01o-fix-isolate-low-findings
- fecha: 2026-10-01
- rama: develop (base `64e7585`)
- flujo: PLAN + AUDIT_PLAN (`PLAN_AUDIT_PLAN.md`, GO_CONDICIONAL) → «Si» (D-1 no, D-2 a, D-3 a) → IMPLEMENT → VERSION

## Prompt issued
«Los tres hallazgos, PLAN Y AUDIT +PLAN» (B-1, B-3 y B-4 del `/audit-code` de `e2ce535..HEAD`) → «Si».

## AI output summary
- Sondas previas (`probes/`): B-1 confirmado con pyodbc y pymssql; **B-3 reclasificado a MEDIA**: con
  `sqlite3` `autocommit=True` las filas no se confirmaban y la BD quedaba bloqueada; quitar el `BEGIN` no bastaba (el
  `ROLLBACK TO` deja abierto el SAVEPOINT externo). El modo `AUTOCOMMIT` de SQLAlchemy funcionaba.
- `bulk/_support/rejects.py`:
  - B-1: `_rollback_after_data_error`: si el rollback al SAVEPOINT falla, se relanza el error de datos con una nota
    (XACT_ABORT ON) y el error del rollback como `__cause__`.
  - B-3: `_savepoint` decide por `driver.autocommit`: heredado → `BEGIN` como antes; `True` → `ValueError` antes de
    enviar nada.
  - B-4: `RejectsWriter` con `_audit.repository._get_file_lock`; cabecera por `handle.tell() == 0`; primera escritura
    de la instancia aparta un fichero con otra cabecera (`AuditCsvRepository._ruta_apartado`, reutilizado sin cambios).
- Tests: 6 unitarios (rollback fallido, sqlite3 `autocommit=True`, `AUTOCOMMIT` de SQLAlchemy limpio y con rechazo,
  cabecera ajena, 4 hilos sobre la misma ruta) + integración SQL Server `XACT_ABORT ON` (pyodbc y pymssql). Mutación: sin
  el lock compartido, el test de hilos falla 3/3.
- Docs: límites en `docs/api/bulk_crud.md`; CHANGELOG (entrada *Added* de `isolate`, aún sin publicar).

## Validación
`ruff`/`mypy` limpios (390); `pytest` 5953 passed; integración `test_bulk_audit_20261001.py` 91 passed (5 servidores)
+ `isolate and mssql` con pymssql 5 passed; `zensical build --strict` sin avisos.

## VERSION — v0.26.0 (`/version-closure`)
- Alcance de la versión (`e2ce535..HEAD`): P-1 (`d2c49ce`), spikes de la Fase 3 (`d53834f`), `prefetch_blocks`
  (`879c3ad`), `on_error="isolate"` (`9e9a914`) y sus correcciones del audit-code (`64e7585`, `6985a0a`).
- SemVer MINOR: API pública nueva (`prefetch_blocks`, `on_error`, `rejects_csv_path`, `max_rejects`, `rows_rejected`),
  opt-in; sin cambios incompatibles ni migraciones. Python `>=3.12` sin cambios; los 6 motores.
- Versión `0.26.0` en `pyproject.toml`, `README.md`, `docs/index.md`, `docs/roadmap.md` y pie de `docs/architecture.md`;
  `CHANGELOG.md` `[Unreleased]` → `[0.26.0] - 2026-10-01`; `.ai/CURRENT_STATE.md` y `SESSIONS_DIGEST.md`.
- Checklist ejecutado: `ruff check`/`format --check` limpios; `mypy` (390) limpio; `pytest` 5953 passed, 341 skipped;
  `tests/integration` 487 passed (5 servidores, pyodbc); `python -m build` → `util_bbdd-0.26.0`; `zensical build
  --strict` sin avisos.
- Rollback: `git revert` del commit de release y de los seis commits de la versión (en orden inverso) o volver al tag
  `v0.25.1`; sin datos ni esquemas que migrar. Riesgo: quien ya use `prefetch_blocks`/`on_error` recibe `TypeError`
  (parámetro desconocido) al volver.
- Limitaciones conocidas: truncado no aislable en Oracle/SQL Server; `XACT_ABORT ON` impide aislar; sin lock entre
  procesos para el CSV de rechazos; `isolate` no disponible en `ParallelBulkLoader` ni `dump`; PostgreSQL 1,65× con 10
  filas malas en lotes de 20 000.
- Handoff: push de `develop` y tag `v0.26.0`; pendientes de `bulk`: S-1 (procesos, NO_GO por ahora), S-3 (`ClientRead`),
  `isolate` en `ParallelBulkLoader`/`dump`, `batcherrors` de Oracle.

## Directrices para Futuras IAs
- **[release]**: `tests/unit/test_docs_version.py` exige la misma versión en `pyproject.toml`, `README.md`, `docs/index.md` y `docs/roadmap.md`; el pie de `docs/architecture.md` se actualiza a mano.
- **[bulk/sqlite]**: con `sqlite3` en Python ≥ 3.12 el modo de transacción lo da `Connection.autocommit`
  (`LEGACY_TRANSACTION_CONTROL`, `True`, `False`), no solo `isolation_level`; con `autocommit=True` no hay forma segura
  de usar SAVEPOINT desde SQLAlchemy.
- **[bulk/rejects]**: un rollback a SAVEPOINT puede fallar (XACT_ABORT ON, conexión rota); el error útil para el usuario
  es el de datos original, con el del rollback como causa.
- **[bulk/csv]**: los CSV que escribe `bulk` (auditoría y rechazos) comparten `_audit.repository._get_file_lock`; solo
  protege entre hilos de un proceso.

## Veredicto final
Veredicto: CLOSED
