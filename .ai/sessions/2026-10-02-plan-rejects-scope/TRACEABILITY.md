# TRACEABILITY

## Session metadata
- id: 2026-10-02-plan-rejects-scope
- fecha: 2026-10-02
- rama: develop (base `97b595d`, v0.27.1)
- flujo: deuda técnica del audit-code (`_tag_rejects`) → PLAN + AUDIT_PLAN (`PLAN_AUDIT_PLAN.md`, GO_CONDICIONAL) → «Si»
  (D-1 a: un cambio con desacoplamiento + API + corrección; D-2 a: solo rechazos; D-3 `rejects_scope`) → IMPLEMENT

## AI output summary
- Sonda (`probe_maintenance_rejects.py`): con `disable_constraints=True` sin hoist, posiciones por chunk (`[1, 1]`) y
  `max_rejects` por chunk → bug de la 0.27.0 (E-2); el mismo patrón afectaba a quien cargara por chunks dentro de
  `bulk_session` (E-3).
- `crud.py`: `rejects_scope(*, partition, row_offset)` público (`_RejectsScope`: partición, desplazamiento, rechazos ya
  hechos); `__isolating` entrega `_IsolatedOperation` y cada llamador anota sus filas de entrada (pipeline:
  `rowcount`; streams: `total`); al cerrar cada operación el ámbito avanza posición y presupuesto. Eliminados
  `_tag_rejects`, `_rejects_partition`, `_rejects_offset`.
- `rejects.py`: `Isolator(already_rejected=…)` para el presupuesto común (bisección y `batcherrors`).
- `parallel_loader.py`: cada intento en `with crud.rejects_scope(partition=index, row_offset=resume_from)`; sin acceso a
  miembros privados de `BulkCrud`.
- Tests: 5 unitarios de `rejects_scope`, 2 del loader (streams/maintenance_scope); integración
  `test_parallel_isolate_positions_with_disable_constraints` (5 motores × 2 vías). Mutación: sin el ámbito en el loader,
  7 tests fallan.
- Docs: `docs/api/bulk_crud.md`, `docs/api/bulk_parallel.md`; CHANGELOG *Added* y *Fixed*.

## Validación
`ruff`/`mypy` limpios (391); `pytest` 5988 passed, 436 skipped; `tests/integration` 582 passed; `zensical build
--strict` sin avisos.

## Directrices para Futuras IAs
- **[bulk/rejects]**: la posición y el presupuesto de rechazos de varias operaciones se agrupan con
  `BulkCrud.rejects_scope`; no reintroducir estado privado compartido entre `ParallelBulkLoader` y `BulkCrud`.
- **[bulk/rejects]**: todo llamador de `__isolating` debe anotar `rows` (filas de entrada) para que el ámbito avance.

## Veredicto final
Veredicto: CLOSED
