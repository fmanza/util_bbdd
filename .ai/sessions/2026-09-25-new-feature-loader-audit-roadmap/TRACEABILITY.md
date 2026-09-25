# TRACEABILITY

## Session metadata
- id: 2026-09-25-new-feature-loader-audit-roadmap
- fecha: 2026-09-25
- rama: develop (base `ba455d7`)
- skill: IMPLEMENT del roadmap `2026-09-25-audit-code-parallel-loader-audit/optimization_roadmap_audit_manager.md`
- fase: IMPLEMENT + AUDIT_CODE (autoauditoría con mutaciones) + VERSION

## Prompt issued
```
commit e IMPLEMENT
```

## Context supplied
- Informe y roadmap de la sesión `2026-09-25-audit-code-parallel-loader-audit` (hallazgos PL-1 a PL-10)
- Reproductores `bench/repro_loader_audit.py` y banco `bench/bench_loader_audit.py` de esa sesión

## AI output summary
- Commit de los artefactos de la auditoría: `ba455d7`.
- Implementado Fase 1 y Fase 2 del roadmap. L-1 y L-2 no se implementan: cambian el contrato del CSV y el roadmap
  los marca como opcionales.

| ID | Hallazgo | Cambio |
|---|---|---|
| QW-1 | PL-3 | `ParallelBulkLoader._resolve_table` pasa `enable_fast_executemany` (y `warn_if_audit_disabled=False`) a su `BulkCrud` |
| QW-2 | PL-4 | `ParallelBulkLoader.__init__` valida `audit_csv_path` creando un `AuditManager` → `AuditConfigError` antes del pool |
| QW-3 | PL-7, PL-8 | `AuditError` en `_EXPECTED_ERRORS`; la rama de reintentos agotados usa `_partition_error()` |
| M-1 | PL-2 | `BulkPersistenceManager._written_uncommitted` + `audit_uncommitted_records`; `_load_partition` no reintenta si > 0 |
| M-2 | PL-1 | `bulk_session` pasa `committed_rows` a `end_session_audit` al fallar con `commit_every_n_chunks`; `unaudited_committed_rows`; aviso "sin confirmarlos enteros" + WARNING con las filas que no constan |
| M-3 | PL-6 | `audited_rows` en `BulkPersistenceManager`, `BulkCrud`, `PartitionResult` y `ParallelLoadResult` |
| M-4 | PL-5 | Opción (b): `AuditManager(warn_if_disabled)`, `BulkCrud(warn_if_audit_disabled)`; el loader y `dump` pasan `False` y avisan con un INFO por carga |
| M-5 | PL-9 | `_confirmed` + umbrales `_CONFIRMED_FLUSH_RECORDS=64` / `_CONFIRMED_FLUSH_SECONDS=1.0`; escritura forzada al cerrar la sesión con o sin error; strict sin cambios |

- `_load_partition` se partió (`_run_attempt`, `_partition_result`) para no pasar de complejidad cognitiva 15.
- Docs: `docs/api/bulk-parallel.md`, `docs/api/bulk-crud.md`, `docs/functional/bulk-audit.md`. `CHANGELOG.md`
  (*Added*, *Changed*, *Fixed*).

## Validación
- **Tests nuevos**:
  - `tests/unit/bulk/test_parallel_loader_audit_fidelity.py` (22): R1–R5 como tests, umbrales de M-5 (registros y tiempo), escritura al fallar, strict sin agrupar, avisos.
  - `test_parallel_loader_audit.py` (+1): `dump` sin auditoría → un solo INFO.
  - Ajustados 3 mocks de `test_parallel_loader.py`, que ahora fijan `audit_uncommitted_records = 0`.
- **Mutaciones**: 14 (una o más por ID). **Todas** hacen fallar algún test.
- **Reproductores de la auditoría** tras el cambio:
  - R1: aviso correcto;
  - R2 strict: sin reintento, CSV `[20, 20]` y BD 0, error explicado;
  - R3: `fast_executemany` sigue en `False`;
  - R4: 0 WARNING;
  - R5: `AuditConfigError` en el constructor.
- **Banco** (SQLite, 1M filas, chunk del lector 500, 4 hilos):

  | Modo | Aperturas CSV (antes → ahora) | Tiempo en escritura | % en escritura | Δ E2E |
  |---|---|---|---|---|
  | `commit_every_n_chunks=2` | 2000 → 35 | 416–477 ms → 75 ms | 8,3–9,3 % → 1,56 % | +8/+9 % → +2,8 % (ruido) |
  | `commit_every_n_chunks=10` | 400 → 35 | 100 ms → 18 ms | 2,2 % → 0,39 % | ruido |
  | atómico | 4 → 4 | 8,6 ms | 0,19 % | ruido |

  El objetivo del roadmap para N=2 (≤ 0,5 %) **no se alcanza**. Cada apertura cuesta ~2 ms bajo contención del GIL con 4 hilos
  (open/close sueltan el GIL y recuperarlo espera al intervalo de cambio), frente a 0,2 ms en el banco anterior. Subir
  el umbral a 256 ahorraría poco, porque el umbral de 1 s ya obliga a ~5 escrituras por worker en una carga de 5 s, y
  ampliaría la ventana de pérdida.
- **Calidad**:
  - `ruff check` y `ruff format --check` limpios;
  - `mypy src tests/unit/test_protocol_conformance.py` limpio (342 ficheros);
  - `pytest tests/unit`: **4400 passed**;
  - `mkdocs build --strict`: exit 0 sin avisos.

## AUDIT_CODE
- **Compatibilidad**: solo parámetros keyword y campos nuevos con valor por defecto, al final de los dataclasses.
- **Cambios de comportamiento documentados en CHANGELOG**:
  - el WARNING de auditoría deshabilitada pasa a INFO dentro del loader y de `dump`;
  - una ruta de auditoría inválida falla en el constructor del loader;
  - `partition_errors` de reintentos agotados por `TimeoutError` lleva ahora el tipo (`TimeoutError: ...`);
  - la escritura por tandas con `commit_every_n_chunks`.
- **Limitaciones aceptadas**:
  - `unaudited_committed_rows` es aproximado en sesiones que mezclan DELETE (el DELETE no suma a `rows_committed`); se excluye de la comparación y se documenta;
  - si el proceso muere de golpe, se pierden como mucho 64 registros ya confirmados (M-5).
- **No hecho**:
  - `DumpAuditSummary` no agrega los contadores nuevos (solo `audit_failures`, como antes);
  - banco en motores servidor (sin `UTIL_BBDD_BENCH_PASSWORD`).
- **Desviación del roadmap**: el roadmap proponía un commit por ID. Se hace uno solo porque `persistence.py` concentra M-1, M-2, M-3 y M-5 en los mismos métodos.

## Rollback
`git revert <commit>` (un solo commit; no hay migración de datos ni cambio de formato del CSV).

## Directrices para Futuras IAs
- **[bulk / persistence]**: `flush_audit_after_commit()` significa "el commit acaba de ir bien". Llamarlo antes del commit o tras uno fallido rompe `audit_uncommitted_records` y el recuento de `unaudited_committed_rows`.
- **[bulk / persistence]**: sin `audit_strict`, lo confirmado pasa por `_confirmed` y solo `end_session_audit()` garantiza que se escriba. Todo camino que abra una sesión de auditoría debe cerrarla con `end_session_audit()` en un `finally`.
- **[bulk / tests con mocks]**: si un test sustituye `BulkCrud` por un `MagicMock` y provoca un error retriable, debe fijar `audit_uncommitted_records = 0`; si no, la comparación `> 0` falla con `TypeError`.
- **[bulk / medición]**: con varios hilos, el tiempo medido dentro de una escritura del CSV incluye la espera del GIL (~2 ms por apertura con 4 hilos ocupados). Comparar aperturas, no solo milisegundos.

## Veredicto final
CLOSED
