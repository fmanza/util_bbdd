# TRACEABILITY

## Session metadata
- id: 2026-10-01s-feat-oracle-batcherrors
- fecha: 2026-10-01
- rama: develop (base `5fefcc7`)
- skill: new-feature (PLAN + AUDIT_PLAN `PLAN_AUDIT_PLAN.md`, GO → «si» → IMPLEMENT → VERSION)

## Prompt issued
«Acepto el punto 1 …» → PLAN/AUDIT_PLAN → «si».

## AI output summary
- `bulk/_support/oracle_batch_errors.py` (nuevo; en `_support` y no en `_execution` para que `rejects.py` no dependa de
  `_execution`): `supports`, `install` (listener `do_executemany` idempotente por engine), `collect` (`ContextVar`),
  `as_exception`.
- `Isolator(batch_errors=…)` y `_run_batch_errors`: un envío por lote en un SAVEPOINT; rechazos por offset;
  `max_rejects` superado → se rechazan los que caben, vuelta al SAVEPOINT y reenvío sin colector (error real del driver).
- `crud.py`: `__batch_errors()` (Oracle + oracledb, instala el listener); en el UPDATE, `batch_errors` solo sin columnas
  LOB (`_LOB_TYPES = (Text, LargeBinary, JSON)`; CLOB/NCLOB/UnicodeText/BLOB son subclases).
- Tests: 7 unitarios (`test_on_error_isolate.py`: un envío, frames, `max_rejects` con reenvío, error de sentencia,
  `supports`/`install` idempotente, LOB en UPDATE) + integración Oracle (4 errores aislados que antes no, UPDATE con LOB
  por bisección, `max_rejects`); el UPDATE demasiado largo de Oracle pasa al test de aislados.
- Medición con la API final (`bench_isolate_oracle.log`, 1M, 3 repeticiones): sin filas malas 1,04× (una repetición de
  11,09 s), 10 malas 1,08× (antes 1,20–1,22× con bisección).
- Docs (`bulk_crud.md`, `bulk_operations.md`, `benchmarks.md`, pie de `architecture.md` 391); CHANGELOG `[Unreleased]`.

## Validación
`ruff`/`mypy` limpios (391); `pytest` 5960 passed; `tests/integration` 491 passed (5 servidores); `zensical build
--strict` sin avisos.

## Directrices para Futuras IAs
- **[bulk/oracle]**: `oracle_batch_errors` vive en `bulk/_support/`; `_support` no importa de `_execution`.
- **[bulk/oracle]**: el listener `do_executemany` está inactivo salvo dentro de `collect()` en ese hilo; no afecta a
  operaciones sin `isolate` aunque esté registrado en el engine.
- **[bulk/oracle]**: no usar `batcherrors` en UPDATE con binds LOB (ORA-03106, oracledb 4.0.1 thin); volver a probar con
  versiones nuevas de oracledb (`s5_ora03106.py` de `2026-10-01r`) antes de quitar la regla.

## Veredicto final
Veredicto: CLOSED
