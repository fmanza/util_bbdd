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

Banco real: ejecuta `DumpOrchestrator` contra los motores de `docker-compose.bench.yml` (PostgreSQL, MySQL, MariaDB,
SQL Server, Oracle y SQLite como destino). Incluye:
- **Variantes**: `baseline`, auditoría, cursor de servidor, `arraysize`, lotes, solape, rangos de PK, índices y combinaciones
- **Volúmenes**: tiny (8,5K), small (85K), medium (850K), large (3,5M filas)
- **Desglose por fase**, memoria pico y verificación origen/destino en cada medición
- **Resumen Markdown** con la mediana por motor y variante (`summarize`)

**Uso**: capturar la línea base y validar mejoras antes y después de implementarlas.

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

**Duración**: 30–60 minutos con el volumen `large` en un motor
**Entrada**: contenedores de `docker-compose.bench.yml`
**Salida**: `results.jsonl` y resumen Markdown para comparar después

**Pasos**:

1. Levanta los contenedores y define `UTIL_BBDD_BENCH_PASSWORD`.
2. Prepara los datos: `python scripts/bench_dump.py setup --engines postgresql --volume large`.
3. Mide la línea base con 3 repeticiones: `python scripts/bench_dump.py run --engines postgresql --variants baseline --volume large --repeat 3 --out <carpeta>`.
4. Resume: `python scripts/bench_dump.py summarize <carpeta>/results.jsonl` y guarda la salida con el informe de la sesión.

---

## Uso del banco de rendimiento

### Requisitos

- Contenedores de `docker-compose.bench.yml` levantados y `UTIL_BBDD_BENCH_PASSWORD` definida con la misma contraseña.
  Puertos: los del banco o `UTIL_BBDD_BENCH_<MOTOR>_PORT`. El banco solo se conecta a `127.0.0.1`.
- SQL Server con pyodbc y *ODBC Driver 18 for SQL Server*; Oracle con `oracledb` (modo thin).

!!! warning "Solo contra los contenedores del banco"
    `setup` borra y recrea `dump_src`/`dump_dst` (esquemas en PostgreSQL y SQL Server, bases en MySQL/MariaDB, usuarios
    en Oracle) y cada medición recrea las tablas de `dump_dst`.

### Subcomandos

| Subcomando | Qué hace |
|---|---|
| `setup --engines E1,E2 --volume V` | Crea origen (datos generados en el servidor) y destino vacío con PK de identidad e índice en cada FK |
| `run --engines … --variants … --volume V --repeat N --out DIR` | Una medición por subproceso (memoria pico propia); añade una línea JSON por medición a `DIR/results.jsonl` |
| `summarize DIR/results.jsonl [...]` | Tabla Markdown: mediana por motor × variante, Δ frente a `baseline`, memoria pico, fases y verificación |
| `list` | Variantes y volúmenes disponibles |

Motores: `postgresql`, `mysql`, `mariadb`, `mssql`, `oracle`, `sqlite` (destino, con PostgreSQL de origen).
Volúmenes: `tiny` (8,5K filas), `small` (85K), `medium` (850K), `large` (3,5M). Tres tablas encadenadas por FK
(`customers` → `orders` → `order_items`).

### Variantes principales

| Variante | Qué cambia |
|---|---|
| `baseline` | `DumpConfig` por defecto |
| `audit` / `audit_history` | Auditoría de `bulk` activa; con CSV nuevo o con un CSV que ya tiene `BENCH_DUMP_AUDIT_HISTORY_ROWS` registros (500.000 por defecto) |
| `stream` | Origen con `stream_results=True` (cursor de servidor) |
| `arraysize` | Origen Oracle con `arraysize=5000` |
| `chunk20k` | `chunk_size=20_000` |
| `prefetch` | Prototipo de solape lectura/escritura (un hilo lector y una cola de 2 chunks) |
| `ranges4`, `ranges8` | `parallel_pk_ranges=4` / `8` |
| `indexes` | `manage_indexes=True` |
| `nocheck` | Rehabilita constraints sin revalidar datos (mide el coste de la validación) |
| `redump` | Destino ya cargado: mide la limpieza de un volcado repetido |
| `combo*`, `best_pg`, `stream_c20k_prefetch`, `arraysize_*` | Combinaciones validadas en la auditoría de 2026-09-25 |

`python scripts/bench_dump.py list` muestra la configuración exacta de cada una.

### Ejemplo: línea base y una variante, 3 repeticiones

```bash
python scripts/bench_dump.py setup --engines postgresql,mssql --volume large
python scripts/bench_dump.py run --engines postgresql,mssql --variants baseline,stream --volume large --repeat 3 --out bench_results/dump
python scripts/bench_dump.py summarize bench_results/dump/results.jsonl
```

### Interpretación de resultados

Cada línea de `results.jsonl` incluye:

- `total_s` y `rows_per_s`: tiempo total del volcado (`DumpOrchestrator(...)` + `run()`) y filas por segundo.
- `phases`: segundos por fase (`read`, `write`, `prep_derived`, `counts`, `constraints_*`, `indexes_*`, `cleanup`,
  `analysis`, `reflect`, `pk_sync`, `audit_summary`, `report`). En variantes con hilos las fases se suman entre hilos:
  compara solo el total.
- `peak_rss_mb`: memoria pico del proceso.
- `status` y `errors` por tabla, `constraints`, `pk_sync`, `indexes` y, con auditoría, `audit`.
- `verify`: COUNT y SUM(PK) de origen y destino por tabla (`ok`) y la sonda de identidad (`identity_ok`: un INSERT sin
  PK tras el volcado no choca con las filas cargadas).

Criterios: usa la mediana de 3 repeticiones (el ruido de una sola repetición llegó a ±10 %) y no des por buena una
medición con `verify.ok = false` o con alguna tabla distinta de `success`.

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
   /performance-audit-dump
   
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

**Respuesta**: `scripts/bench_dump.py` mide SQLite solo como **destino**, con PostgreSQL de origen (el origen SQLite no
está soportado por `dump`). Para medir necesitas al menos el contenedor PostgreSQL de `docker-compose.bench.yml`. Las
cifras de SQLite en memoria no son representativas: la escritura y la lectura contra un servidor real dominan el tiempo
(45–73 % y 19–42 % en la auditoría de 2026-09-25).

### ¿Cada cuánto debo re-auditar?

**Respuesta**:
- **Primera vez**: Auditoría completa (4-6 hrs)
- **Después de cambios mayores** (refactor, nueva versión): Auditoría completa
- **Trimestral**: Benchmarking baseline (30 mins) para detectar regresiones

### ¿Puedo compartir resultados de benchmarking?

**Respuesta**: Sí. Cada `run` añade una línea JSON por medición a `<out>/results.jsonl` (sin contraseñas). Guarda ese
fichero y la salida de `summarize` en la carpeta de la sesión (`.ai/sessions/<fecha>-performance-audit-dump/`), junto al
informe que los cita.

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

1. **Primer paso recomendado**: capturar la línea base con el banco real (ver «Uso del banco de rendimiento»).
   ```bash
   python scripts/bench_dump.py setup --engines postgresql --volume small
   python scripts/bench_dump.py run --engines postgresql --variants baseline --volume small --repeat 3 --out bench_results/dump
   python scripts/bench_dump.py summarize bench_results/dump/results.jsonl
   ```

2. **Luego, solicitar auditoría**:
   ```
   @Performance Auditor
   (Ver Opción A arriba)
   ```

3. **Implementar mejoras fase a fase** según roadmap del informe.

---

*Guía actualizada: 2026-09-24 | Versión: 1.0*
