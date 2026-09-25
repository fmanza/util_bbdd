# REQUEST

## Session metadata
- id: 2026-09-25-performance-audit-bulk-sql
- fecha: 2026-09-25
- rama: develop
- skill: performance-audit-bulk (→ refactor para la implementación)
- fase solicitada: PLAN y AUDIT_PLAN del roadmap de serialización SQL

## Solicitud original saneada
1. `/performance-audit-bulk` — Mejorar los tiempos de serialización de los ficheros SQL. Scope: `src/util_bbdd/bulk/`.
   Fases MAP_CURRENT_STATE → MEASURE_OVERHEAD → ANALYZE_CODE → PROPOSE_OPTIMIZATIONS → VALIDATE_MULTI_DIALECT.
   Inputs aclarados: 5 dialectos, 1M filas, baseline + validación, salida en `.ai/audit/*_bulk_sql_serialization*`.
2. "PLAN y AUDIT_PLAN".

## Objetivo operativo de esta sesión
- Plan de implementación de P0 + P1 del roadmap (P-33, P-31, P-32) con cambios, tests y criterios verificables.
- AUDIT_PLAN: viabilidad, riesgos y supuestos verificados contra el código y SQLAlchemy 2.0.50.

## Restricciones explícitas
- Sin IMPLEMENT en esta fase.
- P1 debe producir SQL byte-idéntico al actual en los 5 dialectos.

## Resultado esperado
- `PLAN.md`, `AUDIT_PLAN.md`, `TRACEABILITY.md` en esta carpeta.
- Informes de la auditoría en `.ai/audit/` (ya emitidos).
