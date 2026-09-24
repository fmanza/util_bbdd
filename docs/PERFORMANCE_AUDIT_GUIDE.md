# Guía de Auditoría de Rendimiento — Módulo `dump`

## Propósito

Esta guía explica cómo usar el sistema de auditoría de rendimiento para el módulo `dump` de util_bbdd, que orquesta el volcado (copia masiva) de datos entre esquemas/bases de datos.

**Objetivo**: Identificar y ejecutar mejoras de rendimiento para maximizar la velocidad de carga de datos.

---

## ¿Por Qué Auditar Rendimiento?

El módulo `dump` es **crítico de rendimiento** para casos de uso como:
- Migraciones de bases de datos (millones de filas)
- Copias de esquemas en CI/CD (tests, clones dev)
- Archivado de datos históricos
- Replicación entre motores (PostgreSQL → SQL Server, etc.)

**Impacto**: Una mejora del **+20% en throughput** puede ahorrar **horas** en volcados de millones de filas.

---

## Componentes del Sistema

### 1. Prompt de Auditoría Generic
**Ubicación**: `.github/prompts/performance_audit_dump.prompt.md`

Prompt exhaustivo (referencia técnica) que detalla:
- Contexto de arquitectura actual (5 fases)
- Cuellos de botella hipotéticos (CB1-CB8)
- Mejoras concretas categorizadas (Lectura, Escritura, Constraints, etc.)
- Métricas de éxito y benchmarks
- Referencias a documentación oficial

**Uso**: Consultar cuando necesites **contexto completo** o buscar ideas específicas.

### 2. Prompt para Agente Especializado
**Ubicación**: `.github/prompts/performance_audit_dump_agent.prompt.md`

Prompt ejecutable por agentes (Copilot, Claude Code). Estructura por **fases**:
- **FASE 1**: Análisis de arquitectura (2 hrs)
- **FASE 2**: Identificación de cuellos (2 hrs)
- **FASE 3**: Propuestas de mejora (3 hrs)
- **FASE 4**: Informe final (2 hrs)
- **FASE 5**: Testing/validación (opcional)

**Uso**: Invocar directamente con un agente para obtener auditoría completa.

### 3. Script de Benchmarking
**Ubicación**: `scripts/bench_dump.py`

Herramienta de línea de comandos para medir rendimiento actual. Incluye:
- **Configuraciones**: baseline, optimized, parallel
- **Volúmenes**: small (10k-50k), medium (100k-500k), large (500k-2M)
- **Generador de datos** sintéticos
- **Resultados JSON** con estadísticas

**Uso**: Capturar baseline actual y validar mejoras post-implementación.

---

## Flujo de Trabajo Recomendado

### Opción A: Auditoría Completa (Con Agente)

**Duración**: 4-6 horas  
**Entrada**: Especificación de objetivo  
**Salida**: Informe + recomendaciones + roadmap

**Pasos**:

1. **Invocar agente** (Copilot Chat o Claude Code):
   ```
   @Performance Auditor
   Lee .github/prompts/performance_audit_dump_agent.prompt.md
   Audita módulo src/util_bbdd/dump/
   Entregar: informe estructurado + mejoras priorizadas + roadmap
   ```

2. **Agente ejecuta 5 fases**:
   - Analiza arquitectura actual
   - Identifica cuellos de botella
   - Propone mejoras concretas (ordenadas por prioridad)
   - Genera informe ejecutivo
   - Sugiere testing/validación

3. **Revisar salida**:
   - Tabla de mejoras (impacto × esfuerzo × riesgo)
   - Roadmap de implementación (fases)
   - Recomendaciones de configuración por dialecto
   - Próximos pasos

4. **Crear issues** en GitHub basados en roadmap:
   - P1 (quick wins, 1-2 semanas)
   - P2 (medio plazo, 2-4 semanas)
   - P3 (largo plazo, 1-2 meses)

---

### Opción B: Análisis Rápido (Manual)

**Duración**: 1-2 horas  
**Entrada**: Punto de interés específico  
**Salida**: Análisis localizado + recomendación

**Pasos**:

1. **Identificar cuello de botella**:
   - Revisar `.github/prompts/performance_audit_dump.prompt.md` § "Cuellos Hipotéticos"
   - Ej: "¿Lectura origen lenta?" → CB1

2. **Consultar propuestas** por categoría:
   - § "Mejoras Concretas" → buscar categoría (Lectura, Escritura, etc.)
   - Leer Impacto/Esfuerzo/Riesgo
   - Evaluar viabilidad

3. **Implementar cambio acotado**:
   - Crear feature branch
   - Cambios mínimos (no refactorizar)
   - Tests pasan

4. **Benchmarkear**:
   - Ejecutar `scripts/bench_dump.py` antes/después
   - Validar que % mejora coincide con estimación

---

### Opción C: Benchmarking Baseline (Setup Inicial)

**Duración**: 30-60 minutos  
**Entrada**: BD de prueba (o SQLite sintético)  
**Salida**: Métricas baseline para futuras comparaciones

**Pasos**:

1. **Listar configuraciones disponibles**:
   ```bash
   python scripts/bench_dump.py --list-configs
   ```
   ```
   Configuraciones disponibles:
     baseline          — Configuración default (chunk_size=5000, no paralelismo)
     optimized         — Optimizado: chunk dinámico, constraints batched, row_counts=False
     parallel          — Paralelo: parallel_pk_ranges=CPU_COUNT, chunk_size=10000
   ```

2. **Capturar baseline** (configuración actual):
   ```bash
   python scripts/bench_dump.py \
     --config baseline \
     --volume small \
     --iterations 3 \
     --output bench_results/
   ```

3. **Registrar resultados**:
   - Archivo generado: `bench_results/bench_results_YYYYMMDD_HHMMSS.json`
   - Ejemplo:
     ```json
     {
       "timestamp": "2026-09-24T14:30:00",
       "config": "baseline",
       "volume": "small",
       "throughput_rows_per_sec": 15234,
       "avg": 3.28
     }
     ```

4. **Repetir con volúmenes mayores**:
   ```bash
   python scripts/bench_dump.py --config baseline --volume medium
   python scripts/bench_dump.py --config baseline --volume large
   ```

5. **Guardar baseline** como referencia:
   ```
   # Git commit
   git add bench_results/bench_results_*.json
   git commit -m "docs: baseline benchmark — dump module (small/medium/large)"
   ```

---

## Uso de Scripts de Benchmarking

### Sintaxis Básica

```bash
python scripts/bench_dump.py [options]
```

### Opciones

| Opción | Defecto | Descripción |
|---|---|---|
| `--config` | baseline | Configuración: `baseline`, `optimized`, `parallel` |
| `--volume` | small | Volumen: `small` (10k-50k), `medium` (100k-500k), `large` (500k-2M) |
| `--iterations` | 1 | Número de iteraciones (para promediado) |
| `--db-url` | `sqlite:///:memory:` | URL de conexión (defecto: SQLite en memoria) |
| `--output` | `bench_results/` | Directorio de salida |
| `--list-configs` | — | Listar configuraciones |
| `--list-volumes` | — | Listar volúmenes |
| `-v, --verbose` | — | Logging detallado |

### Ejemplos de Uso

**1. Baseline rápido (SQLite in-memory)**:
```bash
python scripts/bench_dump.py --config baseline --volume small
```

**2. Benchmark con BD real (PostgreSQL)**:
```bash
python scripts/bench_dump.py \
  --config optimized \
  --volume large \
  --iterations 3 \
  --db-url "postgresql+psycopg2://user:pass@localhost/testdb" \
  --output bench_results/postgres/
```

**3. Comparar configuraciones**:
```bash
# Baseline
python scripts/bench_dump.py --config baseline --volume medium -o results/

# Optimizado
python scripts/bench_dump.py --config optimized --volume medium -o results/

# Paralelo
python scripts/bench_dump.py --config parallel --volume medium -o results/

# Comparar resultados/bench_results_*.json
```

**4. Listar opciones**:
```bash
python scripts/bench_dump.py --list-configs
python scripts/bench_dump.py --list-volumes
```

### Interpretación de Resultados

Archivo de salida: `bench_results/bench_results_YYYYMMDD_HHMMSS.json`

```json
{
  "timestamp": "2026-09-24T14:30:45.123456",
  "config": "baseline",
  "volume": "small",
  "iterations": 3,
  "times_seconds": [3.28, 3.35, 3.31],
  "min": 3.28,
  "max": 3.35,
  "avg": 3.31,
  "total_rows": 85000,
  "throughput_rows_per_sec": 25682
}
```

**Métricas clave**:
- **throughput_rows_per_sec**: Filas cargadas por segundo (KPI principal)
- **avg**: Tiempo promedio de carga (segundos)
- **total_rows**: Volumen total para esta ejecución

**Comparación baseline vs. optimizado**:
```
Baseline:  throughput=15000 rows/sec, avg=5.66s
Optimized: throughput=18750 rows/sec, avg=4.53s
Mejora:    +25% en throughput, -20% en tiempo
```

---

## Cómo Usar el Prompt con Agentes

### Con Copilot Chat (VS Code)

1. **Abre Copilot Chat** (Ctrl+L o Cmd+L)

2. **Invoca el agente Performance Auditor**:
   ```
   @Performance Auditor
   
   Lee .github/prompts/performance_audit_dump_agent.prompt.md
   Audita el módulo src/util_bbdd/dump/ para identificar mejoras de rendimiento.
   Fase 1-4: análisis completo + propuestas + roadmap.
   ```

3. **Agente ejecuta y devuelve**:
   - Informe estructurado (Markdown)
   - Tabla de mejoras priorizadas
   - Recomendaciones de configuración
   - Plan de testing

4. **Guardar resultado**:
   - Copiar informe a `.ai/sessions/[fecha]/PERFORMANCE_AUDIT_DUMP.md`
   - Commit en Git

### Con Claude Code

1. **Ejecuta slash command** (si está configurado):
   ```
   /performance-audit
   
   Objetivo: auditar dump/ para rendimiento
   ```
   
   Alternativa (sin slash command predefinido):
   ```
   Lee .github/prompts/performance_audit_dump_agent.prompt.md
   Aplica las 5 fases de auditoría al módulo src/util_bbdd/dump/
   Entrega: informe + mejoras + roadmap
   ```

2. **Claude Code ejecuta fases** y devuelve resultado

3. **Guardar en `.ai/sessions/[fecha]/`**

---

## Interpretación del Informe de Auditoría

El informe sigue esta estructura:

### Sección 1: Resumen Ejecutivo
- Hallazgos clave (3-5 puntos)
- Oportunidad de mejora estimada (ej: +25% throughput)
- Esfuerzo total (horas)
- Nivel de riesgo

### Sección 2: Cuellos de Botella Identificados

| Código | Cuello | Ubicación | Evidencia |
|---|---|---|---|
| CB1 | Lectura origen lenta | `orchestrator.py:_load_whole_table()` | chunk_size=5000 puede ser subóptimo |
| CB2 | Transform overhead | Loop de chunks | Renombrado por fila vs. por chunk |
| ... | | | |

### Sección 3: Mejoras Priorizadas

| ID | Mejora | Categoría | Impacto | Esfuerzo | Riesgo | Priority | Ejemplo |
|---|---|---|---|---|---|---|---|
| P1 | Batch disable constraints | Constraints | 2/5 | 2/5 | 1/5 | 0.5 | Ver pseudocódigo en informe |
| P2 | PostgreSQL COPY | Escritura | 4/5 | 3/5 | 2/5 | 0.67 | `COPY tablename FROM STDIN` |
| ... | | | | | | | |

**Cómo interpretar Priority**: `Priority = Impacto / (Esfuerzo × Riesgo)`
- Priority > 0.6 → Quick wins (implementar primero)
- 0.3 < Priority ≤ 0.6 → Mediano plazo
- Priority ≤ 0.3 → Largo plazo o research

### Sección 4: Roadmap de Implementación

**Fase 1 — Quick Wins** (1-2 semanas):
- P1, P5, P6a — bajo esfuerzo, riesgo mínimo

**Fase 2 — Mediano Plazo** (2-4 semanas):
- P2, P3, P4 — requiere testing, dialecto-specific

**Fase 3 — Largo Plazo** (1-2 meses):
- P7, P8, P9 — refactorización mayor, validación exhaustiva

### Sección 5: Recomendaciones de Configuración

Por dialecto (SQL Server, PostgreSQL, MySQL, Oracle, SQLite):
- Valores default recomendados para `DumpConfig`
- Tuning pre/post carga
- Best practices

### Sección 6: Plan de Testing

- Scripts en `scripts/bench_dump.py`
- Criterios de éxito (% mejora, regresión)
- Casos de test por mejora

---

## Integración con GitHub Issues y Roadmap

Una vez completada la auditoría:

1. **Crear issues por mejora** (P1, P2, ...):
   ```
   Title: [PERF] Dump: Batch disable constraints
   Tipo: Enhancement
   Prioridad: High
   Estimación: 4 horas
   Impacto: +15% throughput en Fase 2
   Descripción: Ver auditoría en .ai/sessions/[fecha]/PERFORMANCE_AUDIT_DUMP.md
   ```

2. **Asignar a fases**:
   - Milestones: "Phase 1 — Quick Wins", "Phase 2 — Medium Term", etc.
   - Labels: `perf-audit`, `dump`, `enhancement`

3. **Vincular a PR**:
   - Implementar mejora en feature branch
   - Citar issue en PR description
   - Ejecutar benchmarks en CI (si está disponible)

---

## Preguntas Frecuentes

### ¿Por dónde empiezo si nunca he auditado rendimiento?

**Respuesta**: Opción A (Auditoría Completa) es recomendada para entender el panorama completo. Toma 4-6 horas pero da visibilidad de roadmap para **meses de optimización**.

### ¿Puedo auditar solo una parte (ej: lectura origen)?

**Respuesta**: Sí. Usa Opción B (Análisis Rápido):
1. Abre `.github/prompts/performance_audit_dump.prompt.md`
2. Busca categoría de interés (ej: "Optimización de Lectura")
3. Revisa propuestas + impacto
4. Implementa + benchmarkea

### ¿Con qué BD testeo si solo tengo SQLite?

**Respuesta**: `scripts/bench_dump.py` usa **SQLite in-memory por defecto**. Perfecto para:
- Baseline rápido
- Comparar configuraciones
- Validar lógica

Para benchmarking realista con múltiples dialectos:
- Usar Docker Compose (si dispones)
- Probar con PostgreSQL local (o cloud trial)

### ¿Cada cuánto debo re-auditar?

**Respuesta**:
- **Primera vez**: Auditoría completa (4-6 hrs)
- **Después de cambios mayores** (refactor, nueva versión): Auditoría completa
- **Trimestral**: Benchmarking baseline (30 mins) para detectar regresiones

### ¿Puedo compartir resultados de benchmarking?

**Respuesta**: Sí, guardá en:
```
bench_results/
  YYYYMMDD_baseline_small.json
  YYYYMMDD_baseline_medium.json
  YYYYMMDD_optimized_medium.json
  ...
```
Luego crea PR con benchmark results (documenta en RELEASE_NOTES o similar).

---

## Recursos Relacionados

- **Prompt base**: `.github/prompts/performance_audit_dump.prompt.md`
- **Prompt agente**: `.github/prompts/performance_audit_dump_agent.prompt.md`
- **Script benchmark**: `scripts/bench_dump.py`
- **Código módulo dump**: `src/util_bbdd/dump/`
- **Docs funcional**: `docs/functional/dump.md` (si existe)
- **Docs técnica**: `docs/api/dump.md` (si existe)

---

## Próximos Pasos

1. **Primer paso recomendado**:
   ```bash
   # Capturar baseline
   python scripts/bench_dump.py --config baseline --volume small
   
   # Guardar en Git
   git add bench_results/
   git commit -m "perf: baseline benchmark — dump (small volume)"
   ```

2. **Luego, solicitar auditoría**:
   ```
   @Performance Auditor
   (Ver Opción A arriba)
   ```

3. **Implementar mejoras fase a fase** según roadmap del informe.

---

*Guía actualizada: 2026-09-24 | Versión: 1.0*
