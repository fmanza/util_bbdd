# TRACEABILITY

## Session metadata
- id: 2026-10-01k-fix-bulk-audit-debt
- fecha: 2026-10-01
- rama: develop (base `b98a7b2`, v0.25.0 publicada)
- skill: fix (deuda A3–A5 del audit-code de `2026-10-01i-perf-bulk-b04-batch-size/AUDIT_CODE_fases0-2_b04.md`)
- fase: PLAN → IMPLEMENT (test-first) → verificación

## Prompt issued
«Adelante con la propuesta» (empezar por A3; A4 y A5 en el mismo cambio).

## AI output summary
- **A3** (`bulk/crud.py`, `__ensure_no_open_session`): `bulk_insert_from_chunks` y `__stream_operation`
  (`bulk_update_from_chunks`/`bulk_delete_from_chunks`) lanzan `RuntimeError` si `self._session.active`, antes de
  reflejar o leer nada. Comprobado antes que ningún código interno las llama dentro de una sesión (`dump` y
  `ParallelBulkLoader` no lo hacen).
- **A4** (`bulk/_execution/executors.py`): `_commit_periodico` añade la nota `_COMMIT_FAILURE_NOTE` si falla el COMMIT;
  `batch_failure_note`, al verla, escribe «el lote N (filas …) se ejecutó; falló el COMMIT periódico posterior».
- **A5**: `__batch_note(operation: BulkOperation, ...)`; sin `type: ignore`.
- Tests: `tests/unit/bulk/test_open_session_and_commit_note.py` (5; 4 fallaban antes del fix: las tres vías dentro de
  una sesión —18 s de esperas `database is locked` en SQLite— y la nota del COMMIT).
- Docs: `docs/api/bulk_crud.md` (fila `RuntimeError`), `CHANGELOG.md` `[Unreleased]` → *Fixed*.

## Validación
- `ruff check`/`ruff format --check` limpios; `mypy src tests/unit/test_protocol_conformance.py`: sin errores (388).
- `pytest`: 5880 passed / 312 skipped. `tests/integration` (5 servidores, pyodbc): 455 passed.
- `zensical build --strict`: sin avisos.

## Impacto en API pública
- Llamar a una vía `*_from_chunks` dentro de un `bulk_session` abierto pasa a lanzar `RuntimeError` (los docstrings ya lo
  prohibían; antes bloqueaba en SQLite o rompía la atomicidad de la sesión externa).

## Rollback
- `git revert` del commit; sin migración.

## Directrices para Futuras IAs
- **[bulk/sesión]**: las vías `*_from_chunks` abren su propia `bulk_session`; dentro de otra, usar `*_from_df` por chunk.
- **[bulk/notas]**: un error con la nota `_COMMIT_FAILURE_NOTE` viene del COMMIT periódico, no de los datos del lote.
- **[edición]**: al insertar código antes de una función decorada, comprobar que no queda entre el decorador y el `def`.

## Cierre de versión (v0.25.1)
- Commits: `3e061c9` fix(bulk) y `release: v0.25.1` con tag anotado `v0.25.1` (local; push pendiente de decisión).
- Versión: PATCH (corrección; sin cambios de firma). CHANGELOG `[0.25.1] - 2026-10-01`; `pyproject.toml`, `README.md`,
  `docs/index.md`, `docs/roadmap.md` y pie de `docs/architecture.md` en 0.25.1.
- Checklist: `ruff`/`mypy` limpios; `pytest` 5880 passed (incluye `test_docs_version.py`); `tests/integration` 455
  passed; `python -m build` 0.25.1; `zensical build --strict` sin avisos.
- Compatibilidad: Python >= 3.12; todos los motores; ningún consumidor interno llamaba a `*_from_chunks` dentro de una
  sesión (`dump`, `ParallelBulkLoader`).
- Rollback: antes del push, `git tag -d v0.25.1 && git reset --hard b98a7b2`; después, `git revert` del release y de
  `3e061c9`.

## Veredicto final
Veredicto: CLOSED (v0.25.1)
Pendientes al cierre:
- Fase 3 del roadmap de `2026-10-01h` (spikes) y coste del filtro de OPENJSON (2,2 → 2,5 s/1M).
