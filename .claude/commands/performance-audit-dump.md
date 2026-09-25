# /performance-audit-dump

Auditoría sistemática de rendimiento del módulo dump (volcado masivo) con análisis de 8 cuellos de botella, propuestas priorizadas y benchmarking validado.

---

## Cuándo usar

- **Auditoría completa**: Necesitas análisis exhaustivo del módulo dump (todas las áreas)
- **Enfoque específico**: Quieres optimizar lectura (CB1), constraints (CB4), PK sync (CB7), indexes (CB8)
- **Multi-dialect**: Proyecto soporta PostgreSQL + MySQL + Oracle + SQL Server + SQLite; necesitas recomendaciones por dialect
- **Baseline capturado**: Ya ejecutaste `/quick-bench` y quieres propuestas priorizadas
- **NO usar cuando**: Solo necesitas medir throughput actual (usa `/quick-bench`)
- **NO usar cuando**: Necesitas propuesta acotada en UN cuello (usa `/perf-proposal CB{N}`)

---

## Inputs requeridos (OBLIGATORIO completar TODOS)

- [ ] **Objetivo de auditoría**: ¿Qué áreas optimizar? (lectura | constraints | indexes | todas)
- [ ] **Baseline actual**: ¿Tienes benchmark baseline? Si no: ¿ejecutar /quick-bench primero? (sí/no)
- [ ] **Dialects objetivo**: ¿Qué bases de datos? (PostgreSQL | MySQL | SQL Server | Oracle | SQLite | todas)
- [ ] **Volumen típico**: ¿Escala esperada? (small: 85k | medium: 850k | large: 3.5M | otra)
- [ ] **Timeline**: ¿Cuándo necesitas resultados? (ASAP | próxima semana | flexible)
- [ ] **Validación**: ¿Ejecutar benchmark post-audit? (sí/no)

**⚠️ VALIDACIÓN**: Si falta alguno, DETENTE y aclara antes de FASE 1. No inicies sin contexto completo.

---

## Referencia Completa

Usa `.claude/performance-audit-guide.md` como referencia principal para:
- Descripción de 8 cuellos (CB1–CB8)
- Interpretación de benchmarks
- Configuraciones disponibles (baseline/optimized/parallel)
- Troubleshooting

Usa `.github/prompts/performance_audit_dump_agent.prompt.md` para ver el flujo 5-fase que ejecutarás.

---

## Workflow: 5 Fases Estructuradas

### FASE 1: Análisis de Arquitectura (1–2 hrs)
Lee orchestrator.py, constraints, indexes, models. Documenta arquitectura actual.

### FASE 2: Validar 8 Cuellos de Botella (1–2 hrs)
Confirma CB1–CB8 en código con grep_search + read_file. Genera tabla resumen.

### FASE 3: Generar Propuestas Priorizadas (2–3 hrs)
Para cada cuello: impacto, esfuerzo, riesgo, priority score. Ordena P1 → P2 → P3.

### FASE 4: Informe + Roadmap (1–2 hrs)
Genera audit_report_dump_*.md + improvement_roadmap_dump.md con recomendaciones por dialect.

### FASE 5: Validación (opcional, 1–2 hrs)
Ejecuta `python scripts/bench_dump.py run --variants baseline,<variantes> --repeat 3 --out <sesión>/…` y `summarize`. Compara medianas y valida (verificación origen/destino en cada medición).

---

## Outputs

- `audit_report_dump_YYYYMMDD.md` — Informe ejecutivo + hallazgos
- `improvement_roadmap_dump.md` — Roadmap P1/P2/P3 con timeline
- `validation_report_YYYYMMDD.md` — Benchmark comparison (si FASE 5 ejecutada)

---

*Referencia: `.claude/performance-audit-guide.md` + `.github/prompts/performance_audit_dump_agent.prompt.md`*

## Referencia
- Base: `.github/prompts/performance_audit_bulk.prompt.md`
- Agente: `Performance Auditor` (`.github/agents/performance-auditor.agent.md`)
- 10 áreas: Batching, Paralelización, Normalización SQL, Conexiones, Auditoría, Memoria, SQL generation, DB-specific, PK sync, Validation
