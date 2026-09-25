# TRACEABILITY

## Session metadata
- id: 2026-09-25-performance-audit-dump
- fecha: 2026-09-25
- rama: develop (sobre `37cf690`)
- skill: performance-audit
- fase: FASE 1 (arquitectura) + FASE 2 (CB1–CB8) + FASE 3 (propuestas) + FASE 4 (informe + roadmap) + FASE 5 (validación). Sin IMPLEMENT: `src/` no se modifica.

## Prompt issued
```
/performance-audit
Objetivo: todas las áreas
Baseline: ejecutar /quick-bench primero
Dialects: PostgreSQL, MySQL, SQL Server, Oracle
Volumen: large
Timeline: ASAP
Validation: sí
```
Durante la sesión, el usuario pidió incluir MariaDB y SQLite (inicialmente fuera de alcance).

## Context supplied
- `.claude/commands/performance-audit.md`, `.claude/performance-audit-guide.md`, `.github/prompts/performance_audit_dump_agent.prompt.md`
- `src/util_bbdd/dump/` (orchestrator, _constraints, _indexes, _models, _sql_utils) y `src/util_bbdd/bulk/` (crud, _execution/batch, _execution/parallel_loader, normalize, _support/validation, _support/pk_sync)
- `.ai/CURRENT_STATE.md`, sesión `2026-09-23-performance-audit-bulk` (método y banco de `bulk`), `docker-compose.bench.yml`

## AI output summary
- `/quick-bench` no existe. `scripts/bench_dump.py` resultó no válido como línea base: no llama a `DumpOrchestrator` y falla por defecto (`unknown database bench_source`). Se escribió `bench/bench_dump_real.py`: `DumpOrchestrator` real, instrumentación por fase, verificación de datos y sonda de identidad, un subproceso por medición.
- Setup `large` (3,5M filas) en PostgreSQL, MySQL, MariaDB, SQL Server (pyodbc) y Oracle, en los contenedores del banco; SQLite como destino desde PostgreSQL (el origen SQLite no está soportado).
- Línea base (mediana de 3): PG 25,5 s · SQLite 25,6 · MariaDB 57,2 · MySQL 61,9 · Oracle 67,0 · SQL Server 69,0.
- Matriz de 10 variantes × 6 motores (1 repetición) + validación de las mejores combinaciones (3 repeticiones) + microbanco de lectura (`bench_read_path.py`) + coste fijo por tabla (`bench_many_tables.py`, 200 tablas en estrella y en cadena).
- 9 fallos de corrección (PD-01…PD-09), confirmados con ejecución real o reproducción aislada (psql en el esquema `zz_probe`, SQLite en memoria).
- Validación de CB1–CB8: CB1 y CB3 confirmados; CB2 moderado; CB6 como coste fijo por tabla (+ PD-08); CB4, CB5 (tablas grandes) y CB7 refutados; CB8 como palanca.
- Workaround de PD-02 verificado (`BulkCrud.sync_pk_sequences(["esquema.tabla", …])` en PG y Oracle).
- Incidencia: 2 mediciones de Oracle `arraysize` contaminadas por las tablas `zm_` de la prueba en cadena; se descartaron (fichero aparte) y se repitieron. La primera cifra de Oracle (−37 %, 1 repetición) se corrigió a la mediana (−29 %).
- Limpieza: se borraron los informes Excel generados por el banco, `__pycache__`, la carpeta `reports/` creada en la raíz y los ficheros SQLite del scratchpad. En los contenedores del banco quedan los esquemas `dump_src`/`dump_dst` (PG, SQL Server), las bases `dump_src`/`dump_dst` (MySQL/MariaDB) y los usuarios `DUMP_SRC`/`DUMP_DST` (Oracle) con los datos `large`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Solicitud | `00_REQUEST.md` | emitido |
| Informe de auditoría (PLAN, AUDIT_PLAN, AUDIT_CODE, priorización) | `audit_report_dump_20260925.md` | emitido |
| Roadmap | `improvement_roadmap_dump.md` | emitido |
| Informe de validación | `validation_report_20260925.md` | emitido |
| Banco real de `dump` | `bench/bench_dump_real.py` | completado |
| Microbanco de lectura | `bench/bench_read_path.py` | completado |
| Banco de coste fijo por tabla | `bench/bench_many_tables.py` | completado |
| Resumen de resultados | `bench/summarize.py` → `baseline/summary_large.md` | completado |
| Datos crudos | `baseline/large/`, `variants/large/`, `validation/` | completado |

## Directrices para Futuras IAs
- **[bench]**: `scripts/bench_dump.py` NO mide `dump` (simula con `pd.to_sql`) y falla por defecto. Usa `bench/bench_dump_real.py` de esta sesión (necesita `UTIL_BBDD_BENCH_PASSWORD`; con `BENCH_DUMP_SQLITE_DIR` para SQLite) hasta que se lleve a `scripts/` (roadmap 1.5).
- **[bench]**: `DumpConfig` sin `tables` vuelca TODO el esquema. No dejes tablas auxiliares (`zm_*`) en `dump_src`/`dump_dst` mientras mides el volumen `large`.
- **[bench]**: el banco de `bulk` (`scripts/bench_bulk.py::physical_name`) crea en SQL Server las columnas en MAYÚSCULAS, y eso oculta PD-01. Cualquier test o banco nuevo de mssql debe incluir columnas en minúsculas.
- **[dump]**: con `target_schema`, `_sync_pk_sequences` no hace nada (PD-02). `pk_sync_results=None` no significa «nada que sincronizar».
- **[dump/pg]**: `VALIDATE CONSTRAINT` tras `DISABLE TRIGGER ALL` no valida nada (PD-04). No lo tomes como prueba de integridad.
- **[rendimiento]**: las palancas no se suman. PG rangos + `stream_results` → +2 %; Oracle `arraysize` + solape o rangos → peor que `arraysize` solo; SQL Server `chunk_size` 20K → +57 %; MySQL/MariaDB `parallel_pk_ranges` → peor. Valida cada combinación con 3 repeticiones (ruido de una sola repetición: ±10 %).
- **[rendimiento]**: en variantes con hilos, las fases del banco se suman entre hilos. Compara solo el total.
- **[bulk]**: `reflect_table` refleja el cierre transitivo de FKs (PD-08): coste cuadrático y `RecursionError` con ~150 tablas encadenadas.

## Veredicto final
Veredicto: GO_CONDICIONAL (APROBADO CON CONDICIONES: corregir PD-01 a PD-05 y PD-08 antes de aplicar los quick wins de la Fase 1)
Pendientes al cierre:
- Abrir `/hotfix` para PD-01, PD-02, PD-03, PD-08 (prioridad) y después PD-04, PD-05, PD-06, PD-09 y PD-07.
- Implementar la Fase 1 del roadmap (Q1–Q4, Q7) con medición antes/después.
- Investigar por qué rangos + `stream_results` no se suman en PostgreSQL.
- Documento para el equipo publicado (privado hasta que se comparta): https://claude.ai/artifact/FZHNc58yRmBSiwTNr93KqH
