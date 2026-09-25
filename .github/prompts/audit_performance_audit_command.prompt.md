# PROMPT: Auditoría de Comando `/performance-audit`

## Objetivo

Auditar la **calidad, completitud e información** del comando `/performance-audit` documentado en
`.claude/commands/performance-audit-bulk.md`. Identificar gaps, oportunidades de mejora de rendimiento
en la documentación y proponer enhancements en la presentación y utilidad del comando.

---

## Scope de auditoría

### A. Estructura y navegabilidad
- [ ] ¿Está claro **cuándo usar** el comando vs. alternativas (p.ej. `/quick-bench`, `/perf-proposal`)?
- [ ] ¿Los inputs OBLIGATORIOS están completos y validados?
- [ ] ¿El workflow de 4 fases (PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION) está claramente definido?
- [ ] ¿Existen ejemplos reales de invocación?

### B. Completitud de información
- [ ] ¿Se explica cada una de las 10 áreas de auditoría? ¿Son suficientes los detalles?
- [ ] ¿Se incluyen referencias a archivos y funciones exactas del módulo `bulk/`?
- [ ] ¿Los criterios de prioridad (CRÍTICA, ALTA, MEDIA, BAJA, INFO) están justificados?
- [ ] ¿Se describe cómo validar hallazgos (benchmarks, tests)?
- [ ] ¿Hay guía de troubleshooting para problemas comunes?

### C. Optimización del rendimiento (información)
- [ ] ¿Se explica clara y concisamente **por qué cada área impacta rendimiento**?
- [ ] ¿Se incluyen estimaciones de impacto (% mejora esperada)?
- [ ] ¿Se referencian best practices y documentación oficial?
- [ ] ¿Se detalla el overhead de cada remediación propuesta?
- [ ] ¿Se diferencian hipótesis de confirmaciones basadas en código?

### D. Propuestas de mejora
- [ ] **Información faltante**: ¿Qué datos, ejemplos o referencias debería incluir?
- [ ] **Claridad**: ¿Qué secciones son confusas o ambiguas?
- [ ] **Usabilidad**: ¿Cómo podría mejorar el flujo de invocación?
- [ ] **Ejemplos**: ¿Se necesitan más casos de uso concretos?
- [ ] **Integración**: ¿Cómo conecta con otros comandos y agentes?

---

## Plan de auditoría (4 fases)

### FASE 1: AUDIT_STRUCTURE (0.5 hrs)
**Responsabilidad**: Revisar estructura, navegabilidad y completitud de índices.

**Checklist**:
1. ¿El encabezado (`#` y `##`) sigue la jerarquía Markdown estándar?
2. ¿Cada sección principal tiene un propósito claro?
3. ¿Existe tabla de contenidos (TOC) o es fácil navegar?
4. ¿Los links internos (`.github/`, `.claude/`, `.ai/`) son correctos y relativos?
5. ¿Las tablas son legibles y bien formateadas?

**Salida**: Lista de hallazgos estructurales + recomendaciones de formato.

---

### FASE 2: AUDIT_COMPLETENESS (1–1.5 hrs)
**Responsabilidad**: Validar completitud de información vs. necesidades de usuario final.

**Checklist**:
1. ¿Los 10 inputs OBLIGATORIOS cubren **todos** los parámetros necesarios?
   - ¿Qué inputs podrían ser opcionales?
   - ¿Qué inputs adicionales faltan?

2. ¿Las 10 áreas de auditoría están suficientemente documentadas?
   - ¿Se explica cómo cada área se mide/valida?
   - ¿Se incluyen ejemplos de hallazgos típicos?

3. ¿Los outputs generados (`audit_report_bulk_*.md`, etc.) están bien definidos?
   - ¿Qué incluye cada archivo?
   - ¿Cuál es el formato esperado?

4. ¿Se describe el criterio de prioridad de forma clara y defensible?
   - ¿Cuál es la fuente de estos umbrales (% mejora)?
   - ¿Son realistas para módulo bulk?

5. ¿Hay guía para interpretar resultados?
   - ¿Cómo sabe el usuario qué hacer con los hallazgos?
   - ¿Hay ejemplos de decisión (implementar P0, postergar P2)?

**Salida**: Tabla de gaps + sugerencias de contenido faltante + prioridades.

---

### FASE 3: AUDIT_PERFORMANCE_INFO (1–1.5 hrs)
**Responsabilidad**: Evaluar calidad de la información sobre optimización de rendimiento.

**Checklist**:
1. **Claridad causal**: Para cada una de las 10 áreas, ¿se explica claramente **por qué** afecta rendimiento?
   - Ejemplo: "A1 Batching afecta porque reduce roundtrips (SQL: 1 query = N inserts vs. N queries = N inserts)"
   - ¿Se incluye matemática simple (O(N) vs. O(1))?

2. **Estimaciones de impacto**:
   - ¿Se dan rangos realistas (5-20%, 20-50%, etc.)?
   - ¿Se basan en benchmarks conocidos o son hipótesis?
   - ¿Se diferencia claramente?

3. **Best practices**:
   - ¿Se referencian guías oficiales (SQLAlchemy, Pandas, documentación de BBDD)?
   - ¿Los ejemplos están basados en código real del repositorio?
   - ¿Se incluyen links a documentación externa verificable?

4. **Trade-offs**:
   - ¿Se menciona el overhead de implementación (complejidad, mantenibilidad)?
   - ¿Se considera impacto multi-dialect (¿funciona igual en Oracle, MySQL, PostgreSQL)?
   - ¿Se documenta riesgo de breaking changes?

5. **Validación**:
   - ¿Se explica claramente cómo **confirmar** un hallazgo?
   - ¿Se diferencia entre "código suena lento" y "benchmark prueba es lento"?
   - ¿Se incluye estrategia de benchmark (tools, tamaños, repeticiones)?

**Salida**: Hallazgos sobre claridad de información de rendimiento + propuestas de mejora.

---

### FASE 4: AUDIT_USABILITY (0.5–1 hr)
**Responsabilidad**: Evaluar experiencia de usuario al usar el comando.

**Checklist**:
1. **Invocación**:
   - ¿Es clara la sintaxis del comando (`/performance-audit`)?
   - ¿El ejemplo de invocación es realista y fácil de copiar?
   - ¿Se explica qué esperar como salida?

2. **Integración con otros comandos**:
   - ¿Se menciona `/quick-bench` como alternativa?
   - ¿Se explica cuándo usar `/performance-audit` vs. `/quick-bench` vs. `/perf-proposal A{N}`?
   - ¿Se integra con `/new-feature`, `/refactor`, etc.?

3. **Troubleshooting**:
   - ¿Se responden preguntas típicas?
   - ¿Se documentan errores comunes y soluciones?
   - ¿Se advierte sobre limitaciones?

4. **Documentación conexa**:
   - ¿Se referencian correctamente `.github/agents/performance-auditor.agent.md`?
   - ¿¿Se apunta a `.github/prompts/performance_audit_bulk.prompt.md`?
   - ¿Se menciona `scripts/bench_bulk.py`?
   - ¿¿Se enlaza a `docs/PERFORMANCE_AUDIT_GUIDE.md`?

5. **Claridad narrativa**:
   - ¿Un usuario sin contexto entiende de qué trata?
   - ¿El tono es consistente (técnico pero accesible)?
   - ¿La longitud es proporcional (no demasiado largo, no demasiado breve)?

**Salida**: Recomendaciones de UX y propuestas de clarificación.

---

## Formato de hallazgo

Para cada hallazgo identificado:

```
### Hallazgo: [Nombre breve]

**Área de auditoría**: [A|B|C|D — ver scope arriba]
**Severidad**: [CRÍTICA | ALTA | MEDIA | BAJA | INFO]
**Sección afectada**: [Ruta en el documento, p.ej. "## Inputs OBLIGATORIOS"]

**Descripción del problema**:
[Qué está faltando, es confuso, o podría mejorarse]

**Impacto**:
[Cómo afecta la experiencia del usuario o calidad de la información]

**Propuesta de mejora**:
- [Cambio concreto sugerido]
- [Adicional si aplica]

**Referencia**:
[Link a SHARED_INSTRUCTIONS.md, documentación, o best practice]

**Esfuerzo estimado**:
[Trivial | Bajo | Medio | Alto]
```

---

## Version - Reporte final

### Estructura del reporte

```
## AUDIT REPORT: `/performance-audit` Command

### Executive Summary
- Veredicto general: [COMPLETO | MAYORÍA_GAPS | GAPS_CRÍTICOS | REQUIERE_REWRITE]
- Hallazgos totales: [N]
- Severidad: [CRÍTICA: X | ALTA: Y | MEDIA: Z | BAJA: W | INFO: V]
- Recomendación: [Implementar mejoras antes de publicación | Publicar con notas | Completar y revisar]

### Top 5 Mejoras prioritarias
1. [Hallazgo + impacto]
2. [Hallazgo + impacto]
3. ...

### Roadmap de implementación
- **Sprint 1 (CRÍTICA + ALTA)**: Cambios prioritarios [lista]
- **Sprint 2 (MEDIA + BAJA)**: Enhancements [lista]
- **Sprint 3 (INFO + Polish)**: Mejoras menores y ejemplos [lista]

### Quick wins (< 1h, alto valor)
- [Mejora + razón]
- ...

### Dependencias y referencias
- Agente relacionado: `.github/agents/performance-auditor.agent.md`
- Prompt base: `.github/prompts/performance_audit_bulk.prompt.md`
- Guía usuario: `docs/PERFORMANCE_AUDIT_GUIDE.md`
- Validador: `scripts/bench_bulk.py`

### Checklist de cierre
- [ ] Todos los hallazgos CRÍTICA resueltos
- [ ] Ejemplos validados con sintaxis real
- [ ] Links internos verificados
- [ ] Markdown valida (`mdlint` sin errores)
- [ ] Coherencia con `.github/SHARED_INSTRUCTIONS.md`
- [ ] Coherencia con `CLAUDE.md` y `copilot-instructions.md`
```

---

## Criterios de éxito

Un comando `/performance-audit` auditado satisfactoriamente debe:

1. ✅ **Estructura**: Fácil de navegar, bien jerarquizado, TOC si > 100 líneas
2. ✅ **Inputs**: Claros, validados, con ejemplos, sin ambigüedad
3. ✅ **Workflow**: 4 fases bien diferenciadas, outputs claros, sin solapamiento
4. ✅ **Áreas**: 10 áreas documentadas con archivo(s) específicos, ejemplos de hallazgo típicos
5. ✅ **Información técnica**: Causal claro, estimaciones justificadas, best practices referenciadas
6. ✅ **Validación**: Estrategia de benchmark explicada, diferencia hipótesis de confirmación
7. ✅ **Usabilidad**: Ejemplo de invocación realista, troubleshooting, integración clara
8. ✅ **Referencias**: Links verificados, archivos existentes, no placeholders
9. ✅ **Coherencia**: Alineado con `.github/SHARED_INSTRUCTIONS.md`, agentes, prompts
10. ✅ **Completitud**: Nada crítico omitido, pero tampoco es libro (máx. 300 líneas)

---

## Checklist de ejecución

Antes de iniciar auditoría:

- [ ] Leer archivo actual: `.claude/commands/performance-audit-bulk.md`
- [ ] Leer agente relacionado: `.github/agents/performance-auditor.agent.md`
- [ ] Leer prompt base: `.github/prompts/performance_audit_bulk.prompt.md`
- [ ] Leer guía usuario: `docs/PERFORMANCE_AUDIT_GUIDE.md` (si existe)
- [ ] Leer instrucciones compartidas: `.github/SHARED_INSTRUCTIONS.md`
- [ ] Acceso a estructura de módulo: `src/util_bbdd/bulk/`
- [ ] Referencia de scripts: `scripts/bench_bulk.py`

---

## Referencias (entradas de búsqueda sugeridas)

Para validar información sobre optimización de rendimiento:

- "Python bulk database operations performance best practices 2024"
- "SQLAlchemy bulk insert vs. executemany performance"
- "Database connection pooling optimal size threading"
- "Pandas DataFrame batch insert optimization"
- "Oracle parallel bulk insert APPEND hint performance"
- "MySQL LOAD DATA INFILE vs. INSERT batch performance"
- "PostgreSQL COPY performance multi-row insert"
- "SQL Server BULK INSERT vs. INSERT VALUES"
- "SQLite batch insert transaction performance WAL"
- "Audit logging async performance impact"
- "Python tracemalloc memory profiling bulk operations"
- "Concurrent futures thread pool database performance"

---

## Invocación

```markdown
Lee .claude/commands/performance-audit-bulk.md y audita su calidad.

Aplica los 4 criterios de auditoría: ESTRUCTURA, COMPLETITUD, INFORMACIÓN_RENDIMIENTO, USABILIDAD.

Genera: PHASE 1 → PHASE 2 → PHASE 3 → PHASE 4 → VERSION

Entrega: audit_report_performance_audit_command_YYYYMMDD.md
         + improvement_roadmap_performance_audit_command.md

Propósito: Identificar gaps, mejorar información sobre rendimiento y optimizar usabilidad del comando.

Puedes consultar internet para best practices en optimización de bases de datos y Python.
```

---

*Creado: 2026-09-25*
*Aplicable a*: `.claude/commands/performance-audit-bulk.md` y agentes relacionados
