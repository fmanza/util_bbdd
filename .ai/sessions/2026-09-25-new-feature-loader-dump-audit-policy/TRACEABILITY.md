# TRACEABILITY

## Session metadata
- id: 2026-09-25-new-feature-loader-dump-audit-policy
- fecha: 2026-09-25
- rama: develop (base `1b072cf`)
- skill: new-feature
- origen: límite abierto tras M-2 (`ParallelBulkLoader` sin `audit_strict` ni `audit_failures`); alternativa A + `dump`, elegida por el usuario

## Prompt issued
```
Implement con la parte de dump
```

## AI output summary
- **Loader** (`bulk/_execution/parallel_loader.py`):
  - `ParallelBulkLoader(audit_strict=False)` se pasa a cada `BulkCrud`.
  - `PartitionResult.audit_failures` se rellena en los 3 caminos con `BulkCrud`: éxito, error permanente y reintentos agotados. Si falla la creación de la `BulkCrud` queda en 0.
  - `ParallelLoadResult.audit_failures` es una propiedad que suma las particiones.
  - Con strict, el error de auditoría cae en el `except Exception` genérico: error permanente, sin reintento.
- **Dump** (`dump/_models.py`, `dump/orchestrator.py`):
  - `DumpConfig.bulk_audit_strict` va al final del dataclass, para no romper a quien lo construye por posición.
  - `_make_worker_crud` crea y registra todas las `BulkCrud`, también la principal de `run`, que tenía una copia de los mismos argumentos.
  - `_load_in_pk_ranges` suma `result.audit_failures`. El estado está protegido por un lock y se reinicia en `run()` con `_reset_audit_tracking()`.
  - `DumpAuditSummary.audit_failures`. `_build_audit_summary(..., audit_failures=0)` devuelve un resumen a ceros si hubo fallos y no hay entradas.
- **Fallo encontrado al probar**: con strict, `_load_whole_table` solo capturaba `SQLAlchemyError`/`ValueError`. Un `AuditError`/`OSError` abortaba el volcado entero, y antes de M-2 esa era la política por defecto. Ahora queda como error de la tabla.
- **Docstring de `DumpConfig.max_parallel_tables`** corregido: afirmaba que la auditoría se desactivaba con paralelismo.

## Validación
- **Tests nuevos**:
  - `tests/unit/bulk/test_parallel_loader_audit.py` (5), con SQLite real: loader sin fallos, fail-open (2+2 = 4), strict sin reintento; `dump` de extremo a extremo en fail-open (datos cargados, `audit_failures=1`) y strict (tabla en error, 0 filas, el volcado sigue).
  - `tests/unit/dump/test_orchestrator.py` (+4): `audit_strict` y la suma del loader en `_load_in_pk_ranges`; resumen con fallos sin CSV, con entradas, y `None` sin fallos. El helper `_orch` de `TestLoadInPkRanges` llama a `_reset_audit_tracking()`.
- **Mutación**: 7 mutaciones (propagación a loader y `BulkCrud`, `audit_failures` en éxito, suma del loader, resumen sin entradas, captura por tabla). Todas hacen fallar algún test.
- **Calidad**:
  - `ruff check` y `ruff format --check` limpios; `mypy` limpio (342 ficheros);
  - `tests/unit` 4377 passed;
  - `mkdocs build --strict` sin avisos.

## AUDIT_CODE
- **Compatibilidad**: solo campos y parámetros nuevos, con valor por defecto y al final. `_build_audit_summary` conserva la firma posicional.
- **Hilos**: `_audit_cruds` y `_loader_audit_failures` bajo `_audit_lock`. El recuento lee `crud.audit_failures` al final del volcado, cuando los hilos ya terminaron.
- **Edge cases**:
  - Reintentos del loader en fail-open: la misma `BulkCrud` acumula los fallos de todos los intentos.
  - Los intentos deshechos no cuentan: lo pendiente se descarta, no falla.
- **No verificado**: motores servidor (sin credenciales del banco). La lógica no depende del dialecto.

## Rollback
`git revert <commit>`.

## Directrices para Futuras IAs
- **[dump / BulkCrud]**: crear siempre las `BulkCrud` del volcado con `_make_worker_crud()`; si no, sus `audit_failures` no llegan al resumen.
- **[dump / errores por tabla]**: la carga de una tabla debe capturar también `AuditError`/`OSError`. Un fallo de auditoría estricta es un error de esa tabla, no del volcado.
