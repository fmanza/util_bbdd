# TRACEABILITY

## Session metadata
- id: 2026-09-25-audit-code-parallel-loader-audit
- fecha: 2026-09-25
- rama: develop (base `52549e9`)
- skill: audit-code
- fase: MAP_CURRENT_STATE + MEASURE_OVERHEAD + ANALYZE_CODE + PROPOSE_OPTIMIZATIONS + VALIDATE_MULTI_DIALECT (solo lectura)

## Prompt issued
```
/audit-code Audita el componente de auditoría integrada del módulo bulk.
Scope: parallel_loader  (src\util_bbdd\bulk\_execution\parallel_loader.py)
Referencia: .github/prompts/audit_audit_manager_bulk.prompt.md
Aplica las 5 fases: MAP_CURRENT_STATE → MEASURE_OVERHEAD → ANALYZE_CODE → PROPOSE_OPTIMIZATIONS → VALIDATE_MULTI_DIALECT
Genera: audit_report_audit_manager_YYYYMMDD.md + optimization_roadmap_audit_manager.md
Puedes consultar internet para best practices en logging async y auditoría.
```

## Context supplied
- `.github/prompts/audit_audit_manager_bulk.prompt.md`
- Informe y roadmap anteriores: `.ai/sessions/2026-09-25-audit-code-audit-manager/`
- `TRACEABILITY.md` de `2026-09-25-new-feature-loader-dump-audit-policy`
- Código: `parallel_loader.py`, `persistence.py`, `crud.py` (sesión, chunks, mantenimiento), `batch.py` (commits, `fast_executemany`), `_audit/{repository,record,errors}.py`, `audit.py`
- Tests: `test_parallel_loader_audit.py`, `test_audit_deferred_session.py`, `test_parallel_loader_hoist.py`

## AI output summary
- Mapeado el flujo de la auditoría por partición: 1 fila CSV por chunk del lector, 1 apertura por partición en modo atómico y hasta 2 por commit periódico.
- Banco `bench/bench_loader_audit.py` (SQLite WAL, 4 workers, 100K y 1M filas, 4 modos). Resultados en `bench/bench_results.md`:
  - modo atómico: 0,08 %–0,22 %;
  - `commit_every_n_chunks=2`: +8 % a +9 %;
  - `commit_every_n_chunks=10`: +1,1 %.
- Reproductores `bench/repro_loader_audit.py`:
  - R1 (hueco con commits periódicos y aviso inexacto);
  - R2 (strict + reintento tras COMMIT fallido: CSV 80 frente a BD 40);
  - R3 (`fast_executemany` activado con `False`);
  - R4 (9 WARNING con la auditoría desactivada);
  - R5 (ruta inválida detectada tarde).
- 10 hallazgos, PL-1 a PL-10: 3 MEDIA (PL-2, PL-3, PL-9), 4 BAJA y 3 INFO. PL-1 se bajó a BAJA al ver que el infraconteo ya lo fija un test como limitación aceptada.
- Roadmap QW-1…QW-3, M-1…M-5, L-1 y L-2. Descartados: logging async, handle persistente, buffer compartido, tabla en BD y compresión.
- Banco multi-motor no medido: `UTIL_BBDD_BENCH_PASSWORD` no está en el entorno y no se extrajo de los contenedores. El % en servidores es una proyección.
- No se ha modificado `src/` ni `tests/`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Informe | `.ai/sessions/2026-09-25-audit-code-parallel-loader-audit/audit_report_audit_manager_20260925.md` | emitido |
| Roadmap | `.ai/sessions/2026-09-25-audit-code-parallel-loader-audit/optimization_roadmap_audit_manager.md` | emitido |
| Banco | `bench/bench_loader_audit.py` + `bench/bench_results.md` | ejecutado |
| Reproductores | `bench/repro_loader_audit.py` | ejecutado (R1–R5 confirmados) |

## Directrices para Futuras IAs
- **[bulk / medición de auditoría]**: en cargas paralelas, medir el tiempo **dentro** de `AuditCsvRepository.escribir_registros`. Con `commit_every_n_chunks`, `register_operation` puede escribir dentro, así que sus tiempos no se suman a los de la escritura.
- **[bulk / commit_every_n_chunks]**: con operaciones de 1 lote hay 2 aperturas del CSV por commit periódico (una en el hook y otra en `register_operation` fuera de transacción). No es "1 por commit".
- **[bulk / loader]**: `_resolve_table` construye una `BulkCrud` propia; cualquier opción del constructor que tenga efectos sobre el engine (hoy `enable_fast_executemany`) debe propagarse.
- **[bulk / strict]**: en strict la auditoría se escribe antes del COMMIT; un COMMIT fallido deja registros sin datos. Con reintentos, se duplican (R2).
- **[bench]**: el banco de 5 motores exige `UTIL_BBDD_BENCH_PASSWORD`; no extraerla de `docker inspect` sin permiso del usuario.

## Veredicto final
GO_CONDICIONAL: APROBADO CON CONDICIONES (QW-1; M-1 antes de recomendar strict con reintentos; texto del aviso de PL-1)
