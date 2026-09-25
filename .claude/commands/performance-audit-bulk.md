# /performance-audit-bulk

Auditoría sistemática de rendimiento del módulo bulk (carga masiva: INSERT/UPDATE/DELETE) con análisis de 10 áreas clave, propuestas priorizadas y benchmarking validado.

**Referencia**: `.github/agents/performance-auditor.agent.md` — Agente especializado  
**Guía completa**: `.claude/performance-audit-guide.md`

---

## Cuándo usar

- ✅ **Auditoría completa**: Necesitas análisis exhaustivo del módulo bulk (todas las áreas)
- ✅ **Enfoque específico**: Quieres optimizar batching (A1), paralelización (A2), normalización SQL (A3), etc.
- ✅ **Multi-dialect**: Soportas PostgreSQL + MySQL + Oracle + SQL Server + SQLite; necesitas recomendaciones por dialect
- ✅ **Baseline capturado**: Ya mediste rendimiento actual y quieres mejoras priorizadas
- ❌ **NO usar cuando**: Solo necesitas medir throughput actual (usa `/quick-bench`)
- ❌ **NO usar cuando**: Necesitas propuesta acotada en UN área (más tarde: `/perf-proposal A{N}`)

---

## Inputs OBLIGATORIOS

Completa TODOS antes de iniciar:

- [ ] **Objetivo de auditoría**: ¿Qué áreas optimizar? 
  - Opciones: `batching` | `paralelización` | `SQL` | `conexiones` | `auditoría` | `memoria` | `todas`
- [ ] **Baseline actual**: ¿Tienes benchmark baseline?
  - Si no: ¿ejecutar `/quick-bench` primero? (sí/no)
- [ ] **Dialects objetivo**: ¿Qué bases de datos?
  - Opciones: `PostgreSQL` | `MySQL` | `Oracle` | `SQL Server` | `SQLite` | `todas`
- [ ] **Volumen típico**: ¿Escala esperada?
  - Opciones: `pequeño (1K)` | `medio (100K)` | `grande (1M)` | `otra: [especifica]`
- [ ] **Timeline**: ¿Cuándo necesitas resultados?
  - Opciones: `ASAP (24h)` | `próxima semana` | `flexible`
- [ ] **Validación post-audit**: ¿Ejecutar benchmark post-audit?
  - Opciones: `sí` | `no`

⚠️ **VALIDACIÓN**: Si falta alguno, DETENTE y aclara antes de FASE 1. No inicies sin contexto completo.

---

## Referencia de 10 Áreas

| Área | Enfoque | Archivo(s) principal(es) |
|------|---------|-------------------------|
| **A1: Batching y lotes** | I/O bound, tamaño, bind parameters | `bulk_crud.py`, `builder.py` |
| **A2: Paralelización** | `ParallelBulkLoader`, worker count, contención | `bulk_crud.py` (parallel_insert, etc.) |
| **A3: Normalización SQL** | Escape, tipo inferencia, memory footprint | `normalizacion_sql.py` |
| **A4: Conexiones** | Reuso, pool exhaustion, transacciones largas | Connection manager (common/) |
| **A5: Auditoría integrada** | Costo por fila, logging sync/async, persistencia | `audit_manager.py` |
| **A6: Memoria** | Copy vs. vistas, deallocación, leaks | `bulk_crud.py`, `builder.py` |
| **A7: SQL generation** | Compilación dinámica, CASE, IDENTITY override | `normalizacion_sql.py` |
| **A8: DB-specific** | Oracle APPEND, MySQL LOAD DATA, PostgreSQL COPY, SQL Server BULK INSERT, SQLite WAL | Dialect handlers |
| **A9: PK sync** | Queries SELECT, cache, roundtrips | `pk_sync.py` |
| **A10: Validation** | Introspección, validación por fila, rollback cost | `bulk_crud.py` (validation) |

---

## Workflow: 4 Fases Estructuradas

### FASE 1: PLAN (1–2 hrs)
- Mapea el flujo actual: INSERT → batching → auditoría → persistencia
- Identifica teóricamente cuellos de botella por área
- Propón estrategia de benchmark (qué medir, cómo reproducir)

**Entregables**: 
- Diagrama de flujo actual
- Tabla de 10 áreas + estimación de riesgo/impacto teórico
- Estrategia de benchmark

### FASE 2: AUDIT_PLAN (1–2 hrs)
- Valida viabilidad de cada mejora propuesta
- Verifica breaking changes y compatibilidad multi-BBDD
- Define pruebas requeridas por área
- Establece orden de ejecución (dependencias)

**Entregables**:
- Matriz de viabilidad (impacto vs. esfuerzo)
- Roadmap de fases (P0 → P1 → P2)
- Riesgos y mitigation plan

### FASE 3: AUDIT_CODE (2–3 hrs)
- Revisa 10 áreas con grep_search y read_file
- Para cada hallazgo: Severidad, Archivo, Líneas, Descripción, Impacto%, Evidencia, Remediación
- Diferencia confirmado (código + benchmark) de hipótesis (requiere validación)
- Consulta internet para best practices y versiones actuales de dependencias

**Entregables**:
- Tabla de hallazgos por severidad (CRÍTICA → BAJA → INFO)
- Evidence snippets de código
- Remediación propuesta con estimación de esfuerzo

### FASE 4: VERSION (1–2 hrs)
- Emite veredicto final: CRÍTICO | SIGNIFICATIVO | MODERADO | LIMPIO
- Top 5 mejoras de mayor impacto
- Quick wins (< 1h, 5%+ mejora, sin breaking changes)
- Fases de implementación recomendadas
- Métricas de éxito (antes/después en benchmark)

**Entregables**:
- `audit_report_bulk_YYYYMMDD.md` — Informe ejecutivo + hallazgos
- `improvement_roadmap_bulk.md` — Roadmap P0/P1/P2 con timeline
- `validation_report_YYYYMMDD.md` — Benchmark comparison (si validación ejecutada)

---

## Ejemplo de invocación

```
/performance-audit-bulk

Objetivo: Auditar rendimiento del módulo bulk (carga masiva de datos)

Alcance: src/util_bbdd/bulk/ — todas las clases y funciones

Inputs requeridos:
  - Objective: paralelización + batching
  - Baseline: no (ejecutar /quick-bench primero)
  - Dialects: PostgreSQL + MySQL + SQL Server (las 3 más usadas)
  - Volumen: medio (100K registros típicos)
  - Timeline: ASAP
  - Validación: sí (post-audit con benchmark)
```

---

## Outputs generados

| Archivo | Propósito | Ubicación |
|---------|-----------|-----------|
| `audit_report_bulk_YYYYMMDD.md` | Hallazgos detallados por área y severidad | Raíz del repo o `.ai/audit/` |
| `improvement_roadmap_bulk.md` | Roadmap P0/P1/P2 con timeline estimado | Raíz del repo o `.ai/audit/` |
| `validation_report_YYYYMMDD.md` | Benchmark before/after (opcional) | Raíz del repo o `.ai/audit/` |

---

## Criterios de prioridad

| Prioridad     | Entrada                                        | Impacto | Riesgo | Quick-win? |
|---------------|------------------------------------------------|---------|--------|-----------|
| **CRÍTICA**   | > 50% slow-down, afecta TODO insert/update/del | > 50%↑  | ALTO   | ❌        |
| **ALTA**      | 20-50% slow-down, común en cargas > 100K     | 20-50%↑ | MEDIO  | ⚠️        |
| **MEDIA**     | 5-20% slow-down, depende BBDD/tamaño         | 5-20%↑  | BAJO   | ✅        |
| **BAJA**      | < 5% slow-down, edge case                     | < 5%↑   | MUY BAJO | ✅      |
| **INFO**      | Maintainability, sin impacto directo tiempo  | N/A     | NONE   | ✅        |

---

## Integración con tests y CI/CD

Una vez completada la auditoría:

1. **Validación de benchmarks**: Usa `scripts/bench_bulk.py` para medir antes/después
2. **Tests de regresión**: Asegura que cambios no degradan otros dialects
3. **PR checklist**: Incluye benchmark results en descripción de PR

---

## Troubleshooting

**P: El agente tarda mucho en FASE 3**  
R: Usa scope más acotado (p.ej. "solo batching y paralelización") o divide en 2 sesiones.

**P: ¿Puedo saltarme FASE 1 si ya conozco los cuellos de botella?**  
R: No. FASE 1 es crítica para documentar el estado actual y estrategia de medición.

**P: ¿Qué pasa si un cuello no es "confirmable" con código?**  
R: Decláralo como HIPÓTESIS y sugiere benchmark para validar antes de implementar.

---

## Checklist final

- [ ] Todos los inputs OBLIGATORIOS completados
- [ ] Agente tiene acceso a `.ai/architecture.md`, `.ai/standards.md`, `.ai/runtime.md`, `.ai/glossary.md`
- [ ] Agente puede consultar `.github/prompts/performance_audit_bulk.prompt.md`
- [ ] Si validación = sí: `scripts/bench_bulk.py` disponible y funcional
- [ ] Timeline: 4–8 hrs sesión (puede dividirse en 2 sesiones de 2–4 hrs c/u)

---

**Referencia**:  
- Agente: `.github/agents/performance-auditor.agent.md`  
- Prompt: `.github/prompts/performance_audit_bulk.prompt.md`  
- Guía usuario: `docs/PERFORMANCE_AUDIT_GUIDE.md`  
- Benchmarking: `scripts/bench_bulk.py`

*Creado: 2026-09-25*
