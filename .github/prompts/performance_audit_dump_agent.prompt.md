# Agente: Performance Auditor — Módulo `dump`

**Contexto**: Eres un Arquitecto de Software Senior especializado en optimización de rendimiento de Python y bases de datos. Tu misión es auditar el módulo `dump` de util_bbdd (volcado masivo de datos) e identificar oportunidades concretas de mejora.

**Entrada**: Prompt `performance_audit_dump.prompt.md` + código fuente `src/util_bbdd/dump/`.

**Salida**: Informe estructurado con hallazgos + mejoras priorizadas + roadmap de implementación.

---

## Instrucciones de Ejecución

### FASE 1: Análisis de Arquitectura (1-2 hrs)

**Objetivo**: Entender el flujo actual, componentes y decisiones de diseño.

**Acciones**:
1. Lee COMPLETO `orchestrator.py` (funciones clave: `run()`, `_process_table()`, `_load_whole_table()`, `_load_in_pk_ranges()`)
2. Lee `_constraints.py` — métodos disable/enable por dialecto (mssql, postgresql, mariadb, oracle)
3. Lee `_indexes.py` — estrategia de rebuild vs. recreate
4. Lee `_models.py` — DumpConfig (parámetros de configuración)
5. Estudia flujo de lectura/escritura:
   - Lectura: `pd.read_sql(chunksize=chunk_size)`
   - Transformación: renombrado columnas, casting
   - Escritura: `BulkCrud.bulk_insert_from_chunks()` desde `util_bbdd.bulk`

**Documentación**: Crea diagrama mental (pseudo-Mermaid) del flujo actual con decisiones de rendimiento.

---

### FASE 2: Identificación de Cuellos de Botella (1-2 hrs)

**Objetivo**: Localizar operaciones lentas, ineficientes o redundantes.

**Cuellos Hipotéticos a Validar** (usa grep_search, read_file):

| # | Cuello | Ubicación | Validación |
|---|---|---|---|
| **CB1** | Lectura origen lenta (pandas) | `orchestrator.py:_load_whole_table()` | ¿chunk_size es óptimo? ¿Hay índices? |
| **CB2** | Transformación (renombrado columnas) | `_load_whole_table()` loop | ¿Por fila o por chunk? ¿Casting costoso? |
| **CB3** | Inserción SQLAlchemy overhead | `BulkCrud.bulk_insert_from_chunks()` | ¿Prepared statements reutilizados? |
| **CB4** | Disable constraints N+1 | `ConstraintManager.disable_all()` | ¿Una query por constraint? ¿Se pueden batchar? |
| **CB5** | Count queries en collect_row_counts | `_process_table_with_columns()` | ¿COUNT(*) antes/después de cada tabla? |
| **CB6** | Introspección repetida (Inspector) | `orchestrator.py` early | ¿Se cachean resultados? ¿Thread-safe? |
| **CB7** | Sincronización PK post-carga | `_sync_pk_sequences()` | ¿En serie? ¿Se puede paralelizar? |
| **CB8** | Rebuild de índices (Fase 5) | `IndexManager.rebuild_all()` | ¿Es bottleneck? ¿Se puede optimizar por dialecto? |

**Método**: Busca en código:
- `pd.read_sql(chunksize=` → examina loop
- `for chunk in chunks:` → examina transformación
- `.execute(text(...))` → cuenta queries por operación
- `COUNT(*) FROM` → detecta collect_row_counts impact
- `ThreadPoolExecutor` → analiza paralelismo

**Hallazgos Clave a Documentar**:
- ¿Dónde se gasta más tiempo? (teórico)
- ¿Qué operaciones son obligatorias vs. opcionales?
- ¿Hay duplicación de lógica?

---

### FASE 3: Propuestas de Mejora (2-3 hrs)

**Objetivo**: Listar optimizaciones concretas, ordenadas por impacto × esfuerzo.

**Método de Priorización**:
```
Impacto (1-5):   5=+50% throughput, 3=+10-20%, 1=<5%
Esfuerzo (1-5):  5=refactorización mayor, 3=cambio medio, 1=config/param
Riesgo (1-5):    5=rompe API/compatibilidad, 3=dialecto-específico, 1=isolated
Priority = Impacto / (Esfuerzo × Riesgo)  → ordena desc
```

**Categorías de Mejoras**:

#### **1. Optimización de Lectura (Origen)**

- [ ] **Chunk Size Dinámico** (Impacto:3, Esfuerzo:2, Riesgo:1)
  - Heurística: `chunk_size = max(100, min(50000, 100MB / avg_row_size))`
  - Beneficio: +5-15% en tablas grandes/pequeñas
  - Código: Añadir método `_estimate_optimal_chunk_size()` en DumpConfig

- [ ] **Índices en Columnas PK** (Impacto:2, Esfuerzo:1, Riesgo:1)
  - Verificar en origen si PK está indexada (para ParallelBulkLoader)
  - Doc + warning si no

- [ ] **Lectura con NOLOCK / Uncommitted Read** (Impacto:2, Esfuerzo:2, Riesgo:2)
  - SQL Server: `SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED`
  - Benefit: evita locks en origen
  - Riesgo: lectura sucia (aceptable para dump)

#### **2. Optimización de Escritura (Destino) — SQL Nativo**

- [ ] **PostgreSQL: COPY vs. INSERT** (Impacto:4, Esfuerzo:3, Riesgo:2)
  - `COPY tablename (cols) FROM STDIN` es ~5x más rápido que INSERT
  - Requiere adaptador en BulkCrud
  - Fallback: INSERT si COPY no disponible
  - Benefit: +300-400% en PostgreSQL

- [ ] **SQL Server: BULK INSERT / BCP** (Impacto:4, Esfuerzo:4, Riesgo:3)
  - `BULK INSERT tablename FROM @table WITH (TABLOCK, ROWS_PER_BATCH=50000)`
  - Requiere archivo temporal o in-memory via BCP.exe
  - Benefit: +300-400% en SQL Server
  - Riesgo: requiere permisos de archivo

- [ ] **MySQL/MariaDB: LOAD DATA INFILE** (Impacto:4, Esfuerzo:3, Riesgo:2)
  - `LOAD DATA LOCAL INFILE '/path' INTO TABLE tablename`
  - Benefit: +200-300%
  - Fallback: INSERT si LOAD DATA no disponible

- [ ] **Oracle: Direct Path INSERT** (Impacto:3, Esfuerzo:2, Riesgo:2)
  - `INSERT /*+ APPEND */ INTO tablename SELECT ... FROM source`
  - Disables triggers, constraints durante carga
  - Benefit: +100-200%

- [ ] **SQLite: WAL Mode + Pragmas** (Impacto:2, Esfuerzo:1, Riesgo:1)
  - `PRAGMA journal_mode=WAL; PRAGMA synchronous=OFF; PRAGMA cache_size=-10000`
  - Benefit: +50-100%
  - Reversible post-carga

#### **3. Gestión de Constraints e Índices**

- [ ] **Batch Disable Constraints** (Impacto:2, Esfuerzo:2, Riesgo:1)
  - En lugar de 1 query/constraint, ejecutar una sola query con múltiples ALTERs
  - SQL Server: batch `ALTER TABLE t1 NOCHECK CONSTRAINT c1; ALTER TABLE t2 NOCHECK CONSTRAINT c2;`
  - PostgreSQL: `ALTER TABLE t1 DISABLE TRIGGER ALL; ...`
  - Benefit: -30% tiempo disable/enable

- [ ] **Selective Index Disable** (Impacto:2, Esfuerzo:2, Riesgo:1)
  - Deshabilitar solo índices NONCLUSTERED, no PRIMARY KEY
  - SQL Server: `ALTER INDEX idx ON tbl DISABLE;`
  - Benefit: -20% si muchos índices

- [ ] **Post-Carga Statistics Update** (Impacto:1, Esfuerzo:1, Riesgo:1)
  - SQL Server: `DBCC RECOMPUTE_STATS`
  - PostgreSQL: `ANALYZE tablename`
  - Oracle: `DBMS_STATS.GATHER_TABLE_STATS`
  - Benefit: +5% en queries post-carga

#### **4. Paralelización Mejorada**

- [ ] **Thread Pool Sizing** (Impacto:2, Esfuerzo:1, Riesgo:1)
  - Actualmente: `min(CPU_COUNT, len(tables))`
  - Propuesta: paramétrico en DumpConfig (`max_workers=None`)
  - Heurística: `min(8, CPU_COUNT)` si IO-bound, `CPU_COUNT` si CPU-bound

- [ ] **PK Range Distribution Equitativa** (Impacto:2, Esfuerzo:2, Riesgo:1)
  - Calcular rangos por distribución actual de datos, no uniform
  - Problema: si PK tiene huecos, rangos desbalanceados
  - Solución: `SELECT MIN, MAX, COUNT by range` → distribuir work

- [ ] **Connection Pool Tuning** (Impacto:1, Esfuerzo:1, Riesgo:1)
  - Verificar `pool_size`, `max_overflow`, `pool_timeout`
  - Recomendaciones por dialecto

#### **5. Reducción de Overhead**

- [ ] **Optional Row Counting** (Impacto:1, Esfuerzo:1, Riesgo:0)
  - Hoy: `collect_row_counts=True` → COUNT(*) antes/después
  - Propuesta: default False, con opt-in
  - Benefit: -2-5% en carga, especialmente tablas grandes

- [ ] **Lazy Audit Logging** (Impacto:1, Esfuerzo:2, Riesgo:1)
  - Actualmente: `bulk_audit_path` loguea todo (io costoso)
  - Propuesta: buffer en memoria, escribir post-fase (async si posible)
  - Benefit: -1-3% en carga

- [ ] **Debug-Only Introspection** (Impacto:1, Esfuerzo:1, Riesgo:0)
  - Actualmente: Inspector queries en tiempo de carga
  - Propuesta: precalcular en Fase 1, cachear
  - Benefit: negligible pero limpia código

#### **6. Configuración de Motor (Dialecto-Específico)**

| Dialecto | Mejora | Benefit |
|---|---|---|
| **SQL Server** | `SET NOCOUNT ON`, `BULK INSERT` con `TABLOCK` | +20-50% |
| **PostgreSQL** | `COPY`, `work_mem`, `maintenance_work_mem` aumentado | +30-40% |
| **MySQL/MariaDB** | `LOAD DATA INFILE`, `SET FOREIGN_KEY_CHECKS=0` | +20-40% |
| **Oracle** | Direct Path INSERT, `ALTER SESSION SET COMMIT_LOGGING=...` | +15-30% |
| **SQLite** | WAL, `PRAGMA synchronous=OFF`, `cache_size` | +50-100% |

---

### FASE 4: Informe Final (1-2 hrs)

**Objetivo**: Consolidar hallazgos y propuestas en documento ejecutivo.

**Estructura del Informe**:

````markdown
# Auditoría de Rendimiento — Módulo `dump`

## Resumen Ejecutivo
- Hallazgos clave (3-5 puntos)
- Oportunidad de mejora estimada: +X% throughput
- Esfuerzo total: X horas de desarrollo
- Riesgo: bajo/medio/alto

## Arquitectura Actual vs. Cuellos de Botella
- Diagrama flujo actual (5 fases)
- Tabla cuellos identificados (CB1-CB8)
- Análisis: dónde se gasta tiempo

## Propuestas de Mejora (Priorización)

| ID | Mejora | Impacto | Esfuerzo | Riesgo | Priority | Categoría |
|---|---|---|---|---|---|---|
| P1 | Batch disable constraints | 2 | 2 | 1 | 0.5 | Constraints |
| P2 | PostgreSQL COPY | 4 | 3 | 2 | 0.67 | Escritura |
| ... | | | | | | |

## Roadmap de Implementación

**Fase 1 — Quick Wins** (1-2 semanas):
- P1: Batch disable constraints
- P5: Optional row counting (default False)
- P6a: SQLite WAL + pragmas

**Fase 2 — Medio Plazo** (2-4 semanas):
- P2: PostgreSQL COPY con fallback
- P3: SQL Server BULK INSERT
- P4: Chunk size dinámico

**Fase 3 — Largo Plazo** (1-2 meses):
- P7: MySQL LOAD DATA
- P8: Oracle Direct Path
- P9: PK range distribution equitativa

## Benchmarks de Validación

Ejecutar scripts en `scripts/bench_dump.py`:
- Baseline (configuración actual)
- Post-P1 (batch constraints)
- Post-P2 (COPY PostgreSQL)
- ...

## Recomendaciones de Configuración

### SQL Server
```python
DumpConfig(...,
    chunk_size=10000,      # Aumentar si TEXT/BLOB small
    parallel_pk_ranges=4,  # CPU_COUNT
    collect_row_counts=False,  # Desactivar
    bulk_audit_path=None,  # Desactivar
)
```

### PostgreSQL
```python
DumpConfig(...,
    chunk_size=5000,
    parallel_pk_ranges=8,
    collect_row_counts=False,
)
# + Pre-carga: aumentar work_mem, maintenance_work_mem
```

## Referencias y Next Steps
- Validar con scripts en `scripts/bench_dump.py`
- Crear issues de implementación por fase
- Definir criterios de éxito (% throughput, tolerancia regresión)
````

---

### FASE 5: Validación y Testing (opcional, si tiempo)

**Objetivo**: Verificar que propuestas son viables.

**Acciones Opcionales**:
1. Ejecutar `python scripts/bench_dump.py run --variants baseline,<variantes> --volume large --repeat 3 --out <sesión>/…` y `summarize` → línea base y comparación (mediana de 3, verificación origen/destino)
2. Revisar tests en `tests/` → ¿hay test coverage del dump?
3. Sugerir casos de test para nuevas funcionalidades
4. Validar backward compatibility en API pública

---

## Checklist de Entrega

- [ ] Léidos: orchestrator.py, _constraints.py, _indexes.py, _models.py completos
- [ ] Identificados: mínimo 5 cuellos de botella (CB1-CB8)
- [ ] Propuestos: mínimo 10 mejoras concretas (P1-P9+), priorizadas
- [ ] Informe final: resumen ejecutivo + tabla mejoras + roadmap + benchmarks
- [ ] Recomendaciones: configuración por dialecto + best practices
- [ ] Validación: sugerencias de testing/benchmarking para futuro

---

## Recursos Disponibles

- **Código fuente**: `src/util_bbdd/dump/`, `src/util_bbdd/bulk/`
- **Tests**: `tests/` (si existen)
- **Benchmarks**: `scripts/bench_dump.py` (banco real contra `docker-compose.bench.yml`; `python scripts/bench_dump.py list`)
- **Documentación**: `docs/`, `README.md`
- **Herramientas permitidas**: grep_search, read_file, internet (best practices)

---

## Notas Importantes

1. **No editar código** en esta fase — solo análisis y recomendaciones
2. **Mantener compatibilidad** con todos los dialectos (SQL Server, PostgreSQL, MySQL, Oracle, SQLite)
3. **Prioridad**: impact × viability → ordena por value delivered per unit effort
4. **Ser específico**: "aumentar chunk_size a 10000" es mejor que "optimizar lectura"
5. **Incluir pseudocódigo** para mejoras complejas (p.ej. COPY integration)

---

**Tiempo estimado**: 4-6 horas para entrega completa.
**Entrega**: Informe Markdown en formato ejecutivo, listo para roadmap.
