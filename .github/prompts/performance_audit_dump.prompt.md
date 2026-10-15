# Performance Audit Prompt — Módulo `dump` de util_bbdd

**Nivel**: Arquitecto de Software Senior (Expertise: Python, Base de Datos, Rendimiento)
**Objetivo Principal**: Auditar el módulo `dump` (volcado de datos masivos) e identificar oportunidades de mejora de rendimiento para maximizar velocidad de carga.
**Objetivo Secundario**: Verificar que los cambios propuestos mantengan compatibilidad con múltiples dialectos (PostgreSQL, MySQL/MariaDB, Oracle, SQL Server, SQLite).

Agente: Performance Auditor. Flujo operativo en 5 fases: `.github/prompts/performance_audit_dump_agent.prompt.md`.
Guía: `.claude/performance-audit-guide.md` (cuellos CB1–CB8) y `docs/guides/performance_audit_guide.md`.

> ⚠️ **Pre-requisito**: Antes de auditar rendimiento de dump, consultar `.github/prompts/engine_readiness_integration.prompt.md`
> para validar que los engines origen **y destino** están correctamente configurados mediante `EngineReadinessAdvisor`.
> Esto es crítico para volcados masivos (evita timeouts, lost connections, pool exhaustion).

## Inputs requeridos

- **Objetivo**: áreas a optimizar (`lectura` | `constraints` | `indexes` | `todas`)
- **Baseline**: ¿hay medición previa? Si no, capturarla primero con `scripts/bench_dump.py` (sí/no)
- **Dialects**: `PostgreSQL` | `MySQL` | `MariaDB` | `SQL Server` | `Oracle` | `SQLite` | `todas`
- **Volumen**: `small` (85k) | `medium` (850k) | `large` (3,5M) | otro
- **Timeline**: `ASAP` | `próxima semana` | `flexible`
- **Validación post-audit**: ¿medir con `scripts/bench_dump.py` tras las mejoras? (sí/no)

Si falta alguno, detente y aclara antes de la fase 1.

---

## Contexto del Módulo

### Propósito
El módulo `dump` en `src/util_bbdd/dump/` orquesta el volcado (copia masiva) de datos de un esquema/base de datos origen a otro. La carga es el caso de uso **crítico de rendimiento**: optimizar cada parte del pipeline es esencial para volúmenes grandes (millones de filas, gigabytes de datos).

### Arquitectura Actual (5 Fases)

```
Fase 1: Análisis de carga
  ├─ Introspección: tablas origen/destino, FKs
  ├─ Orden topológico: resolver dependencias FK
  └─ Validación: case-insensitive matching destino

Fase 2: Deshabilitar constraints en destino
  ├─ ConstraintManager: disable_all() por dialecto
  ├─ IndexManager (opcional): deshabilitar índices secundarios
  └─ Ventaja: acelera INSERTs evitando validaciones

Fase 3: Limpieza del destino
  ├─ TRUNCATE (rápido) vs. DELETE (si FK entrantes en SQL Server)
  └─ Reintento automático si TRUNCATE falla

Fase 4: Carga de datos (tabla por tabla)
  ├─ Lectura origen: pd.read_sql(chunksize=chunk_size)
  ├─ Transformación: renombrado de columnas, casting
  ├─ Inserción destino: BulkCrud → bulk_insert_from_chunks()
  ├─ Paralelización opcional (Incremento 3b): ParallelBulkLoader con rangos PK
  └─ Best-effort: continúa ante errores por tabla

Fase 5: Post-carga
  ├─ Rehabilitar constraints + sincronizar PKs
  ├─ Reconstruir índices
  └─ Generar informe Excel (auditoría, columnas faltantes, ciclos FK)
```

### Componentes Clave

| Componente | Ubicación | Responsabilidad |
|---|---|---|
| **DumpOrchestrator** | `orchestrator.py` | Orquestación: coordina las 5 fases, maneja threading |
| **ConstraintManager** | `_constraints.py` | Disable/enable constraints por dialecto |
| **IndexManager** | `_indexes.py` | Gestión de índices secundarios (rebuild/recreate) |
| **DumpConfig** | `_models.py` | Configuración: tablas, chunk_size, output_dir, parallelismo |
| **ParallelBulkLoader** | `bulk/` (módulo sep.) | Carga paralela por rangos PK (Incremento 3b) |
| **BulkCrud** | `bulk/` (módulo sep.) | Inserción atómica por chunks con rollback |
| **DumpReporter** | `reporters.py` | Generación Excel: auditoría, volumetría, errores |

### Configuraciones Críticas de Rendimiento

```python
DumpConfig:
  chunk_size: int = 5000           # Filas por chunk (lectura + inserción)
  parallel_pk_ranges: int = 1      # Paralelismo de carga por rango PK (0..CPU_COUNT)
  bulk_audit_path: Path | None     # Auditoría de cambios (puede ralentizar)
  collect_row_counts: bool = True  # Contar filas origen/destino (IO extra)
  truncate_target: bool = True     # Limpiar destino (ej. TRUNCATE vs. DELETE)
```

---

## Scope de Auditoría

### **A) Análisis de Flujo Actual y Cuellos de Botella**

**Leer y analizar:**

1. **`orchestrator.py`**:
   - `run()`: orquestación de fases
   - `_process_table()` + `_process_table_with_columns()`: lógica tabla individual
   - `_load_whole_table()`: flujo de lectura/escritura sin paralelismo
   - `_load_in_pk_ranges()`: paralelismo por rangos PK (si activado)
   - `_warn_chunk_size()`: advertencias actuales MariaDB/MySQL
   - Intros doctring: explicación de decisiones de diseño

2. **`_constraints.py`**:
   - `disable_all()`: impacto de desactivar constraints (¿cuántas queries?)
   - Métodos dialecto-específicos: `_disable_mariadb()`, `_disable_sqlserver()`, etc.
   - ¿Se pueden batchar las queries?

3. **`_indexes.py`** (si existe):
   - Estrategia de rebuild vs. recreate
   - ¿Se pueden deshabilitar índices de forma más eficiente?

4. **`_models.py`**:
   - `DumpConfig`: decisiones de valores default
   - ¿Falta algún parámetro de sintonización?

5. **`_sql_utils.py`**:
   - Funciones de quoting: ¿hay overhead?

6. **`reporters.py`**:
   - Generación Excel: ¿impacta en rendimiento de carga?

**Identificar:**
- Lecturas/escrituras no necesarias o redundantes
- Queries N+1 en introspección o desactivación de constraints
- Overhead de auditoría (`bulk_audit_path`)
- Conteos de filas innecesarios (`collect_row_counts`)

---

### **B) Benchmarking y Análisis de Rendimiento**

**Ejecutar y profundizar:**

1. **Escenarios de carga existentes**:
   - Revisar `bench_results/` (si hay datos de sesiones anteriores)
   - Identificar configuraciones testeadas, volúmenes, tiempos
   - Detectar regresiones o anomalías

2. **Profiling localizado** (sin cambiar código):
   - ¿Dónde pasa más tiempo?: lectura origen, transformación, inserción destino, constraints, índices?
   - `timeit` / `cProfile` en métodos críticos:
     - Lectura pandas: `pd.read_sql(chunksize=...)`
     - Transformación: renombrado de columnas, tipo de dato casting
     - Inserción: `BulkCrud.bulk_insert_from_chunks()`
     - Disable/enable constraints

3. **Análisis de memoria**:
   - ¿Hay retención de DataFrames grandes? (streaming vs. materialización)
   - Streaming correctamente con `chunksize`?

4. **Dialecto-específico**:
   - SQL Server: ¿BULK INSERT más eficiente que sqlalchemy?
   - PostgreSQL: ¿COPY es mejor que INSERT?
   - MySQL/MariaDB: ¿LOCAL INFILE o fast batches?
   - Oracle: ¿SQL Loader o direct path?

---

### **C) Cuellos de Botella Conocidos (Hipótesis a Validar)**

1. **Lectura origen lenta** (pandas + SQLAlchemy):
   - ¿chunk_size es óptimo? (defecto 5000)
   - ¿Hay indices en origen? ¿Se usan?
   - ¿Conexión de origen está en pool o dedicada?

2. **Transformación y casting** (renombrado de columnas):
   - ¿Se hace por fila o por chunk?
   - ¿Hay conversión de tipo costosa? (p.ej. string → timestamp)

3. **Inserción destino lenta**:
   - ¿SQLAlchemy es overhead vs. SQL nativo?
   - ¿bulk_insert_from_chunks() reutiliza prepared statements?
   - ¿Transactions grandes o micro-transacciones?

4. **Desactivación de constraints** (Fase 2):
   - ¿Cada constraint dispara una query? (N+1)
   - ¿Se puede hacer más eficientemente por dialecto?

5. **Sincronización PK y re-habilitación de índices** (Fase 5):
   - ¿Se ejecutan en serie? ¿Se pueden paralelizar?
   - ¿Rebuild de índices es cuello de botella?

6. **Conteo de filas** (`collect_row_counts=True`):
   - ¿Antes y después de cada tabla?
   - ¿COUNT(*) es innecesario en volúmenes grandes?

7. **Auditoría** (`bulk_audit_path`):
   - ¿Logging/escritura ralentiza la carga?
   - ¿Se puede activar solo en modo debug?

---

### **D) Mejoras Concretas a Auditar/Proponer**

#### **D.1 Optimizaciones de Lectura (Origen)**

- [ ] **Chunk size dinámico** (heurística basada en columnas, tamaño de fila estimado)
- [ ] **Índices en origen**: ¿se sugieren en docs? ¿se podrían auto-detectar?
- [ ] **Pool de conexiones origen**: verificar configuración (size, timeout, overflow)
- [ ] **Lectura con cursor servidor** (PostgreSQL) en lugar de fetch all
- [ ] **Query hints SQL** para lecturas masivas (p.ej. NOLOCK en SQL Server)
- [ ] **Columnas BLOB/TEXT**: excluir de lectura si no se necesitan

#### **D.2 Optimizaciones de Escritura (Destino)**

- [ ] **SQL nativo** por dialecto vs. SQLAlchemy:
  - SQL Server: `BULK INSERT` + `BCP.exe` o Direct Path
  - PostgreSQL: `COPY` via conexión nativa
  - MySQL/MariaDB: `LOAD DATA INFILE` / `INSERT INTO ... SELECT`
  - Oracle: `SQL*Loader` o `INSERT /*+ APPEND */`
  - SQLite: WAL mode, PRAGMA synchronous, PRAGMA cache_size

- [ ] **Prepared statements** reutilización (¿las reutiliza BulkCrud?)
- [ ] **Batch sizes** optimales por dialecto (¿defecto 5000 es óptimo?)
- [ ] **Transacciones**: tamaño (¿por chunk o por tabla?)
- [ ] **Identity inserts**: desactivar si PK es auto, reactivar tras carga
- [ ] **Índices**: deshabilitar ANTES de carga (Fase 2), rebuild DESPUÉS (Fase 5)

#### **D.3 Paralelización Mejorada**

- [ ] **Paralelismo tabla-nivel** (ThreadPoolExecutor): ¿worker threads suficientes?
- [ ] **Paralelismo PK-range** (ParallelBulkLoader): ¿range distribution es equitativa?
- [ ] **Límite de workers**: ¿CPU count es correcto? ¿disk I/O es bottleneck?
- [ ] **Sincronización de threads**: ¿hay contención en pool de conexiones destino?

#### **D.4 Gestión de Constraints e Índices**

- [ ] **Batch disable/enable**: ¿se pueden agrupar por tabla?
- [ ] **Foreign Keys**: desactivar, reload data, reactivar (vs. ON DELETE CASCADE)
- [ ] **Check constraints**: eliminar DDL y recrear post-carga?
- [ ] **Índices secundarios**: rebuild vs. recreate trade-off
- [ ] **Estadísticas**: `ANALYZE`, `DBCC RECOMPUTE`, etc. post-carga

#### **D.5 Reducción de Overhead**

- [ ] **collect_row_counts**: ¿siempre necesario? → opción para desactivar
- [ ] **bulk_audit_path**: auditoría lazy o asíncrona
- [ ] **Introspección**: cachear resultados Inspector (no es thread-safe, pero se puede precalcular)
- [ ] **Logging**: niveles DEBUG vs. INFO vs. WARNING

#### **D.6 Configuración de Motor (Dialecto-Específico)**

**SQL Server:**
- `BULK INSERT` con `BATCHSIZE`, `TABLOCK`, `ROWS_PER_BATCH`
- `SET NOCOUNT ON` para reducir overhead de conteo de filas
- `ALTER DATABASE SET RECOVERY SIMPLE` (dev/test)
- Índices: deshabilitar NONCLUSTERED antes de carga

**PostgreSQL:**
- `COPY` en lugar de INSERT (órdenes de magnitud más rápido)
- `work_mem` aumentado para sorts
- `maintenance_work_mem` para índices
- `fsync=off` + `synchronous_commit=off` (dev/test)
- Desactivar triggers con `ALTER TABLE ... DISABLE TRIGGER ALL`

**MySQL/MariaDB:**
- `LOAD DATA INFILE` (local en cliente)
- `max_allowed_packet` aumentado (si TEXT/BLOB)
- `innodb_flush_log_at_trx_commit=2`
- Desactivar chequeo de FK: `SET FOREIGN_KEY_CHECKS=0`
- Índices: `DISABLE KEYS` / `ENABLE KEYS`

**Oracle:**
- `SQL*Loader` o direct path INSERT
- `ALTER SESSION SET COMMIT_LOGGING=NOARCHIVELOG`
- Desactivar constraints: `ALTER TABLE ... DISABLE CONSTRAINT`
- Estadísticas: `DBMS_STATS.GATHER_TABLE_STATS` post-carga

**SQLite:**
- `PRAGMA synchronous = OFF`
- `PRAGMA journal_mode = WAL`
- `PRAGMA cache_size = -10000` (MB)
- `PRAGMA temp_store = MEMORY`

---

### **E) Validación de Compatibilidad**

Asegurar que mejoras propuestas:

- [ ] Funcionan en **todos los dialectos soportados** (SQL Server, PostgreSQL, MySQL/MariaDB, Oracle, SQLite)
- [ ] Mantienen **backward compatibility** (DumpConfig no pierde parámetros)
- [ ] Se degradan elegantemente si dialecto no soporta optimización nativa
- [ ] Tests pasan sin regresión en `tests/unit/` (si existen)
- [ ] Documentación (`docs/`) se actualiza con nuevas opciones

---

### **F) Métricas de Éxito**

Definir benchmarks para validar mejoras:

| Métrica | Benchmark Actual | Target | Método |
|---|---|---|---|
| **Throughput** | filas/seg (origen) | +20-50% | Medir con volumes 100K-1M filas |
| **Latencia tabla** | tiempo total (tabla) | -10-30% | Cronometrar fases individuales |
| **Memory peak** | MB (max RSS) | -20% | `memory_profiler` |
| **CPU utilization** | % (promedio) | +10% (aprovechar paralelismo) | `psutil` |
| **Disk I/O** | IOPS / MB/s | Medir baseline | Herramientas SO (iostat, perfmon) |

---

## Entregables Esperados

### 1. **Informe de Auditoría** (formato: Markdown + diagramas)

- Resumen ejecutivo: hallazgos clave + impacto estimado
- Arquitectura actual vs. cuellos de botella (diagrama de flujo)
- Benchmarks de referencia (si se ejecutan)
- Hallazgos ordenados por: **impacto ✕ esfuerzo**

### 2. **Propuestas de Mejora** (con priorización)

| ID | Mejora | Dialecto | Impacto Est. | Esfuerzo | Riesgo | Notas |
|---|---|---|---|---|---|---|
| P1 | Batch disable constraints | Todos | +15% | Bajo | Bajo | Quick win |
| P2 | SQL COPY/BULK nativo | PostgreSQL/MSSQL | +30% | Alto | Medio | Requiere fallback |
| P3 | Chunk size dinámico | Todos | +5% | Medio | Bajo | Heurística columnas |
| ... | | | | | | |

### 3. **Recomendaciones de Configuración**

- DumpConfig defaults recomendados por dialecto
- Guía de sintonización (chunk_size, workers, audit level)
- Best practices de pre/post carga (índices, estadísticas)

### 4. **Roadmap de Implementación** (fases)

- **Fase Inmediata** (quick wins, bajo riesgo): mejoras P1, P3, ...
- **Fase Mediano Plazo** (medio riesgo, alto impacto): mejoras P2, ...
- **Fase Largo Plazo** (refactorización mayor, validación exhaustiva): ...

### 5. **Pruebas Propuestas**

- Benchmarks de referencia a ejecutar (scripts pytest + datasets)
- Verificación de backward compatibility
- Casos de regresión a vigilar

---

## Contexto: util_bbdd

- **Repo**: https://github.com/fmanza/util_bbdd
- **Ubicación módulo**: `src/util_bbdd/dump/`
- **Estructura archivos**:
  ```
  dump/
    __init__.py             (re-exportaciones públicas)
    orchestrator.py         (DumpOrchestrator: núcleo)
    _models.py              (DumpConfig, DumpResult, ...)
    _constraints.py         (ConstraintManager: disable/enable)
    _indexes.py             (IndexManager: deshabilitar/rebuild índices)
    _sql_utils.py           (quote_identifier, quote_table)
    _source_reader.py       (lectura del origen: cursor por driver, prefetch, lotes)
    _fk_graph.py            (orden de carga por FK)
    _audit_summary.py       (resumen del CSV de auditoría)
    reporters.py            (DumpReporter: informe Excel)
  ```
- **Dependencias críticas**:
  - `util_bbdd.bulk`: BulkCrud, ParallelBulkLoader (inserción masiva)
  - SQLAlchemy: Engine, Inspector, introspección
  - Pandas: lectura SQL con chunksize
- **Versión Python**: >= 3.12
- **Dialectos soportados**: PostgreSQL, MySQL/MariaDB, Oracle, SQL Server, SQLite

---

## Restricciones y Consideraciones

1. **No refactorizar la API pública** (DumpConfig, DumpOrchestrator.run() deben ser compatibles)
2. **Mantener soporte de múltiples dialectos** (sin romper algunos para mejorar otros)
3. **Testing debe pasar**: auditoría no incluye cambios de código, solo recomendaciones
4. **Documentación vigente**:
   - README.md
   - docs/functional/, docs/api/ (si existen módulos dump)
   - Docstrings en código
5. **Puedes consultar fuentes externas** (webs oficiales de bases de datos, blogs, papers sobre rendimiento masivo)

---

## Enfoque Recomendado

1. **Fase 1 — Lectura y Análisis** (1-2 hrs):
   - Leer orchestrator.py completo, entender flujo
   - Revisar _constraints.py, _indexes.py, _models.py
   - Estudiar BulkCrud/ParallelBulkLoader en bulk/

2. **Fase 2 — Identificación de Cuellos de Botella** (1-2 hrs):
   - Perfil hipotético: si tienes datos de benchmarks, analizar
   - Comparar con best practices conocidas (BULK INSERT, COPY, etc.)
   - Documentar supuestos y preguntas sin respuesta

3. **Fase 3 — Propuestas** (1-2 hrs):
   - Listar mejoras concretas ordenadas por impacto/esfuerzo
   - Incluir ejemplos de código (pseudocódigo o snippets)
   - Validar compatibilidad dialecto-específica

4. **Fase 4 — Informe Final** (0.5-1 hrs):
   - Consolidar hallazgos + propuestas
   - Diagramas y tablas de priorización
   - Recomendaciones de testing/benchmarking

---

## Referencias Útiles

- **SQLAlchemy Best Practices**: https://docs.sqlalchemy.org/
- **Database-Specific Bulk Loading**:
  - PostgreSQL COPY: https://www.postgresql.org/docs/current/sql-copy.html
  - SQL Server BULK INSERT: https://learn.microsoft.com/en-us/sql/t-sql/statements/bulk-insert-transact-sql
  - MySQL LOAD DATA: https://dev.mysql.com/doc/refman/8.0/en/load-data.html
  - Oracle SQL*Loader: https://docs.oracle.com/cd/B19306_01/server.102/b14215/ldr_concepts.htm
- **Pandas read_sql Performance**: https://pandas.pydata.org/docs/user_guide/io.html
- **Connection Pooling**: https://docs.sqlalchemy.org/en/20/core/pooling.html
- **Python Profiling**: `cProfile`, `timeit`, `memory_profiler`, `py-spy`

---

*Generado para auditoría de rendimiento de util_bbdd.dump — Enfoque: maximizar throughput de carga masiva de datos.*
