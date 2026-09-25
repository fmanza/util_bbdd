# Performance Audit Guide for Claude Code

**Versionado**: v0.10.0  
**Propósito**: Guía de referencia para ejecutar auditorías de rendimiento del módulo `dump` usando Claude Code slash commands.

> Usa este archivo cuando necesites auditar rendimiento del módulo volcado masivo (dump) o cuando `/performance-audit-dump` sea invocado.

---

## Descripción General

El framework de auditoría de rendimiento consta de:

| Componente | Ubicación | Propósito |
|---|---|---|
| **Reference Prompt** | `.github/prompts/performance_audit_dump.prompt.md` | Análisis técnico detallado de cuellos de botella |
| **Agent Prompt** | `.github/prompts/performance_audit_dump_agent.prompt.md` | Workflow estructurado en 5 fases para agentes |
| **Benchmarking Tool** | `scripts/bench_dump.py` | CLI para medir baseline y validar mejoras |
| **User Guide** | `docs/PERFORMANCE_AUDIT_GUIDE.md` | Documentación para usuarios finales |

---

## Slash Commands en Claude Code

### `/performance-audit-dump` — Auditoría Completa de Rendimiento

**Propósito**: Ejecutar análisis exhaustivo del módulo dump, identificar cuellos de botella, proponer mejoras priorizadas y generar roadmap.

**Duración estimada**: 4–6 horas (agente trabaja de forma independiente)

**Invocación**:

```
/performance-audit-dump

Objective: Auditar rendimiento del módulo dump (volcado masivo de datos)

Scope: src/util_bbdd/dump/ — todas las clases y funciones

Focus areas (optional):
  - Chunk reading performance (fase 2)
  - Constraint management (fase 4)
  - Index rebuild efficiency (fase 5)

Validation: ejecutar bench_dump.py post-audit para validar mejoras
```

**Qué hace el agente**:
1. **FASE 1** — Lee arquitectura del módulo (orchestrator.py, _constraints.py, _indexes.py, _models.py)
2. **FASE 2** — Valida 8 cuellos de botella conocidos (CB1–CB8) mediante grep_search y lectura de código
3. **FASE 3** — Genera propuestas de mejora con matriz Impacto/Esfuerzo/Riesgo
4. **FASE 4** — Entrega informe Markdown + tabla de mejoras + roadmap por fases + métricas esperadas
5. **FASE 5** (opcional) — Ejecuta benchmark comparativo (baseline vs. optimizado)

**Salida esperada**:
- `audit_report_dump_YYYYMMDD.md` — Informe ejecutivo con hallazgos
- `improvement_roadmap_dump.md` — Roadmap priorizado con fases (quick wins → medium → long term)
- Throughput estimado + propuestas de configuración por dialect (PostgreSQL, MySQL, Oracle, SQL Server, SQLite)

**Notas**:
- Usa el prompt agent en `.github/prompts/performance_audit_dump_agent.prompt.md` como guía
- Contrasta hallazgos con `.github/prompts/performance_audit_dump.prompt.md` (reference)
- Dialect-specific: propuestas adaptadas a PostgreSQL COPY, SQL Server BULK INSERT, MySQL LOAD DATA, Oracle Direct Path, SQLite WAL

---

### `/quick-bench` — Capturar Baseline de Rendimiento Actual

**Propósito**: Ejecutar benchmarking rápido para medir throughput actual (baseline) antes de cualquier optimización.

**Duración estimada**: 15–30 minutos (ejecución del script)

**Invocación**:

```
/quick-bench

Volume: small | medium | large
  (recomendado: small para feedback rápido, large para datos realistas)

Configurations to test:
  - baseline (default actual: chunk_size=5000, parallel_pk_ranges=1)
  - (optional) optimized (propuesta: chunk_size=dynamic, parallel=1, no counting)

Database: SQLite in-memory (default) o especificar URL

Output: JSON + resumen en console
```

**Qué hace Claude Code**:
1. Ejecuta `python scripts/bench_dump.py --config baseline --volume {size} --iterations 3`
2. Captura JSON con métricas (min/max/avg seconds, throughput rows/sec)
3. Genera resumen con interpretación
4. Opcional: compara baseline vs. optimized si ambas configs se especifican

**Salida esperada**:
```
✅ Baseline Results (small):
   Throughput: 12,500 rows/sec (avg)
   Min: 3.2s | Max: 3.8s | Avg: 3.5s
   Total: 85k rows
   
Interpretación: rendimiento actual moderado; buscar optimizaciones en
  lectura de chunks (CB1) y sincronización de PKs (CB7)
```

**Notas**:
- Guardar resultados en `bench_results/baseline_YYYYMMDD.json` para comparar post-mejora
- Recomendado ejecutar 3+ iteraciones para promediar variaciones de SO

---

### `/perf-proposal` — Generar Propuestas de Mejora Específica

**Propósito**: Enfocarse en un cuello de botella específico (CB1–CB8) y generar propuesta de implementación acotada.

**Duración estimada**: 1–2 horas

**Invocación**:

```
/perf-proposal

Bottleneck: CB1 | CB2 | CB3 | CB4 | CB5 | CB6 | CB7 | CB8
  
  CB1: lectura lenta de chunks (pd.read_sql)
  CB2: transformación overhead (dtype casting, memoria)
  CB3: SQLAlchemy overhead (reflection, table introspection)
  CB4: constraint sync N+1 (disable/enable one by one)
  CB5: collect_row_counts overhead (COUNT(*) por tabla)
  CB6: introspection cache ineficiente
  CB7: PK sync serialización (no parallelization)
  CB8: index rebuild bottleneck (estrategia actual)

Estimated impact: P1 (quick win, <20% esfuerzo) | P2 (medium) | P3 (large, >40% esfuerzo)
```

**Qué hace Claude Code**:
1. Lee referencia de cuello específico en `.github/prompts/performance_audit_dump.prompt.md`
2. Analiza ubicación en código (grep_search + read_file)
3. Propone fix con:
   - Descripción del cambio
   - Código de ejemplo
   - Tests para validar no rompe funcionalidad
   - Impacto estimado en throughput

**Salida esperada**:
- `proposal_CB{N}_dump.md` — Descripción técnica
- Código sugerido (inline en Markdown con bloques ```python)
- PR mockup con commit message sugerido

**Notas**:
- Usar cuando hay consenso en qué optimizar
- Útil para P1 (quick wins) antes de auditoría completa

---

### `/perf-validate` — Validar Mejora Post-Implementación

**Propósito**: Ejecutar benchmark post-mejora, comparar vs. baseline, generar informe de validación.

**Duración estimada**: 30–60 minutos

**Invocación**:

```
/perf-validate

Optimization: [describe qué se optimizó, e.g., "disable constraints in batch"]

Baseline result: [ruta o resultados JSON previos]
  (Si no especificas, busca en bench_results/baseline_YYYYMMDD.json)

Configuration: optimized | custom
  (custom: especificar chunk_size, parallel_pk_ranges, etc.)

Volume: small | medium | large
```

**Qué hace Claude Code**:
1. Ejecuta benchmark con configuración post-mejora
2. Compara min/max/avg vs. baseline
3. Calcula % de mejora (throughput gain)
4. Genera reporte de validación con:
   - Métricas antes/después
   - % de mejora observada vs. estimada
   - Riesgos o regresos detectados
   - Recomendación: ✅ APROBADO | ⚠️ REVISAR | ❌ RECHAZAR

**Salida esperada**:
```
📊 Validation Report: CB7 - PK Sync Parallelization

Baseline (3.5s avg) → Optimized (2.8s avg)
Improvement: +25% throughput (3,570 → 4,464 rows/sec)
Estimated: +20% → Actual: +25% ✓ (ahead of estimate)

Status: ✅ APROBADO
  - Throughput mejora confirmada
  - No hay regresos en constraint handling
  - Tests pasan sin cambios

Recomendación: Integrar a main branch
```

**Notas**:
- Guardar reporte en `bench_results/validation_CB{N}_YYYYMMDD.md`
- Usar para aprobar/rechazar propuestas antes de mergear PR

---

## Workflow Recomendado: Auditoría Completa

### Fase 0: Preparar Baseline (30 mins)

```
/quick-bench

Volume: small
Configurations: baseline
Database: SQLite (default)
```

→ Captura baseline actual en `bench_results/baseline_20260925.json`

---

### Fase 1: Ejecutar Auditoría Completa (4–6 hrs)

```
/performance-audit-dump

Objective: Auditar módulo dump completo
Focus areas: todas (lectura, constraints, indexes)
Validation: true
```

→ Genera informe + roadmap + propuestas priorizadas

---

### Fase 2: Implementar Quick Wins (1–2 hrs por P1)

Para cada propuesta P1 en roadmap:

```
/perf-proposal

Bottleneck: CB{N}
Estimated impact: P1
```

→ Genera propuesta acotada, implementar y testear

---

### Fase 3: Validar Mejora (30–60 mins)

```
/perf-validate

Optimization: "constraint batching + dynamic chunk sizing"
Baseline result: bench_results/baseline_20260925.json
Configuration: optimized
Volume: small
```

→ Confirma mejora vs. baseline, genera reporte de validación

---

### Fase 4: Iterar P2 y P3 (según roadmap)

Repetir Fases 2–3 para propuestas de impacto medio y largo plazo

---

## Configuraciones Disponibles en `bench_dump.py`

| Config | chunk_size | parallel_pk_ranges | collect_row_counts | Use Case |
|---|---|---|---|---|
| **baseline** | 5000 | 1 | True | Rendimiento actual (default) |
| **optimized** | dynamic (recomendado 20k) | 1 | False | Después de optimizaciones simples |
| **parallel** | 10000 | CPU_COUNT | False | Máximo throughput con paralelización |

---

## Perfiles de Volumen

| Perfil | Customers | Orders | Order_Items | Total Rows | Tiempo Est. |
|---|---|---|---|---|---|
| **small** | 10k | 25k | 50k | 85k | 3–5s (baseline) |
| **medium** | 100k | 250k | 500k | 850k | 30–60s |
| **large** | 500k | 1M | 2M | 3.5M | 3–8 mins |

→ Usa **small** para iteración rápida, **large** para validar en escala realista

---

## Interpretación de Resultados

### Throughput

```
Rows per second = Total Rows / Avg Time (seconds)
```

**Benchmark típicos**:
- SQLite (in-memory): 10k–20k rows/sec
- PostgreSQL: 5k–15k rows/sec (depende de dialecto + constraints)
- SQL Server: 3k–10k rows/sec (depende de BULK INSERT config)
- MySQL: 5k–12k rows/sec

**Objetivos de mejora**:
- +20%: Viable con optimizaciones simples (CB1, CB5)
- +40%: Requiere paralelización (CB7, batch constraints)
- +60%+: Paralelización + dialect-specific (COPY, BULK INSERT)

### Comparación Baseline vs. Optimized

```
% Improvement = ((Optimized - Baseline) / Baseline) × 100
```

**Criterios de aprobación**:
- ≥ 90% de mejora estimada: ✅ APROBADO
- 75–90% de mejora estimada: ⚠️ REVISAR (aceptable si <2% de regresión)
- < 75% de mejora estimada: ❌ RECHAZAR (revisar cambios)

---

## Integración con GitHub Roadmap

Después de auditoría, crear issues con template:

**Issue Title**: `[PERF] CB{N}: {descripción cuello}`  
**Labels**: `performance`, `dump`, `P{1/2/3}`, `optimization`

**Body**:
```markdown
## Problem
[Descripción cuello de botella]

## Proposed Solution
[Descripción de la propuesta]

## Impact
- Estimated throughput gain: +{X}%
- Estimated effort: {X} hours
- Risk level: {Low/Medium/High}

## Acceptance Criteria
- [ ] Benchmark: baseline → optimized validates improvement
- [ ] All tests pass
- [ ] No regressions in other bottlenecks
- [ ] Dialects: PostgreSQL, MySQL, SQL Server passing

## Reference
[Link a audit report o proposal doc]
```

---

## Notas Importantes

### Determinismo en Benchmarks

- Ejecutar múltiples iteraciones (≥3) para promediar variaciones del SO
- Usar SQLite in-memory (default) para consistencia reproducible
- Aislar máquina: cerrar otras apps que consuman recursos durante benchmark
- Seed aleatorio (si aplica en generador de datos): fijar seed para reproducibilidad

### Multi-Dialect Considerations

Propuestas de mejora pueden aplicar diferentemente:

| Mejora | PostgreSQL | MySQL | SQL Server | Oracle | SQLite |
|---|---|---|---|---|---|
| Constraint batching | ✅ Muy recomendado | ✅ Recomendado | ✅ Crítico | ✅ Crítico | ⚠️ Mínimo impacto |
| Dynamic chunk sizing | ✅ +15% | ✅ +12% | ✅ +10% | ✅ +18% | ✅ +8% |
| PK sync parallelization | ✅ +25% | ✅ +20% | ⚠️ +5% | ✅ +22% | ❌ No aplica |
| Index rebuild strategy | ✅ REINDEX online | ⚠️ Rebuild serial | ✅ REBUILD ONLINE | ✅ REBUILD PARALLEL | ⚠️ Rebuild simple |

→ Validar propuestas con dialects relevantes antes de mergear

---

## Troubleshooting

### Benchmark no ejecuta o falla

```bash
# Verifica que DumpOrchestrator está disponible
python -c "from util_bbdd.dump import DumpOrchestrator; print('OK')"

# Verifica dependencias (pandas, sqlalchemy, psycopg2, pymysql, pyodbc, cx_Oracle)
pip install pandas sqlalchemy psycopg2 pymysql pyodbc

# Ejecuta en modo verbose para debug
python scripts/bench_dump.py --config baseline --volume small --verbose
```

### Resultados inconsistentes

- Cierra otras aplicaciones (navegador, IDE compilando, etc.)
- Aumenta `--iterations 5` (en lugar de default 3)
- Usa base de datos en SSD, no en carpeta compartida
- En Windows, desactiva antivirus durante benchmark

### Audit no termina o se demora mucho

- Reduce a `--volume small` para feedback rápido
- Especifica solo bottlenecks críticos en `/perf-proposal`
- Paralleliza: ejecutar múltiples `/perf-proposal` en paralelo (CB1 + CB5 simultáneamente)

---

## Referencias

- **Reference Prompt**: `.github/prompts/performance_audit_dump.prompt.md`
- **Agent Prompt**: `.github/prompts/performance_audit_dump_agent.prompt.md`
- **Benchmarking Tool**: `scripts/bench_dump.py`
- **User Guide**: `docs/PERFORMANCE_AUDIT_GUIDE.md`
- **Module Source**: `src/util_bbdd/dump/`

---

*Última actualización: 2026-09-25*
