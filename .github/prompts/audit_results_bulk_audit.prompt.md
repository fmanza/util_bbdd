# PROMPT: Auditoría de Resultados de `/performance-audit` (Bulk)

## Objetivo

Auditar la **calidad, veracidad y utilidad** de los reportes generados por la auditoría de rendimiento
del módulo bulk: validar hallazgos, benchmarks, recomendaciones y priorización.

**Inputs**: Reportes generados
- `audit_report_bulk_YYYYMMDD.md` — Hallazgos principales
- `improvement_roadmap_bulk.md` — Roadmap de mejoras
- `validation_report_YYYYMMDD.md` — Benchmarks before/after (opcional)

**Outputs**: Auditoría de calidad con hallazgos y propuestas de corrección

---

## Contexto previo

Lee antes de auditar:

1. `.github/agents/performance-auditor.agent.md` — Definición del agente que generó reportes
2. `.github/prompts/performance_audit_bulk.prompt.md` — Guía de auditoría bulk
3. `.claude/commands/performance-audit-bulk.md` — Especificación del comando
4. `.ai/standards.md` — Criterios de calidad de reportes
5. `docs/PERFORMANCE_AUDIT_GUIDE.md` — Documentación usuario

---

## Scope de auditoría

### A. Validez de hallazgos (AUDIT_CODE)

Para cada hallazgo reportado en `audit_report_bulk_YYYYMMDD.md`:

- [ ] **Severidad justificada**: ¿Es CRÍTICA/ALTA/MEDIA/BAJA/INFO correcta?
  - ¿Se basa en estimación de impacto real (% mejora)?
  - ¿Es consistente con los umbrales definidos (CRÍTICA > 50%, ALTA 20-50%, etc.)?
  - ¿Se justifica en el texto del hallazgo?

- [ ] **Área asignada**: ¿Pertenece a una de las 10 áreas?
  - ¿La asignación es unívoca o se solapa con otra área?
  - ¿Se menciona el archivo/función específica?

- [ ] **Evidencia verificable**: ¿El hallazgo está respaldado?
  - ¿Se incluye snippet de código actual?
  - ¿Se cita una best practice o documentación oficial?
  - ¿Se diferencia entre confirmado (código + benchmark) e hipótesis?
  - ¿La evidencia es reproducible?

- [ ] **Impacto cuantificable**: ¿Se estima % de mejora realista?
  - ¿Se basa en benchmarks reales o es teórico?
  - ¿Se explica la matemática (O(N), roundtrips, etc.)?
  - ¿Se diferencia por dialect (Oracle ≠ PostgreSQL)?
  - ¿Se menciona rango (5-20%, 20-50%, etc.)?

- [ ] **Remediación viable**: ¿La propuesta de fix es práctica?
  - ¿Es implementable sin breaking changes?
  - ¿Se menciona overhead (complejidad, mantenibilidad)?
  - ¿Se especifican tests requeridos?
  - ¿Se valida compatibilidad multi-dialect?

---

### B. Calidad de benchmarks (VALIDATION)

Para `validation_report_YYYYMMDD.md` (si existe):

- [ ] **Metodología clara**: ¿Se explica cómo se midió?
  - ¿Qué herramienta se usó (timing, profiler, etc.)?
  - ¿Cuál fue el ambiente (CPU, RAM, BBDD, driver)?
  - ¿Cuántas repeticiones/iteraciones se ejecutaron?
  - ¿Hubo warmup?

- [ ] **Escala consistente**: ¿Los benchmark cubren rangos realistas?
  - ¿Se incluye 1K, 100K, 1M registros (o equivalente)?
  - ¿Se menciona volumen de datos (bytes)?
  - ¿Se especifica tamaño de fila?

- [ ] **Multi-dialect coverage**: ¿Se prueba en todas las BDD?
  - ¿Oracle, MySQL, PostgreSQL, SQL Server, SQLite?
  - ¿Se reportan diferencias por dialect?
  - ¿Se explica si alguna BBDD no es aplicable?

- [ ] **Resultados reproducibles**: ¿Se pueden reproducir los benchmarks?
  - ¿Se incluyen los datos de entrada (seeds, fixtures)?
  - ¿Se citan comandos exactos (`scripts/bench_bulk.py`)?
  - ¿Se incluye stdout/stderr del benchmark?
  - ¿Hay gráficos o tablas con números?

- [ ] **Comparación before/after clara**: ¿Se visualiza mejora?
  - ¿Se muestran valores de baseline (antes)?
  - ¿Se muestran valores propuestos (después)?
  - ¿Se calcula % mejora de forma correcta?
  - ¿Se menciona margen de error (si aplica)?

---

### C. Priorización y roadmap (IMPROVEMENT_ROADMAP)

Para `improvement_roadmap_bulk.md`:

- [ ] **Orden coherente**: ¿Las mejoras están prioridas correctamente?
  - ¿P0 (CRÍTICA) está antes que P1 (ALTA)?
  - ¿La priorización se justifica en impacto vs. esfuerzo?
  - ¿Se menciona si P0 bloquea P1?

- [ ] **Esfuerzo estimado realista**: ¿Son las estimaciones de horas viables?
  - ¿Se desglosa por tarea (implementación, tests, validación)?
  - ¿Se compara con complejidad del código?
  - ¿Se mencionan dependencias (si implementar A requiere completar B primero)?

- [ ] **Quick wins identificados**: ¿Se separaron < 1h + 5%+ mejora?
  - ¿Hay al menos 1-2 quick wins?
  - ¿Se implementan sin breaking changes?
  - ¿Se pueden hacer en paralelo o hay bloqueadores?

- [ ] **Fases bien definidas**: ¿El roadmap es un plan ejecutable?
  - ¿Sprint 1, 2, 3 tienen objetivos claros?
  - ¿Se especifican tickets/tareas por fase?
  - ¿Se menciona timeline estimado (semanas, meses)?

- [ ] **Contingency plan**: ¿Se contemplan riesgos?
  - ¿Se mencionan breaking changes y cómo mitigarlos?
  - ¿Se incluyen tests de regresión por fase?
  - ¿Hay plan B si una mejora falla en validación?

---

### D. Coherencia interna (CONSISTENCY)

- [ ] **Referencias cruzadas consistentes**: ¿Los hallazgos en audit_report se mapean a roadmap?
  - ¿Cada hallazgo CRÍTICA tiene una tarea en P0?
  - ¿Los hallazgos INFO aparecen en "nice-to-have"?

- [ ] **Terminología uniforme**: ¿Se usa lenguaje consistente?
  - ¿Las 10 áreas se nombran igual en ambos reportes?
  - ¿Los términos técnicos (batching, paralelización, etc.) están definidos?

- [ ] **Números coherentes**: ¿Las métricas son consistentes?
  - ¿% mejora de roadmap = % impacto de audit_report?
  - ¿Los hallazgos CRÍTICA suman > 50% impacto total?
  - ¿Los números son realistas (no > 100%)?

- [ ] **Alineación con contexto**: ¿Reportes reflejan scope de auditoría?
  - ¿Se auditaron todas las 10 áreas solicitadas?
  - ¿Se respetaron dialects objetivo (PostgreSQL + MySQL + Oracle)?
  - ¿Volumen auditado = volumen solicitado (1K, 100K, 1M)?

- [ ] **Completitud**: ¿No hay saltos lógicos?
  - ¿Se explica cómo pasar de hallazgo a remediación?
  - ¿Se justifica cada decisión de prioridad?
  - ¿Se documentan supuestos y limitaciones?

---

### E. Utilidad práctica (ACTIONABILITY)

- [ ] **Clarity para desarrollador**: ¿Un dev puede implementar?
  - ¿Se incluye diff conceptual o pseudocódigo?
  - ¿Se especifican funciones/métodos a cambiar?
  - ¿Se incluyen ejemplos de cómo probar?

- [ ] **Clarity para PM/Stakeholder**: ¿Se entienden trade-offs?
  - ¿Se explica en términos de negocio (throughput X, latency Y)?
  - ¿Se menciona impacto en usuarios finales?
  - ¿Se justifica por qué gastar tiempo en cada mejora?

- [ ] **Risk assessment**: ¿Se comunican riesgos claramente?
  - ¿Se menciona impacto en otras áreas (si un cambio afecta auditoría)?
  - ¿Se advierte sobre deprecations o EOL de dependencias?
  - ¿Se incluye rollback strategy?

- [ ] **Documentación de validación**: ¿Se sabe cómo confirmar mejora?
  - ¿Se indican tests unitarios a ejecutar?
  - ¿Se especifican benchmarks a rerun?
  - ¿Se explica criterio de "éxito" (threshold de mejora)?

---

## Plan de auditoría (4 fases)

### FASE 1: VALIDATE_HALLAZGOS (1–1.5 hrs)
**Responsabilidad**: Verificar integridad de cada hallazgo reportado.

**Checklist**:
1. Para cada hallazgo (CRÍTICA, ALTA, MEDIA, BAJA, INFO):
   - ✓ Severidad justificada vs. umbrales definidos
   - ✓ Área (1-10) asignada correctamente
   - ✓ Evidencia de código actual (snippet incluido)
   - ✓ Referencia a best practice o documentación oficial
   - ✓ Impacto estimado (% mejora realista)
   - ✓ Remediación viable (implementable, tested)
   - ✓ Multi-dialect considerations mencionadas

2. Diferencia hallazgos **confirmados** vs. **hipótesis**:
   - Confirmado = código actual + benchmark validan
   - Hipótesis = requiere validación previa a implementar

**Salida**: Matriz de hallazgos validados + lista de inconsistencias.

---

### FASE 2: VALIDATE_BENCHMARKS (1 hr)
**Responsabilidad**: Verificar validez y reproducibilidad de benchmarks.

**Checklist**:
1. Metodología:
   - ¿Herramienta documentada (timing, profiler)?
   - ¿Ambiente especificado (CPU, RAM, BBDD version)?
   - ¿Repeticiones y warmup mencionados?

2. Escala:
   - ¿Cubre 1K, 100K, 1M (o rango relevante)?
   - ¿Volumen de datos documentado (bytes/filas)?

3. Multi-dialect:
   - ¿Todas las BDD objetivo (Oracle, MySQL, PostgreSQL, SQL Server, SQLite)?
   - ¿Diferencias por dialect reportadas?

4. Reproducibilidad:
   - ¿Datos de entrada (seeds, fixtures) disponibles?
   - ¿Comandos exactos (`scripts/bench_bulk.py ...`)?
   - ¿Stdout/logs del benchmark incluidos?

5. Comparación:
   - ¿Baseline (antes) vs. propuesto (después)?
   - ¿% mejora calculado correctamente?
   - ¿Margen de error mencionado?

**Salida**: Hallazgos sobre confiabilidad de benchmarks.

---

### FASE 3: VALIDATE_ROADMAP (1–1.5 hrs)
**Responsabilidad**: Verificar viabilidad y coherencia del roadmap.

**Checklist**:
1. Priorización:
   - ¿Orden P0 > P1 > P2 coherente?
   - ¿Justificación (impacto vs. esfuerzo)?
   - ¿Bloqueadores identificados?

2. Esfuerzo:
   - ¿Estimaciones realistas (horas, días)?
   - ¿Desglose de tareas (implement, test, validate)?
   - ¿Comparación con LOC/complejidad del código?

3. Quick wins:
   - ¿Identificados (< 1h, 5%+ mejora)?
   - ¿Sin breaking changes?
   - ¿Parallelizable vs. secuencial?

4. Fases:
   - ¿Sprint 1, 2, 3 claramente definidas?
   - ¿Tickets/tasks agrupadas por fase?
   - ¿Timeline realista?

5. Risk mitigation:
   - ¿Breaking changes documentados?
   - ¿Tests de regresión por fase?
   - ¿Plan B si falla una mejora?

**Salida**: Hallazgos sobre viabilidad del roadmap.

---

### FASE 4: VALIDATE_COHERENCE_ACTIONABILITY (1 hr)
**Responsabilidad**: Verificar coherencia interna y utilidad práctica.

**Checklist**:
1. Referencias cruzadas:
   - ¿Hallazgos audit_report ↔ tareas roadmap?
   - ¿Severidad correlaciona con prioridad (CRÍTICA = P0)?

2. Consistencia:
   - ¿Terminología uniforme (áreas 1-10)?
   - ¿Números coherentes (% suman lógicamente)?
   - ¿Supuestos documentados?

3. Alineación:
   - ¿Se auditaron todas las 10 áreas?
   - ¿Se respetaron dialects y volumen solicitados?

4. Clarity para stakeholders:
   - ¿Dev entiende qué implementar?
   - ¿PM entiende trade-offs de negocio?

5. Completitud:
   - ¿Se explica cómo validar cada mejora?
   - ¿Criterio de "éxito" clara?
   - ¿Rollback strategy mencionada?

**Salida**: Hallazgos sobre utilidad y coherencia.

---

## Formato de hallazgo

```
### Hallazgo: [Nombre]

**Fase afectada**: [1|2|3|4 — ver arriba]
**Tipo de problema**: [Validez | Rigor | Claridad | Completitud]
**Severidad**: [CRÍTICA | ALTA | MEDIA | BAJA]
**Reporte afectado**: [audit_report_bulk | improvement_roadmap | validation_report]

**Descripción**:
[Qué es incorrecto, falta o es confuso]

**Evidencia**:
- Línea/sección del reporte donde ocurre
- Ejemplo de lo encontrado vs. lo esperado

**Impacto**:
[Cómo afecta confiabilidad/usabilidad de los resultados]

**Propuesta de corrección**:
[Cambio concreto o aclaración requerida]

**Esfuerzo**: [Trivial | Bajo | Medio]
```

---

## VERSION - Reporte final

```
## AUDIT REPORT: Resultados de `/performance-audit` (Bulk)

### Executive Summary
**Veredicto**: [CONFIABLE | MAYORMENTE_CONFIABLE | REQUIERE_VALIDACIÓN | NO_CONFIABLE]

- Hallazgos totales: [N]
- Por severidad: CRÍTICA: X | ALTA: Y | MEDIA: Z | BAJA: W
- Reporte más sólido: [audit_report | roadmap | validation]
- Reporte más débil: [audit_report | roadmap | validation]

**Recomendación**:
[Implementar hallazgos tal cual | Implementar con validación adicional |
 Revisar y revalidar antes de implementar | No proceder]

### Top 5 Hallazgos prioritarios
1. [Hallazgo + impacto en confiabilidad]
2. [Hallazgo + impacto en confiabilidad]
3. ...

### Hallazgos por reporte
#### audit_report_bulk_YYYYMMDD.md
- Total hallazgos auditados: [N]
- Hallazgos validados: [N]
- Problemas encontrados: [CRÍTICA: X, ALTA: Y, ...]
- Confiabilidad: [%]

#### improvement_roadmap_bulk.md
- Total mejoras: [N]
- P0 (CRÍTICA): [N]
- P1 (ALTA): [N]
- P2 (MEDIA): [N]
- Quick wins: [N]
- Problemas encontrados: [CRÍTICA: X, ALTA: Y, ...]
- Confiabilidad del roadmap: [%]

#### validation_report_YYYYMMDD.md (si existe)
- Metodología: [Clara | Parcial | Falta detalles]
- Reproducibilidad: [Alta | Media | Baja]
- Coverage de dialectos: [%]
- Confiabilidad de benchmarks: [%]

### Mapping audit_report → roadmap
Validar que cada hallazgo tiene correspondencia en roadmap:

| Hallazgo (audit_report) | Prioridad | Tarea (roadmap) | Status |
|---|---|---|---|
| H1 CRÍTICA ... | P0 | Tarea X | ✓ |
| H2 ALTA ... | P1 | Tarea Y | ✗ (FALTA) |
| ... | ... | ... | ... |

### Blockers y dependencies
- [Explicar si hay mejoras que bloquean a otras]
- [Validaciones requeridas antes de implementar P0]
- [Riesgos conocidos]

### Recomendaciones de acción
1. **Inmediato** (antes de implementar P0):
   - [Validación requerida]
   - [Revisión de riesgo]
   - [Benchmark adicional]

2. **Paralelo** (durante Sprint 1):
   - [Mejoras quick-win]
   - [Tests de regresión]

3. **Post-implementación**:
   - [Validación en staging]
   - [Benchmark comparison]
   - [Rollback triggers]

### Checklist de cierre
- [ ] Todos los hallazgos CRÍTICA resueltos
- [ ] Referencias cruzadas (audit_report ↔ roadmap) validadas
- [ ] Benchmarks son reproducibles
- [ ] Roadmap tiene esfuerzo realista
- [ ] Risk mitigation plan presente
- [ ] Criterios de éxito claros
```

---

## Criterios de éxito

Un reporte de auditoría bulk **auditado satisfactoriamente** debe:

1. ✅ **Validez de hallazgos**: Todos se basan en código verificable, no especulación
2. ✅ **Severidad correcta**: Umbrales (CRÍTICA > 50%, etc.) aplicados consistentemente
3. ✅ **Evidencia completa**: Snippets de código, best practices, referencias oficiales
4. ✅ **Impacto cuantificable**: % mejora realista y justificado
5. ✅ **Benchmarks reproducibles**: Metodología clara, datos disponibles, multi-dialect
6. ✅ **Roadmap viable**: Esfuerzo realista, quick wins identificados, fases claras
7. ✅ **Coherencia interna**: Hallazgos ↔ roadmap aligned, números consistentes
8. ✅ **Clarity práctica**: Dev/PM/Stakeholder entienden qué hacer
9. ✅ **Risk management**: Breaking changes, rollback, validation clara
10. ✅ **Actionability**: Cada mejora es implementable sin ambigüedad

---

## Checklist de ejecución

Antes de iniciar auditoría de resultados:

- [ ] Reporte `audit_report_bulk_YYYYMMDD.md` disponible
- [ ] Reporte `improvement_roadmap_bulk.md` disponible
- [ ] Reporte `validation_report_YYYYMMDD.md` disponible (si aplica)
- [ ] `.github/prompts/performance_audit_bulk.prompt.md` disponible como referencia
- [ ] `src/util_bbdd/bulk/` accesible para verificar hallazgos de código
- [ ] `scripts/bench_bulk.py` disponible para validar benchmarks
- [ ] `.ai/standards.md` disponible para criterios de calidad

---

## Referencias (búsquedas internet recomendadas)

Para validar información sobre optimización:

- "Python bulk database operations performance benchmarking methodology"
- "Database benchmark best practices reproducibility"
- "SQLAlchemy bulk insert performance measurement"
- "Concurrent database operations profiling tools Python"
- "Database connection pool performance impact measurement"

---

## Invocación

```markdown
Audita los resultados de la auditoría de rendimiento del módulo bulk.

Inputs:
- audit_report_bulk_YYYYMMDD.md
- improvement_roadmap_bulk.md
- validation_report_YYYYMMDD.md (si existe)

Aplica las 4 fases: VALIDATE_HALLAZGOS → VALIDATE_BENCHMARKS → VALIDATE_ROADMAP → VALIDATE_COHERENCE

Genera: audit_results_audit_report_YYYYMMDD.md
        + meta_findings_bulk_audit.md

Propósito: Validar que los hallazgos, benchmarks y roadmap son confiables antes de implementar.

Puedes consultar internet para best practices en auditoría de benchmarks y metodología.
```

---

*Creado: 2026-09-25*
*Aplicable a*: Resultados de `/performance-audit` (módulo bulk)
