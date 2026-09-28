# /performance-audit-bulk

Auditoría de rendimiento del módulo `bulk` (carga masiva: INSERT/UPDATE/DELETE) en 10 áreas, con
impacto % estimado y validación con benchmark. Solo lectura: no implementa mejoras.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/performance_audit_bulk.prompt.md` — inputs, áreas, entregables y reglas (contrato de salida)
2. `.github/agents/performance-auditor.agent.md` — rol, 10 áreas, criterios de prioridad y formato de hallazgo
3. `.ai/architecture.md`, `.ai/standards.md`, `.ai/runtime.md` y `.ai/glossary.md`

## Reglas de ejecución

- Si falta algún input del prompt, decláralo como supuesto explícito antes de la fase PLAN.
- Medición: `scripts/bench_bulk.py` (`--list-variants` para ver variantes; banco en `.ai/runtime.md`).
- Puedes consultar internet para best practices y benchmarks; cita la fuente.
- Entregables en la carpeta de la sesión (`.ai/sessions/<fecha>-<slug>/`): `audit_report_bulk_YYYYMMDD.md`,
  `improvement_roadmap_bulk.md` y, si hay validación, `validation_report_YYYYMMDD.md`.
- Las mejoras se implementan después, una por una, con `/refactor`, `/new-feature` o `/hotfix` (commit `perf:`).

## Ejemplo de entrada

```text
/performance-audit-bulk

Objetivo: paralelización + batching
Baseline: no (ejecutar benchmark primero)
Dialects: PostgreSQL + MySQL + SQL Server
Volumen: 100K registros
Timeline: ASAP
Validación: sí
```
