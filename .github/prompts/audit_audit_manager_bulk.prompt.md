# PROMPT: Auditoría del Componente Audit en Módulo Bulk

## Objetivo

Auditar la funcionalidad de **auditoría integrada del módulo bulk** (Área A5 de las 10 áreas):
validar impacto en rendimiento, metodología de logging, persistencia, y oportunidades de optimización.

**Scope**: `src/util_bbdd/bulk/audit.py` (`AuditManager`) + `src/util_bbdd/bulk/_audit/` y su integración con
`src/util_bbdd/bulk/crud.py` a través de `src/util_bbdd/bulk/_support/persistence.py`

> **Mapa real del componente** (verificado 2026-09-25, sesión `2026-09-25-audit-code-audit-manager`; revísalo contra
> el código antes de auditar):
> - `bulk/audit.py`: fachada `AuditManager` (`registrar_operacion`, `_registrar_lote`, filtros, exports) y
>   `AuditTransaction` (contador en memoria, no persiste).
> - `bulk/_audit/repository.py`: CSV **tabulado y síncrono**, sin buffer ni modo async; lock por ruta
>   (intra-proceso); caché de lectura con TTL + firma del fichero.
> - `bulk/_audit/{service,exporters,record,errors}.py`: analítica, Excel/JSON/HTML, `AuditRecord`, excepciones.
> - `bulk/_support/persistence.py`: `BulkPersistenceManager`: auditoría directa fuera de `bulk_session`, diferida
>   hasta el commit dentro; política `audit_strict` (fail-open por defecto).
> - Granularidad: **una fila CSV por operación** (`bulk_*_from_df`) **o por chunk** (`bulk_insert_from_chunks`),
>   nunca por fila de datos. No hay tabla de auditoría en BD.

**Entregables**:
- Hallazgos de rendimiento de `AuditManager`
- Propuestas de optimización de logging sync/async
- Análisis de overhead por fila
- Recomendaciones de persistencia

---

## Contexto previo

Lee antes de auditar:

1. `.ai/architecture.md` — Arquitectura de util_bbdd y capas
2. `.ai/standards.md` — Criterios de calidad
3. `.github/prompts/performance_audit_bulk.prompt.md` — Guía general (Área A5)
4. `src/util_bbdd/bulk/audit.py` y `src/util_bbdd/bulk/_audit/` — Código actual
5. `src/util_bbdd/bulk/crud.py` y `src/util_bbdd/bulk/_support/persistence.py` — Integración con bulk load
6. `docs/PERFORMANCE_AUDIT_GUIDE.md` — Documentación usuario (si existe)

---

## Scope detallado

### A. Análisis estático de código (AuditManager)

- [ ] **Estructura**: ¿Cómo está organizado `AuditManager`?
  - Métodos públicos: logging, persistencia, queryable
  - Métodos privados: formato, serialización, caché

- [ ] **Overhead por operación**: ¿Qué se ejecuta en hot path?
  - `registrar_operacion()` / `_registrar_lote()` → tiempo de ejecución
  - escritura del CSV (`AuditCsvRepository.escribir_registros`) → I/O síncrono
  - Formato de entrada (dict, tuple, etc.) → costo de parsing

- [ ] **Memoria**: ¿Cuál es el footprint?
  - Buffer en memoria antes de persistir
  - Tamaño por fila (audit record)
  - Deallocación (memory leaks?)

- [ ] **Integración con `crud.py`**: ¿Cuándo se invoca?
  - `BulkPersistenceManager.register_operation()`: ¿por operación, por chunk o por fila?
  - ¿Antes o después del commit? (dentro de `bulk_session` se difiere hasta el commit)
  - Configuración (on/off, nivel de detalle)

- [ ] **Dependencias**: ¿Qué librerías usa?
  - sqlite3, sqlalchemy, custom serializer?
  - Impacto de versión de dependencia

---

### B. Comportamiento sync vs. async

- [ ] **Logging sync (default)**:
  - ¿Bloquea el INSERT hasta persistir audit?
  - ¿Cuál es el latency agregado por fila?
  - ¿Es configurable (sync/async)?

- [ ] **Logging async (si existe)**:
  - ¿Usa threading/asyncio?
  - ¿Cuál es el overhead de enqueue?
  - ¿Riesgo de pérdida de datos si falla?
  - ¿Configuración de buffer + flush?

- [ ] **Métricas**:
  - INSERT sin auditoría vs. con auditoría (latency delta)
  - Memoria pico (1K, 100K, 1M registros)
  - CPU usage

---

### C. Persistencia y queryabilidad

- [ ] **Destino de auditoría**:
  - Hoy: CSV local tabulado (no hay tabla de auditoría en BD). ¿Sigue siendo así?
  - ¿Archivo local (JSON, CSV)?
  - ¿Implicación de performance (lock contention, I/O)?

- [ ] **Formato de registro**:
  - Campos auditados por fila
  - Serialización (JSON, pickle, binary)
  - Compression (si volumen grande)

- [ ] **Query pattern**:
  - ¿Se consulta auditoría durante proceso de load?
  - ¿O solo post-load (validación)?
  - Índices, filters disponibles?

- [ ] **Lifecycle**:
  - ¿Cuándo se borra? (purge policy)
  - ¿Afecta rendimiento de load?
  - ¿Hay archivamiento?

---

### D. Validación e integridad

- [ ] **Validación en auditoría**:
  - ¿Se valida cada fila insertada?
  - ¿Retorna errores detallados?
  - Impacto en throughput

- [ ] **Recuperación ante errores**:
  - Si audit persiste falla, ¿se rollback el INSERT?
  - ¿O se continúa sin audit?
  - Configuración y riesgos

- [ ] **Compliance**:
  - ¿Cumple requirement de auditoría?
  - ¿Es recuperable (trazabilidad)?

---

### E. Configuración y knobs

- [ ] **Knobs disponibles**:
  - On/off
  - Nivel de detalle (básico, completo, diagnostics)
  - Buffer size
  - Flush interval
  - Dest (BD, file, disabled)

- [ ] **Documentación**:
  - ¿Están documentados?
  - ¿Recomendaciones de valores por escala?

- [ ] **Valores por defecto**:
  - ¿Son seguros pero cautelosos?
  - ¿O optimistas (riesgo)?

---

## Plan de auditoría (5 fases)

### FASE 1: MAP_CURRENT_STATE (1 hr)
**Responsabilidad**: Mapear arquitectura actual del AuditManager.

**Checklist**:
1. Leer `bulk/audit.py` y `bulk/_audit/`:
   - Clase y métodos principales
   - Dependencias importadas
   - Configuración (si aplica)

2. Leer integración en `bulk/crud.py` y `bulk/_support/persistence.py`:
   - Dónde/cuándo se invoca audit
   - Frecuencia (por fila, por batch)
   - Manejo de errores

3. Dibujar diagrama:
   - INSERT → `register_operation()` → (commit) → escritura CSV
   - Identificar hot paths

4. Documentar supuestos:
   - ¿Qué no está claro?
   - ¿Qué requiere benchmarking?

**Salida**: Diagrama actual + lista de preguntas

---

### FASE 2: MEASURE_OVERHEAD (1.5–2 hrs)
**Responsabilidad**: Cuantificar impacto de auditoría en rendimiento.

**Checklist**:
1. Benchmark simple:
   - INSERT 1K, 100K, 1M registros SIN auditoría
   - INSERT 1K, 100K, 1M registros CON auditoría
   - Calcular delta (ms/fila, throughput %)

2. Ambiente:
   - BBDD: PostgreSQL (por defecto) + otra si aplica (MySQL, SQLite)
   - CPU, RAM, storage info
   - Driver version

3. Metodología:
   - Repeticiones (3x, descartando outliers)
   - Warmup (sí/no)
   - Medición (timing.perf_counter, profiler)

4. Capturar:
   - Latency por fila (ms)
   - Throughput (filas/seg)
   - Pico de memoria
   - CPU usage (%)
   - I/O read/write (si persistencia)

**Salida**: Tabla de benchmarks + gráficos

---

### FASE 3: ANALYZE_CODE (1.5–2 hrs)
**Responsabilidad**: Identificar cuellos de botella y oportunidades en código.

**Checklist**:
1. Audit hot path:
   - `registrar_operacion()` / `escribir_registros()` → línea por línea
   - ¿Hay allocations innecesarias?
   - ¿Hay conversiones de tipo caras?

2. Persistencia:
   - Escritura del CSV → coste de I/O (`open`/`close`, lock, `stat`)
   - ¿Una escritura por operación o por commit (`_registrar_lote`)?
   - Tip: medir el tiempo **dentro** de la auditoría durante una carga real; la resta E2E con/sin queda en el ruido

3. Async (si existe):
   - ¿Thread pool bien configurado?
   - ¿Queue capacity?
   - ¿Backpressure handling?

4. Memory:
   - Buffer size → risk de OOM?
   - Deallocación explícita?
   - Circular references?

5. Comparar con best practices:
   - Python logging module (asyncio support)
   - SQLAlchemy bulk patterns
   - Documentation oficial de BBDD

**Salida**: Hallazgos con snippets de código + best practice referencias

---

### FASE 4: PROPOSE_OPTIMIZATIONS (1–1.5 hrs)
**Responsabilidad**: Proponer mejoras priorizadas.

**Checklist**:
1. Quick wins (< 1h, 5%+ mejora):
   - Eliminar allocations innecesarias
   - Cambiar sync flush → batch
   - Configuración default mejorada

2. Medium (1-4h, 10-20% mejora):
   - Async logging (si sync)
   - Batch commit + índices
   - Compression de audit records

3. Long-term (> 4h, > 20% mejora):
   - Separate audit DB
   - Streaming audit (no buffer)
   - Opt-in detailed audit (levels)

4. Para cada mejora:
   - Descripción
   - Estimación de impacto (%)
   - Esfuerzo (horas)
   - Riesgo (breaking changes, data migration)
   - Trade-offs (mantenibilidad, seguridad)

**Salida**: Roadmap de mejoras priorizado

---

### FASE 5: VALIDATE_MULTI_DIALECT (1 hr)
**Responsabilidad**: Verificar que findings aplican a múltiples BDD.

**Checklist**:
1. Revisar si audit está hardcoded a una BBDD:
   - ¿O es agnóstico (SQL genérico)?

2. Multi-dialect testing (conceptual):
   - ¿Audit funciona igual en PostgreSQL, MySQL, SQLite, SQL Server?
   - ¿Hay diferencias de rendimiento significativas?
   - ¿Optimizaciones specific per dialect?

3. Compatibilidad:
   - ¿Tipos de datos (UUID, JSONB, etc.)?
   - ¿Transacciones (rollback behavior)?
   - ¿Constraints (FK, PK en audit table)?

**Salida**: Matriz de compatibilidad + recomendaciones por dialect

---

## Formato de hallazgo

```
### Hallazgo: [Nombre breve]

**Fase**: [1|2|3|4|5]
**Tipo**: [Overhead | Memory | Async | Config | Compatibility]
**Severidad**: [CRÍTICA | ALTA | MEDIA | BAJA | INFO]

**Descripción**:
[Qué es el problema y por qué afecta rendimiento o confiabilidad]

**Evidencia**:
- Código: [snippet + líneas]
- Benchmark: [métricas cuantificadas]
- Referencia: [best practice link]

**Impacto estimado**:
- Overhead actual: [ms/fila, % throughput]
- Impacto potencial: [% mejora si se optimiza]

**Propuesta de mejora**:
- Cambio concreto: [qué implementar]
- Esfuerzo: [Trivial | Bajo | Medio | Alto]
- Riesgo: [Breaking changes, datos, compatibilidad]
- Tests requeridos: [qué verificar]

**Multi-dialect notes**:
- PostgreSQL: [aplicable / no]
- MySQL: [aplicable / no]
- SQLite: [aplicable / no]
- SQL Server: [aplicable / no]
```

---

## VERSION - Reporte final

```
## AUDIT REPORT: AuditManager Rendimiento

### Executive Summary
**Estado actual**: [BIEN_OPTIMIZADO | ACEPTABLE | SUBOPTIMIZADO | CRÍTICO]

- Overhead actual: [% vs. INSERT sin auditoría]
- Hallazgos totales: [N]
- Por severidad: CRÍTICA: X | ALTA: Y | MEDIA: Z | BAJA: W

**Recomendación**:
[Producción segura | Producción con configuración | Requiere optimización antes de 1M registros]

### Key Metrics (Baseline)
| Métrica | 1K rows | 100K rows | 1M rows |
|---------|---------|-----------|---------|
| Throughput sin audit (rows/sec) | X | X | X |
| Throughput con audit (rows/sec) | X | X | X |
| Overhead (%) | Y | Y | Y |
| Memory pico (MB) | Z | Z | Z |

### Top 5 Hallazgos prioritarios
1. [Hallazgo + impacto en %]
2. ...

### Hallazgos por tipo
#### Overhead (Hot path)
- [Hallazgo 1: código ineficiente]
- [Hallazgo 2: allocations]
- ...

#### Memory
- [Hallazgo: buffer sizing]
- ...

#### Async/Threading
- [Hallazgo: si aplica]
- ...

#### Configuration
- [Hallazgo: defaults no optimales]
- ...

#### Compatibility
- [Hallazgo: multi-dialect issues]
- ...

### Roadmap de Optimización
**Fase 1 (CRÍTICA + ALTA)** — Semana 1
- [Mejora 1: quick win, impacto 5%]
- [Mejora 2: async logging, impacto 15%]

**Fase 2 (MEDIA)** — Semana 2-3
- [Mejora 3: batch commit, impacto 10%]
- ...

**Fase 3 (Nice-to-have)** — Semana 4+
- [Mejora 4: separate DB]
- ...

### Recomendaciones de configuración
Para diferentes escenarios:

**Escenario: 1K registros (desarrollo)**
- Auditoría: ON (detail=basic)
- Buffer: 100
- Flush: sync per batch

**Escenario: 100K registros (staging)**
- Auditoría: ON (detail=basic)
- Buffer: 1000
- Flush: async, batch 5000

**Escenario: 1M registros (producción)**
- Auditoría: ON (detail=basic, events only)
- Buffer: 10000
- Flush: async, separate thread
- Considerar: separate audit DB

### Risk Assessment
- Breaking changes: [ninguno | algunos | muchos]
- Data migration required: [sí/no]
- Rollback complexity: [bajo/medio/alto]
- Multi-dialect compatibility: [%]

### Validation Strategy
Post-implementación de Fase 1:
- Benchmark comparison (before/after)
- Audit data integrity (spot checks)
- Load test (1K, 100K escenarios)
- Multi-dialect validation
```

---

## Criterios de éxito

Un reporte de auditoría AuditManager **completo** debe:

1. ✅ **Overhead cuantificado**: Métricas claras (ms/fila, % throughput)
2. ✅ **Hot path identificado**: Código exacto que causa overhead
3. ✅ **Benchmark multi-escala**: 1K, 100K, 1M en al menos 2 dialects
4. ✅ **Best practices documentadas**: Referencias oficiales (SQLAlchemy, logging, etc.)
5. ✅ **Mejoras priorizadas**: Quick wins + medium + long-term
6. ✅ **Multi-dialect análisis**: Aplicabilidad por BBDD
7. ✅ **Config recomendada**: Guía por escenario de uso
8. ✅ **Risk mapping**: Breaking changes, data migration, rollback
9. ✅ **Validación clara**: Cómo confirmar mejoras post-implementación
10. ✅ **Actionable**: Dev entiende qué implementar, PM entiende ROI

---

## Checklist de ejecución

Antes de iniciar auditoría de AuditManager:

- [ ] `src/util_bbdd/bulk/audit.py` y `src/util_bbdd/bulk/_audit/` disponibles y legibles
- [ ] `src/util_bbdd/bulk/crud.py` y `src/util_bbdd/bulk/_support/persistence.py` disponibles (para integración)
- [ ] `scripts/bench_bulk.py` o equivalente disponible
- [ ] Acceso a ambiente con 2+ BDD (PostgreSQL + MySQL o similar)
- [ ] `.ai/standards.md` disponible
- [ ] `.github/prompts/performance_audit_bulk.prompt.md` disponible como referencia

---

## Referencias (búsquedas internet recomendadas)

Para validar información sobre logging y auditoría:

- "Python logging module performance async handlers"
- "SQLAlchemy audit logging bulk insert performance"
- "Database audit table design performance impact"
- "Async logging buffer sizing Python best practices"
- "Multi-threaded database logging contention patterns"
- "Audit logging compliance vs. performance trade-offs"
- "PostgreSQL MySQL SQLite audit table indexes performance"
- "Python memory profiling bulk operations audit overhead"

---

## Invocación

```markdown
Audita el componente de auditoría integrada del módulo bulk.

Scope: AuditManager (src/util_bbdd/bulk/audit.py + src/util_bbdd/bulk/_audit/)
Integración: src/util_bbdd/bulk/crud.py + src/util_bbdd/bulk/_support/persistence.py

Aplica las 5 fases:
MAP_CURRENT_STATE → MEASURE_OVERHEAD → ANALYZE_CODE →
PROPOSE_OPTIMIZATIONS → VALIDATE_MULTI_DIALECT

Genera: audit_report_audit_manager_YYYYMMDD.md
        + optimization_roadmap_audit_manager.md
        + benchmark_audit_overhead.csv (opcional)

Propósito: Identificar y optimizar overhead de auditoría en carga masiva.

Puedes consultar internet para best practices en logging async y auditoría de bases de datos.
```

---

*Creado: 2026-09-25*
*Aplicable a*: Auditoría de rendimiento del componente AuditManager (Área A5)
