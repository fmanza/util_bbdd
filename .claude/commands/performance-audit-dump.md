# /performance-audit-dump

Auditoría de rendimiento del módulo `dump` (volcado masivo entre esquemas y motores): 8 cuellos de
botella (CB1–CB8), propuestas priorizadas y validación con benchmark. Solo lectura: no implementa mejoras.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/performance_audit_dump.prompt.md` — inputs, contexto del módulo, alcance y entregables (contrato de salida)
2. `.github/prompts/performance_audit_dump_agent.prompt.md` — flujo operativo en 5 fases
3. `.github/agents/performance-auditor.agent.md` — rol y criterios de prioridad
4. `.claude/performance-audit-guide.md` — cuellos CB1–CB8, variantes del banco e interpretación

## Reglas de ejecución

- **⚠️ VALIDACIÓN**: si falta algún input del prompt, DETENTE y aclara antes de la fase 1.
- Medición: `python scripts/bench_dump.py run --engines <motores> --variants baseline,<variantes> --volume <volumen> --repeat 3 --out <sesión>/…`
  y `python scripts/bench_dump.py summarize <sesión>/…/results.jsonl` (verificación origen/destino en cada medición).
- Entregables en la carpeta de la sesión: `audit_report_dump_YYYYMMDD.md`, `improvement_roadmap_dump.md` y,
  si hay fase 5, `validation_report_YYYYMMDD.md`.
- Las mejoras se implementan después con `/refactor`, `/new-feature` o `/hotfix` (commit `perf:`).

## Ejemplo de entrada

```text
/performance-audit-dump

Objetivo: lectura + constraints
Baseline: no (capturarlo primero con scripts/bench_dump.py)
Dialects: PostgreSQL + SQL Server
Volumen: medium (850k)
Timeline: próxima semana
Validación: sí
```
