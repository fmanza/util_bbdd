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

## Directrices para Futuras IAs
- **[dump]**: `dump` desactiva las constraints del destino durante la carga; con `isolate` solo se apartan PK, NOT NULL
  y errores de tipo; las FK huérfanas aparecen al rehabilitar (`constraint_results`).
- **[dump]**: la `BulkCrud` de cada hilo se reutiliza entre tablas: cualquier contador por tabla se calcula por
  diferencia antes/después de `bulk_insert_from_chunks`.

## Veredicto final
Veredicto: CLOSED
