# TRACEABILITY

## Session metadata
- id: 2026-10-01q-docs-parallel-pg
- fecha: 2026-10-01
- rama: develop (base `6eb9392`, v0.26.0)
- flujo: Fase 1 (P-E) del plan `../2026-10-01p-plan-bulk-pending-2/PLAN_AUDIT_PLAN.md` (aprobado con D-1..D-5 recomendadas)

## Prompt issued
«PLAN y AUDIT-PLAN de lo pendiente» → «Si» → Fase 1 (documentación).

## AI output summary
- Al documentar que el INSERT paralelo de PostgreSQL no escala (S-1), `docs/guides/benchmarks.md` decía lo contrario
  (2,6× con 200K, medido el 2026-09-24). Se volvió a medir con la API de v0.26.0 (`bench_parallel_pg.py`,
  `bench_parallel_pg.log`; 200K y 1M, 6 motores, 2–3 repeticiones): con 4 hilos PostgreSQL 1,18× / 1,05×,
  MySQL 1,82× / 1,72×, MariaDB 1,64×, SQL Server (pyodbc) 2,76× / 2,72×, Oracle 1,16× / 1,14×, SQLite 0,87× / 0,98×.
- La diferencia con 2026-09-24 es el envío con un hilo: PostgreSQL 200K 2,65 → 0,77 s tras B-03 (tuplas) y B-04 (lotes
  de 20 000). Hallazgo nuevo: Oracle tampoco escala (causa no medida).
- Docs: tabla y notas en `docs/guides/benchmarks.md` (también la fila «Carga paralela»), `max_workers` en
  `docs/api/bulk_parallel.md`; CHANGELOG `[Unreleased]` → *Changed*.

## Validación
`zensical build --strict` sin avisos. Sin cambios de código.

## Directrices para Futuras IAs
- **[bulk/paralelo]**: las cifras de escalado de `ParallelBulkLoader` dependen del envío con un hilo; tras cambiar una
  estrategia de INSERT o el lote por defecto, volver a medir con `bench_parallel_pg.py` antes de citar la tabla.
- **[bulk/paralelo]**: PostgreSQL con psycopg 3 y Oracle no ganan con hilos (≤ 1,2×); SQL Server, MySQL y MariaDB sí.

## Veredicto final
Veredicto: CLOSED
