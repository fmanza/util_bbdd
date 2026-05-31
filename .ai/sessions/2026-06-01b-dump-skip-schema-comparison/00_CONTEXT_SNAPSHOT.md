# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.github/SHARED_INSTRUCTIONS.md` — arquitectura y reglas canónicas
- `src/util_bbdd/dump/orchestrator.py` — `DumpOrchestrator.run()` (flujo de 6 fases)
- `src/util_bbdd/comparar/comparator.py` — `SchemaComparator.compare()` (cascada N+1 documentada)
- `src/util_bbdd/bulk/crud.py` — `BulkCrud`, `reflect_table`, `bulk_insert_from_df`, `bulk_session`
- `src/util_bbdd/bulk/_execution/batch.py` — estrategias INSERT por motor
- `src/util_bbdd/dump/_models.py` — `DumpConfig`, `TableDumpResult`, `DumpResult`
- `src/util_bbdd/dump/reporters.py` — `DumpReporter.generate()` (consumidor único del `diff`)
- `.ai/sessions/2026-05-31-perf-bulk-dump/TRACEABILITY.md` y `2026-05-31-dump-performance/TRACEABILITY.md`
- `tests/unit/dump/test_orchestrator.py`, `tests/unit/dump/test_reporters.py`

## Estado actual observado
- Suite en verde antes de la sesión (subconjunto `dump` + `comparar`: 375 passed).
- El hot-path de inserción ya estaba optimizado por dos sesiones previas (2026-05-31):
  Identity Map en `reflect_table`, `bulk_session` atómico, `execute_values` (PostgreSQL),
  `fast_executemany` (SQL Server), TRUNCATE híbrido, `collect_row_counts`.
- **Ninguna sesión previa tocó la FASE 1 de comparación de esquemas del orquestador.**
- Hallazgo clave: el `diff` de `SchemaComparator().compare()` se usa en un único sitio
  (`DumpReporter._sheet_missing_columns`) y su contenido es reconstruible desde
  `TableDumpResult.skipped_columns`, ya calculado durante la carga en `_common_columns`.

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno (working tree limpio al inicio)
- Último commit: `4c85125` — fix(comparar): comparación de columnas case-insensitive cross-engine

## Clasificación metodológica
- Tipo principal: new_feature (optimización de rendimiento)
- Estado real de alcance: acotado (dump/orchestrator.py + dump/reporters.py + tests + docs)
- Consecuencia: proceder con IMPLEMENT tras confirmar enfoque con el usuario.

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes (si aplica):
- Confirmar con el usuario el enfoque (eliminar vs. flag) antes de IMPLEMENT — **resuelto: eliminar**.
