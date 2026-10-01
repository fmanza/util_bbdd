# TRACEABILITY

## Session metadata
- id: 2026-10-01i-perf-bulk-b04-batch-size
- fecha: 2026-10-01
- rama: develop (base `722dbd4`, v0.24.0 publicada)
- skill: refactor (`perf:`) — punto 1.5 del roadmap de `2026-10-01h-performance-audit-bulk-todo` (hallazgo B-04)
- fase: medición previa (R-6) → PLAN → IMPLEMENT → validación con banco

## Prompt issued
«Corregir desactualizado y B-04» (tras el push de v0.24.0). Lo «desactualizado» (`.ai/CURRENT_STATE.md` decía que el push
de v0.24.0 estaba pendiente) se corrigió en `722dbd4` (commit y push).

## Context supplied
- `2026-10-01h-performance-audit-bulk-todo`: `audit_report_bulk_20261001.md` § B-04, `AUDIT_PLAN.md` R-6 (repetir el
  barrido con `--repeat 3`; `dump` midió 20 000 −31 % en PostgreSQL y +81 % en SQL Server), `improvement_roadmap_bulk.md` 1.5.
- `dump/orchestrator.py:791` `_resolve_write_batch_size` (20 000 en PostgreSQL sin cadencia).

## AI output summary
1. **Barrido R-6** (`sweep/`): `scripts/bench_bulk.py --sizes 1000000 --repeat 3 --chunk-size {1000,5000,20000,50000}`,
   6 motores, código de v0.24.0: 216/216 mediciones correctas. Resumen en `sweep/summary_b04.txt`:
   - PostgreSQL INSERT 20 000 −13 % (50 000 −19 %), DELETE 20 000 −10 %, **UPDATE (staging) 20 000 +31 %**.
   - SQL Server DELETE (OPENJSON) 20 000 −20 % (50 000 +26 %); INSERT −5 % (marginal; `dump` midió lo contrario).
   - MySQL/MariaDB DELETE 50 000 +65 % / +42 %; 1000 peor en todos los motores y operaciones; resto ±5 %.
2. **Decisión**: un `chunk_size` único por motor no sirve (el UPDATE de PG empeora): lote por motor **y** operación
   solo cuando el usuario no fija `chunk_size` y no hay cadencia; 20 000 (no 50 000) en PostgreSQL por coherencia con
   `dump` y memoria por bloque; tope de 5000 filas por `DELETE … IN` en MySQL/MariaDB sea cual sea el lote.
3. **IMPLEMENT**:
   - `bulk/_support/batch_sizes.py` (nuevo, punto canónico): `DEFAULT_CHUNK_SIZE`, `resolve_batch_sizes`.
   - `crud.py`: `chunk_size: int | None = None`; `_batch_sizes` por operación; bloques de INSERT/UPDATE con su tamaño
     (también la vía de registros de `bulk_insert_from_chunks`); ejecutor de INSERT/UPDATE con
     `max(insert, update)` (no trocea los bloques); DELETE con su tamaño; notas de error con el tamaño de la operación;
     `self.chunk_size` (5000 o el explícito) sigue gobernando `generar_sql`; propiedad `batch_sizes`.
   - `parallel_loader.py`: `chunk_size: int | None = None`, delegado en cada `BulkCrud`.
   - `delete_strategies.py`: `_MYSQL_MAX_DELETE_ROWS = 5000`.
   - `scripts/bench_bulk.py`: `--chunk-size auto` (default nuevo).
   - Tests: `test_batch_sizes.py` (11, nuevo); `test_chunk_size_validation.py` (`None` ya es válido en `BulkCrud`);
     `test_parameter_limits.py` (troceo de 8 × 10 000 parámetros en vez de 65 534 + 14 466, sigue ≤ 65 535).
   - Docs: `docs/api/bulk_crud.md`, `docs/api/bulk_parallel.md`, `docs/guides/benchmarks.md`, pie de
     `docs/architecture.md` (388 ficheros); `CHANGELOG.md` `[Unreleased]`.
4. **Validación** (`validation/`): `--chunk-size auto` frente a 5000 (mediana de 3, 1M): PostgreSQL INSERT 4,04 → 3,45 s
   (−15 %), DELETE 1,86 → 1,66 s (−11 %), UPDATE +2 % (ruido); SQL Server DELETE 2,74 → 2,20 s (−20 %); resto ±3 %
   (SQLite UPDATE +7 % con la misma ruta y el mismo lote: ruido). DELETE MySQL/MariaDB con `chunk_size=50000`: 11,82 →
   6,82 s y 9,50 → 6,57 s (al nivel de lotes de 5000). 54 + 6 mediciones, todas correctas.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Barrido R-6 | `sweep/c{1000,5000,20000,50000}/`, `sweep/summary_b04.txt` | datos |
| Validación | `validation/auto/`, `validation/mysql_c50000/`, `validation/summary_validation.txt` | datos |
| Código | `src/util_bbdd/bulk/_support/batch_sizes.py`, `crud.py`, `parallel_loader.py`, `delete_strategies.py`, `scripts/bench_bulk.py` | completado, sin commit |

## Validación
- `ruff check` / `ruff format --check`: limpios. `mypy src tests/unit/test_protocol_conformance.py`: sin errores (388).
- `pytest`: **5843 passed / 306 skipped**. `tests/integration` (5 servidores, pyodbc): **449 passed**; con pymssql
  (`-k mssql`, bulk/dump): **67 passed**.
- `zensical build --strict`: sin avisos. `gen_arquitectura_capas.py`: dibujo sin cambios (388 ficheros).

## Impacto en API pública
- `BulkCrud(chunk_size=None)` y `ParallelBulkLoader(chunk_size=None)` por defecto (antes `5000`): cambia el lote por
  defecto en PostgreSQL (INSERT/DELETE) y SQL Server (DELETE). Mismo resultado en BD; más memoria por bloque (20 000
  filas). Nuevo `BulkCrud.batch_sizes`. `BulkCrud.chunk_size` sigue siendo un `int` (5000 o el explícito).
- Quien quiera el comportamiento anterior: `chunk_size=5000`.

## Rollback
- `git revert` del commit de B-04. Sin migración de datos. Desactivar sin revertir: `chunk_size=5000` explícito.

## Directrices para Futuras IAs
- **[bulk/lotes]**: el punto canónico del tamaño de lote es `bulk/_support/batch_sizes.py: resolve_batch_sizes`;
  `BulkCrud.chunk_size` ya no es el lote de todas las operaciones, solo el de `generar_sql` y el valor explícito.
- **[bulk/lotes]**: el UPDATE de PostgreSQL por tabla temporal empeora con lotes grandes (20 000: +31 %); no unificar el
  lote de PostgreSQL por motor.
- **[bulk/lotes]**: con `commit_every_n_chunks` el lote por defecto es 5000 en todas las operaciones: la cadencia cuenta
  lotes y cambiar el lote cambiaría cada cuántas filas se confirma (misma regla que `dump`).
- **[bulk/ejecutor]**: el `BatchStatementExecutor` recibe `max(insert, update)`; los bloques ya llegan del tamaño de su
  operación desde `crud.py` y el ejecutor no debe trocearlos más.
- **[bench]**: `scripts/bench_bulk.py --chunk-size auto` (default) mide el comportamiento por defecto de la librería; las
  líneas base anteriores a v0.25 se midieron con 5000 explícito.
- **[sesiones]**: un shell cuyo directorio de trabajo está dentro de una carpeta impide renombrarla o borrarla en
  Windows (`Device or resource busy`); salir de ella antes.

## Veredicto final
Veredicto: CLOSED (B-04 implementado y validado). El audit-code posterior (`AUDIT_CODE_fases0-2_b04.md`, RECHAZADO por A1/A2 de la Fase 1) se resolvió en `2026-10-01j-hotfix-openjson-domain`; B-04 sin hallazgos propios
Pendientes al cierre:
- Commit y, si el usuario lo pide, `/version-closure` (minor: cambia un default).
- Fase 3 del roadmap de `2026-10-01h` (spikes).
