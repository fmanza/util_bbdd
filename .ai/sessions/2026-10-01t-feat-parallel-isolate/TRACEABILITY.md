# TRACEABILITY

## Session metadata
- id: 2026-10-01t-feat-parallel-isolate
- fecha: 2026-10-01
- rama: develop (base `909df1c`)
- skill: new-feature (PLAN + AUDIT_PLAN `PLAN_AUDIT_PLAN.md`, GO → «si» → IMPLEMENT → VERSION)

## Prompt issued
«Sigue con el PLAN y AUDIT_PLAN de batcherrors, y luego pasa a la Fase 3» → «si».

## AI output summary
- `rejects.py`: columna `particion` en `REJECT_COLUMNS` (entre `operacion` y `fila`); `RejectsWriter.write(partition=…)`;
  `validate_isolation()` común a `BulkCrud` y al loader.
- `crud.py`: `_tag_rejects(partition, offset)` (uso interno del loader); el `on_reject` suma `offset` (filas saltadas al
  reanudar, R-1) y escribe la partición.
- `parallel_loader.py`: `on_error`, `rejects_csv_path`, `max_rejects` validados antes del pool y pasados a cada `BulkCrud`;
  `_tag_rejects(index, resume_from)` antes de cada intento; D-2: sin reintento si el intento escribió rechazos (error
  explícito, como PL-2); `PartitionResult.rows_rejected` y `ParallelLoadResult.rows_rejected`.
- Tests: `tests/unit/bulk/test_parallel_loader_isolate.py` (10: rechazos por partición y conciliación con la auditoría,
  update/delete, sin reintento con rechazos, reintento sin rechazos con posición absoluta tras reanudar, `max_rejects`
  por partición, validación, `raise` sin cambios); mocks de `test_parallel_loader*.py` con `rows_rejected = 0`;
  integración `test_parallel_isolate_load_update_delete` (4 hilos, 5 servidores, también pymssql). Mutaciones: sin el
  desplazamiento o sin la regla D-2, sus tests fallan.
- Docs: `docs/api/bulk_parallel.md` (parámetros, `rows_rejected`, conciliación), `docs/api/bulk_crud.md` (columna);
  CHANGELOG *Added* y *Changed* (formato del CSV).

## Validación
`ruff`/`mypy` limpios (391); `pytest` 5970 passed, 350 skipped; `tests/integration` 496 passed (5 servidores, pyodbc) +
`isolate and mssql` con pymssql 6 passed; `zensical build --strict` sin avisos.

## Directrices para Futuras IAs
- **[bulk/paralelo]**: la partición y el desplazamiento del CSV de rechazos se fijan con `BulkCrud._tag_rejects` antes de
  cada intento; `ParallelBulkLoader` es su único llamador.
- **[bulk/paralelo]**: igual que PL-2 con la auditoría estricta, cualquier efecto fuera de la BD escrito por un intento
  fallido (auditoría, rechazos) impide reintentar la partición.
- **[bulk/rejects]**: la cabecera del CSV de rechazos cambió tras la 0.26.0; B-4 aparta los ficheros antiguos.

## Veredicto final
Veredicto: CLOSED
