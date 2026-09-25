# TRACEABILITY

## Session metadata
- id: 2026-09-25-new-feature-audit-deferred-fail-open
- fecha: 2026-09-25
- rama: develop (base `18c72d5`)
- skill: new-feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION
- origen: `.ai/sessions/2026-09-25-audit-code-audit-manager/` (hallazgos H1 y H2, ALTA; roadmap M-1 y M-2)

## Prompt issued
```
si, y usa la opción A
```
(tras proponer M-1 + M-2; opción A de M-2 = fail-open por defecto + `audit_strict`)

## AI output summary
- **M-1 (H2)**:
  - Dentro de `bulk_session` la auditoría se acumula como `AuditRecord` (nuevo, `bulk/_audit/record.py`, con el timestamp del fin de la operación).
  - Se escribe cuando un commit la confirma, con una sola apertura del CSV (`AuditCsvRepository.registrar_operaciones` / `AuditManager._registrar_lote`).
  - Puntos de volcado:
    - fin de la sesión atómica;
    - `persistence.commit(conn)` en el commit final de `commit_every_n_chunks`;
    - `_commit_hook` en los commits periódicos de `BatchStatementExecutor` y `DeleteBatchExecutor`;
    - al registrar una operación si `conn.in_transaction()` es falso (su propio commit periódico ya la confirmó).
  - En rollback, `end_session_audit` descarta con WARNING. `generar_sql=True` se escribe al momento.
- **M-2 (H1), opción A**:
  - `BulkCrud(audit_strict=False)` + `BulkCrud.audit_failures`.
  - Fail-open: `AuditError`/`OSError` al escribir → ERROR con los registros perdidos + contador, sin excepción.
  - Strict: se propaga. En sesión se escribe antes del commit, así que el fallo deshace la sesión.
- Sin cambios en `parallel_loader.py`: sus dos caminos (`bulk_insert_from_chunks`, `_load_with_maintenance`) ya usan `bulk_session`.
- **Formato del CSV**: sin cambios.

## Validación
- **Tests**:
  - `tests/unit/bulk/test_audit_deferred_session.py` (13, nuevo): sesión atómica, rollback, timestamp, `generar_sql`, sin ruta, streaming (fallo y 1 sola escritura para 20 chunks), `commit_every_n_chunks` (4 escenarios, incluido commit a mitad de operación), reintento de `ParallelBulkLoader`.
  - `tests/unit/bulk/test_audit_error_handling.py` (6): BLK-01 pasa a `audit_strict=True`; 3 tests fail-open, uno con un CSV que realmente no se puede escribir.
- **Mutación**: 6 mutaciones (sin diferir, sin gancho periódico, sin `in_transaction`, siempre strict, strict tras commit, sin descarte). Todas hacen fallar algún test. El test del commit a mitad de operación se añadió porque la mutación del gancho sobrevivía.
- **Calidad**:
  - `ruff check` y `ruff format --check` limpios;
  - `mypy src tests/unit/test_protocol_conformance.py` limpio (342 ficheros);
  - `tests/unit`: 4367 passed;
  - `mkdocs build --strict` sin avisos propios.
- **Reproductores de la auditoría**: R2 ya no lanza; R3 deja 0 filas en BD y 0 en el CSV.
- **Rendimiento** (tiempo dentro de la auditoría, SQLite 1M en streaming): chunk 5000 3,35 % → 0,12 %; chunk 500 16,5 % → 0,42 %.

## AUDIT_CODE
- **Regresiones potenciales**:
  - Cambio de comportamiento: un fallo de auditoría ya no lanza por defecto. Documentado en el CHANGELOG (*Changed*).
  - Quien necesite el comportamiento anterior usa `audit_strict=True`.
- **Edge cases**:
  - Con `commit_every_n_chunks`, una operación que falla con lotes ya confirmados no se anota (documentado; `rows_committed` da la cifra).
  - Strict + commit que falla tras escribir: filas de auditoría sin datos (raro, documentado en el diseño).
  - Sesiones anidadas: no soportadas, igual que antes. `__blocks_transaction` no anida.
  - El rollback + commit de restauración de `maintenance_scope` usa `conn.commit()` directo, sin volcar, y la excepción posterior descarta lo pendiente. Es correcto.
- **Seguridad**: el ERROR de fail-open incluye tabla, operación, filas, tiempo y `sql`; nunca valores de datos ni la URL.
- **Tipado**: sin `Any` nuevos salvo la conexión (mismo patrón que `_active_connection`).
- **No verificado**: motores servidor (las URLs del banco no están en el entorno). La lógica depende de `Connection.in_transaction()` y `commit()` de SQLAlchemy 2.0, comunes a todos los dialectos.
- **Pendiente**: `ParallelBulkLoader` no expone `audit_strict` ni suma `audit_failures` en `PartitionResult`; los fallos quedan como ERROR en el log.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Registro | `src/util_bbdd/bulk/_audit/record.py` | nuevo |
| Escritura por lotes | `src/util_bbdd/bulk/_audit/repository.py`, `src/util_bbdd/bulk/audit.py` | modificados |
| Sesión y fail-open | `src/util_bbdd/bulk/_support/persistence.py`, `src/util_bbdd/bulk/crud.py` | modificados |
| Gancho de commit | `src/util_bbdd/bulk/_execution/batch.py` | modificado |
| Tests | `tests/unit/bulk/test_audit_deferred_session.py` (nuevo), `tests/unit/bulk/test_audit_error_handling.py` | — |
| Docs | `docs/api/bulk-crud.md`, `docs/api/bulk-audit.md`, `docs/api/bulk-parallel.md`, `CHANGELOG.md` | modificados |

## Rollback
`git revert <commit>`. No hay migración: el CSV conserva el formato. Tras revertir, los fallos de auditoría vuelven a lanzar excepción.

## Directrices para Futuras IAs
- **[auditoría / sesión]**: la fila de auditoría se escribe cuando un commit confirma la operación. Todo commit nuevo sobre la conexión de `bulk_session` que confirme operaciones debe pasar por `BulkPersistenceManager.commit` (o por `_commit_periodico` en los ejecutores); un `conn.commit()` directo no vuelca la auditoría.
- **[auditoría / fallo]**: por defecto un fallo de escritura del CSV **no** lanza (`audit_strict=False`). No volver a relanzar: los datos ya están en la BD y el llamador reintentaría y duplicaría.
- **[auditoría / tests]**: para simular un fallo de escritura dentro de la sesión, parchear `AuditManager._registrar_lote`; fuera de sesión, `AuditManager.registrar_operacion`.
