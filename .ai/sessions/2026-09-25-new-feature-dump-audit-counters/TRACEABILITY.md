# TRACEABILITY

## Session metadata
- id: 2026-09-25-new-feature-dump-audit-counters
- fecha: 2026-09-25
- rama: develop (base `5de5843`)
- skill: new-feature (PLAN + AUDIT_PLAN aprobados; IMPLEMENT + AUDIT_CODE + VERSION)
- origen: pendiente de `2026-09-25-new-feature-loader-audit-roadmap`: "el resumen de auditoría de dump no suma todavía los contadores nuevos"

## Prompt issued
```
El resumen de auditoría de dump no suma todavía los contadores nuevos. PLAN y AUDIT_PLAN
Adelante
```

## Decisiones (AUDIT_PLAN, opciones recomendadas aprobadas con "Adelante")
- **1a**: el resumen se devuelve sin entradas en el CSV si `audit_failures`, `unaudited_committed_rows` o `audit_uncommitted_records` es > 0. `audited_rows` por sí solo no basta.
- **2a**: WARNING si `total_filas` (CSV) ≠ `audited_rows` (contadores). No se añade ningún campo.
- **Ajuste en IMPLEMENT**: `_build_audit_summary(..., audited_rows: int | None = None)`. `None` significa "no se conoce" y no se compara con el CSV, así que las llamadas sin contadores no dan avisos falsos.

## AI output summary
- Commit previo de la implementación del roadmap del loader: `5de5843`.
- `dump/_models.py`: `DumpAuditSummary.audited_rows`, `unaudited_committed_rows` y `audit_uncommitted_records`, con valor 0 por defecto y al final.
- `dump/orchestrator.py`:
  - dataclass privado `_AuditCounters` (`of()` sobre `BulkCrud` o `ParallelLoadResult`, `__add__`);
  - `_loader_audit_failures` pasa a `_loader_audit`, y `_audit_failures()` a `_audit_counters()`;
  - nuevo `_summarize_audit()`;
  - `_build_audit_summary` con parámetros keyword-only nuevos; la firma posicional no cambia.
- **Hallazgo durante IMPLEMENT**: en `dump`, cada chunk leído mide `chunk_size` filas, así que cada operación es un solo lote y nunca queda confirmada a medias. En la carga por tabla entera `unaudited_committed_rows` siempre vale 0. En la carga por rangos también, porque sus lectores usan el mismo `chunksize`. El campo se mantiene por coherencia con el loader y por si cambia el tamaño de lectura.
- Docs: `docs/api/dump.md`. `CHANGELOG.md` (*Added*).

## Validación
- **Tests**:
  - `test_orchestrator.py`: el test del loader acumula los 4 contadores entre dos tablas; +6 de `_build_audit_summary` (incidencias nuevas sin entradas ×2, `audited_rows` solo → `None`, copia al resumen, WARNING por discrepancia y sin WARNING).
  - `test_parallel_loader_audit.py` +2 E2E en SQLite:
    - volcado correcto: `audited_rows == total_filas == 3`;
    - tabla fallida con commits periódicos: `(audited, unaudited, total_filas) == (2, 0, 2)`.
- **Mutaciones**: 11, todas muertas.
- **Calidad**:
  - `ruff check` y `ruff format --check` limpios;
  - `mypy src tests/unit/test_protocol_conformance.py` limpio;
  - `pytest tests/unit`: **4408 passed**;
  - `mkdocs build --strict`: exit 0.

## AUDIT_CODE
- **Compatibilidad**: campos nuevos con valor por defecto al final de `DumpAuditSummary`. `_build_audit_summary` es privado y conserva su firma posicional. `audit_summary` se devuelve en más casos, solo cuando hay incidencias (CHANGELOG).
- **Hilos**: `_loader_audit` se actualiza bajo `_audit_lock`. Los contadores de las `BulkCrud` se leen al final, cuando los hilos ya terminaron.
- **Doble conteo**: las `BulkCrud` del loader no se registran en `_audit_cruds`; sus contadores solo llegan a través de `ParallelLoadResult`.
- **Mocks**: ningún test de `dump` activa `bulk_audit_path` con `BulkCrud` parcheada (verificado).
- **Fuera del alcance**: el informe Excel (`DumpReporter`) no usa `audit_summary`.

## Rollback
`git revert <commit>`. No hay migración de datos.

## Directrices para Futuras IAs
- **[dump / auditoría]**: toda fuente de contadores de auditoría del volcado debe pasar por `_AuditCounters`, ya sea una `BulkCrud` registrada con `_make_worker_crud()` o un `ParallelLoadResult` acumulado en `_loader_audit`. Si no, no llega a `DumpAuditSummary`.
- **[dump / auditoría]**: `total_filas` sale del CSV (filtrado por hora); `audited_rows`, de los contadores. No sustituir uno por otro: miden cosas distintas y su diferencia es la señal.

## Veredicto final
CLOSED
