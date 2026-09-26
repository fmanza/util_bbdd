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

> Solo `/performance-audit-dump` existe como slash command. `/perf-proposal` y `/perf-validate` describen
> pasos del flujo que se piden en lenguaje natural; la medición se hace siempre con `scripts/bench_dump.py`.

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

### Capturar la línea base (sin slash command)

`/quick-bench` no existe como comando: la línea base se captura con el banco.

```bash
python scripts/bench_dump.py setup --engines postgresql,mysql,mariadb,mssql,oracle --volume large
python scripts/bench_dump.py run --engines postgresql,mysql,mariadb,mssql,oracle,sqlite --variants baseline     --volume large --repeat 3 --out .ai/sessions/<sesión>/baseline
python scripts/bench_dump.py summarize .ai/sessions/<sesión>/baseline/results.jsonl
```

Cada medición registra el total, las fases, la memoria pico y la verificación origen/destino (ver
`docs/PERFORMANCE_AUDIT_GUIDE.md` § «Uso del banco de rendimiento»).

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

```bash
python scripts/bench_dump.py run --engines <motores> --variants baseline --volume large --repeat 3     --out .ai/sessions/<sesión>/baseline
```

→ Deja la línea base en `.ai/sessions/<sesión>/baseline/results.jsonl` (ver «Capturar la línea base»)

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

## Variantes disponibles en `bench_dump.py`

`python scripts/bench_dump.py list` muestra todas con su configuración exacta. Las principales:

| Variante | Qué cambia frente a `DumpConfig` por defecto |
|---|---|
| `baseline` | Nada (`chunk_size=5000`, sin paralelismo, con conteos) |
| `audit`, `audit_history` | Auditoría de `bulk` activa (CSV nuevo / CSV con historial previo) |
| `stream`, `arraysize`, `chunk20k` | Cursor de servidor y `arraysize=5000` en el engine (ya los aplica `dump` desde Q2/Q1), lotes de 20K. El solape lectura/escritura (Q3) está en `dump`, no es una variante |
| `ranges4`, `ranges8`, `indexes`, `nocheck`, `redump` | Rangos de PK, `manage_indexes`, sin revalidar constraints, volcado repetido |
| `combo*`, `best_pg`, `stream_c20k`, `arraysize_ranges4` | Combinaciones de la auditoría de 2026-09-25 |

---

## Perfiles de Volumen

| Perfil | Customers | Orders | Order_Items | Total Rows | Línea base medida (2026-09-25) |
|---|---|---|---|---|---|
| **tiny** | 1k | 2,5k | 5k | 8,5k | — (prueba de humo) |
| **small** | 10k | 25k | 50k | 85k | — |
| **medium** | 100k | 250k | 500k | 850k | — |
| **large** | 500k | 1M | 2M | 3.5M | PG 25,5 s · SQLite 25,6 · MariaDB 57,2 · MySQL 61,9 · Oracle 67,0 · SQL Server 69,0 |

→ Usa **tiny** para comprobar que el banco funciona y **large** para medir (con volúmenes pequeños pesan más los costes fijos por tabla).

---

## Interpretación de Resultados

### Throughput

```
Rows per second = Total Rows / Avg Time (seconds)
```

**Línea base medida** (large, 3,5M filas, contenedores locales, mediana de 3; `.ai/sessions/2026-09-25-performance-audit-dump/`):
- PostgreSQL ≈ 137k filas/s · SQLite (desde PG) ≈ 137k · MariaDB ≈ 61k · MySQL ≈ 57k · Oracle ≈ 52k · SQL Server ≈ 51k


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

- Ejecutar ≥ 3 repeticiones (`--repeat 3`) y comparar medianas (`summarize`)
- Los datos se generan en el servidor de forma determinista (sin aleatoriedad) y el destino se recrea antes de cada medición
- Aislar máquina: cerrar otras apps que consuman recursos durante benchmark

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
# ¿Contenedores levantados y contraseña definida?
docker compose -f docker-compose.bench.yml ps
python -c "import os; print(bool(os.environ.get('UTIL_BBDD_BENCH_PASSWORD')))"

# Una medición suelta, con la traza completa en la salida JSON (campos exception/traceback)
python scripts/bench_dump.py setup --engines postgresql --volume tiny
python scripts/bench_dump.py one --engine postgresql --variant baseline --volume tiny
```

- `unknown database`/`schema does not exist`: falta `setup` para ese motor.
- SQL Server: pyodbc y *ODBC Driver 18 for SQL Server*. Oracle: `oracledb` (thin).

### Resultados inconsistentes

- Usa `--repeat 3` y la mediana de `summarize` (el ruido de una sola repetición llegó a ±10 %).
- No dejes tablas ajenas en `dump_src`/`dump_dst`: `DumpConfig` sin `tables` vuelca todo el esquema.
- Cierra otras cargas pesadas del equipo (compilaciones, otros contenedores) durante la medición.

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
