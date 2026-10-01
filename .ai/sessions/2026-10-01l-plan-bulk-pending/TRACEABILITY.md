# TRACEABILITY

## Session metadata
- id: 2026-10-01l-plan-bulk-pending
- fecha: 2026-10-01
- rama: develop (`e2ce535`, v0.25.1 publicada)
- skill: plan (PLAN + AUDIT_PLAN; sin IMPLEMENT)

## Prompt issued
«Hazlo, PLAN Y AUDIT-PLAN» sobre los pendientes de `bulk`: coste del filtro de OPENJSON del hotfix y Fase 3 del roadmap.

## AI output summary
- Medición de CPU del filtro de OPENJSON (1M claves): INT 0,40 s, VARCHAR 0,31 s, NUMERIC **2,06 s**; prototipo por
  columna INT 0,04 s.
- Verificado: lock de auditoría solo entre hilos (`repository.py:31`), lectores `lambda` en `range_partitioner.py` y guía,
  `py-spy` no instalado.
- `PLAN.md` (P-1, S-1…S-4) y `AUDIT_PLAN.md` (GO_CONDICIONAL; R-1…R-7; D-1…D-3).

## Ejecución (tras «Ok a todo»: D-1 biblioteca estándar, D-2 rechazos opt-in con ruta obligatoria, D-3 S-1 tras S-3)

| Punto | Resultado | Decisión | Informe |
|---|---|---|---|
| P-1 | Filtro por columna con equivalencia exacta; CPU INT 0,40 → 0,08 s/1M, VARCHAR 0,31 → 0,09, DECIMAL 2,06 → 0,40; DELETE 1M SQL Server 2,47 → 2,17 s | Implementado (`d2c49ce`) | `P-1_openjson_column_fits.md` |
| S-4 | Prefetch estable: SQL Server INSERT −10,6 %, resto −2 % a −6 % (3 repeticiones, rangos disjuntos) | GO a `prefetch_blocks` opt-in (`/new-feature`) | `S-4_prefetch.md` |
| S-3 | El modo pipeline de psycopg 3 no escala con hilos (100K: 2,66 → 5,60 s con 4); psycopg2 y PyMySQL escalan 3,6×; no es `wait_c` ni el transporte | Sin cambio en `src/`; justifica S-1 | `S-3_clientread.md` |
| S-2 | SAVEPOINT + bisección correcto en 6 motores; 10 filas malas 1,00–1,16×; 100 malas 1,8–2,8× | GO a `on_error="isolate"` opt-in (`/new-feature`) | `S-2_isolate.md` |
| S-1 | PostgreSQL: inserción 2,7× con 4 procesos frente a 4 hilos, pero el arranque (1,3–1,8 s) la anula a 1M | NO_GO por ahora; reabrir con cargas ≥ 10M/tabla | `S-1_processes.md` |

## Directrices para Futuras IAs
- **[bulk/postgresql]**: el `executemany` de psycopg 3 usa modo pipeline: muy rápido con 1 hilo, pero se degrada con
  varios hilos en el mismo proceso (S-3). No paralelizar UPDATE fila a fila de PostgreSQL con hilos.
- **[bulk/parallel]**: procesos en Windows cuestan 1,3–1,8 s de arranque cada uno; solo compensan en cargas muy grandes.
- **[bench]**: los prototipos de esta sesión parchean métodos privados de `BulkCrud` (`_BulkCrud__record_blocks`,
  `_BulkCrud__sql_blocks`); si cambian sus firmas, actualizar `s4/s4_prefetch.py`.
- **[bulk/delete mssql]**: el filtro `_fits` del hotfix A1 cuesta 2,06 s/1M con PK `DECIMAL` (quantize con contexto
  local por valor); cualquier optimización debe probar equivalencia exacta con `_fits`.
- **[bulk/parallel]**: `ParallelBulkLoader` con procesos exige lectores serializables y un lock de fichero para la
  auditoría CSV (hoy `threading.Lock`).

## Veredicto final
Veredicto: CLOSED (P-1 implementado; Fase 3 investigada: S-4 y S-2 GO a opt-in, S-3 sin cambio, S-1 NO_GO por ahora)
