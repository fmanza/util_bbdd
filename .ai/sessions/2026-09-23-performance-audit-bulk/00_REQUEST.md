# REQUEST

## Session metadata
- id: 2026-09-23-performance-audit-bulk
- fecha: 2026-09-23
- rama: develop
- skill: performance-audit
- fase solicitada: PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION (solo análisis, sin IMPLEMENT)

## Solicitud original saneada
```
/performance-audit

Módulo: src/util_bbdd/bulk/
Operaciones: Todas (INSERT, UPDATE, DELETE)
Escala de datos: Benchmarks con 1K, 10K, 100K, 1M registros
Motores: Oracle, MySQL, PostgreSQL, SQL Server, SQLite
Restricciones: Mantener compatibilidad multi-BBDD y auditoría integrada
Alcance: Análisis + propuestas de remediación + quick wins
```

## Objetivo operativo de esta sesión
- Mapear el flujo de carga de `bulk/` (INSERT/UPDATE/DELETE) y medir el coste por fase a 1K–1M filas.
- Identificar cuellos de botella en las 10 áreas de `.github/prompts/performance_audit_bulk.prompt.md`,
  distinguiendo CONFIRMADO de HIPÓTESIS.
- Proponer remediaciones compatibles multi-BBDD que no alteren la auditoría integrada.
- Emitir veredicto final, quick wins y fases de implementación.

## Restricciones explícitas
- Mantener compatibilidad multi-BBDD (Oracle, MySQL/MariaDB, PostgreSQL, SQL Server, SQLite).
- Mantener la auditoría integrada (contrato del CSV de `AuditManager`).
- Solo análisis: no editar código de `src/` en esta sesión.
- Métricas base no aportadas por el usuario → se generan en la propia sesión (supuesto declarado).

## Resultado esperado
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` con PLAN, AUDIT_PLAN, AUDIT_CODE y VERSION.
- Scripts de benchmark reproducibles en `bench/`.
- `TRACEABILITY.md` y entrada en `INDEX.md` / `SESSIONS_DIGEST.md`.
