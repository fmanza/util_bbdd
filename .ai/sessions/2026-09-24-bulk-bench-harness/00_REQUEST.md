# REQUEST

## Session metadata
- id: 2026-09-24-bulk-bench-harness
- fecha: 2026-09-24
- rama: develop
- skill: new_feature
- fase solicitada: Fase 0 del performance-audit de bulk (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)

## Solicitud original saneada
"Fase 0: montar el banco de pruebas contra los 5 motores reales"
(Fase 0 de `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` § VERSION).

## Objetivo operativo de esta sesión
- Script de benchmark de `BulkCrud` (INSERT/UPDATE/DELETE) contra Oracle, MySQL/MariaDB, PostgreSQL, SQL Server y SQLite, a 1K/10K/100K/1M filas, con línea base y variantes A/B por hallazgo.
- Tests de integración de `bulk/` por motor que se saltan sin servidor configurado.
- Forma reproducible de levantar los 5 motores en local.
- Documentación del banco en la guía existente de benchmarks.

## Restricciones explícitas
- No modificar el comportamiento de `src/util_bbdd/bulk/`.
- Sin credenciales reales en el repo.
- Motores no disponibles: se saltan sin fallar.

## Resultado esperado
- `scripts/bench_bulk.py`, `docker-compose.bench.yml`, `tests/integration/test_bulk_engines.py`, `tests/unit/test_bench_bulk_script.py`.
- `docs/guides/benchmarks.md` actualizado; `CHANGELOG.md` en `[Unreleased]`.
