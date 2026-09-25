# Prompt: Auditoría de Rendimiento — Módulo `bulk`

**Rol**: Arquitecto de software senior experto en Python y optimización de carga de datos
**Objetivo**: Auditar el módulo `src/util_bbdd/bulk/` para proponer mejoras de rendimiento en carga masiva de datos
**Scope**: Velocidad de inserción, batching, particionamiento, I/O, memoria, SQL execution planning

---

## 📋 Inputs requeridos

Antes de ejecutar, confirma que dispones de:

- ✅ **Módulo objetivo**: `src/util_bbdd/bulk/` (crud.py, audit.py, normalize.py, _execution/, _support/)
- ✅ **Contexto de operación**: entornos de prueba (SQLite, MySQL, PostgreSQL, Oracle, SQL Server)
- ✅ **Conjuntos de datos de benchmark**: tamaños típicos (1K, 10K, 100K, 1M registros)
- ✅ **Restricciones conocidas**: ¿hay limpieza de identidades, auditoría, validación?
- ✅ **Métricas de partida**: tiempo base de INSERT/UPDATE/DELETE (si disponible)

Si falta alguno, decláralos como supuesto explícito antes de continuar.

---

## 🔍 Áreas de auditoría

### 1. **Estrategia de batching y lotes (I/O bound)**
   - Tamaño de lote configurable vs. fijo
   - Número de sentencias SQL por lote
   - Compresión de bind parameters
   - Reutilización de prepared statements
   - **Referencia de internet**: Buscar "SQLAlchemy bulk insert best practices", "batch size tuning for different databases"

### 2. **Particionamiento y paralelización (_execution/)**
   - `ParallelBulkLoader` — ¿usa thread pool o asyncio? ¿Número de workers óptimo?
   - `RangePartitioner`, `HashPartitioner` — ¿distribución equilibrada?
   - Contención de conexiones vs. paralelismo real
   - Overhead de creación de particiones vs. ganancia de velocidad
   - **Referencia de internet**: Buscar "Python concurrent.futures thread pool sizing", "database connection pool optimization"

### 3. **Normalización SQL (_support/normalize.py)**
   - Escape de strings — ¿usa bind parameters o string interpolation?
   - Tipo inferencia — ¿hay conversiones redundantes (str→int→str)?
   - Memory footprint de normalización
   - **Referencia de internet**: Buscar "SQL injection vs bind parameters performance", "Python string formatting benchmarks"

### 4. **Gestión de conexiones**
   - Reuso de conexiones vs. creación nueva por lote
   - Connection pool exhaustion under load
   - Context manager cleanup cost
   - Transactiones largas vs. autocommit
   - **Referencia de internet**: Buscar "SQLAlchemy connection pooling strategies", "database transaction commit strategies"

### 5. **Auditoría integrada**
   - Costo de AuditManager por fila
   - Logging synchronous vs. async
   - Persistencia de auditoría — ¿bloquea INSERT principal?
   - Query de auditoría posterior vs. inline tracking
   - **Referencia de internet**: Buscar "database audit logging performance impact", "asynchronous logging patterns"

### 6. **Garbage collection y memoria**
   - DataFrame copia vs. vistas (in-place operations)
   - Deallocación de objetos intermedios
   - Memory leaks en bucles de batching
   - **Referencia de internet**: Buscar "Python memory profiling with tracemalloc", "pandas memory optimization"

### 7. **SQL generation overhead**
   - Compilación dinámica de INSERT/UPDATE/DELETE
   - CASE statements para UPDATE condicionales
   - OVERRIDE IDENTITY en SQL Server — overhead
   - **Referencia de internet**: Buscar "SQL Server identity override performance", "SQLAlchemy compilation cache"

### 8. **Database-specific optimizations**
   - **Oracle**: hint `APPEND`, parallel DML, batch sizes > 1000
   - **MySQL/MariaDB**: `INSERT ... ON DUPLICATE KEY UPDATE`, `LOAD DATA INFILE` simulation
   - **PostgreSQL**: `COPY FROM`, `ON CONFLICT DO UPDATE`
   - **SQL Server**: `BULK INSERT`, `MERGE`, table hints
   - **SQLite**: WAL mode, PRAGMA synchronous levels
   - **Referencia de internet**: Buscar "database-specific bulk insert optimization" por BBDD

### 9. **Synchronization de PKs (pk_sync.py)**
   - `PKSequenceSyncer` — ¿hay queries SELECT adicionales por fila?
   - Cache de sequences vs. roundtrips
   - Impacto en tiempo total si hay muchas PKs autonuméricas
   - **Referencia de internet**: Buscar "auto-increment key retrieval performance", "sequence caching strategies"

### 10. **Validation & error handling overhead**
   - `detect_always_identity_columns` — ¿costo de introspección?
   - Validación de datos por fila vs. por lote
   - Rollback cost en caso de error
   - **Referencia de internet**: Buscar "validation in bulk operations best practices"

---

## 📊 Deliverables esperados

### PLAN
- Mapa mental de flujo de carga actual (INSERT → batching → auditoría → persistence)
- Cuellos de botella teóricos identificados por área
- Estrategia de benchmark (qué medir, cómo reproducir)

### AUDIT_PLAN
- Validación de viabilidad de cada mejora (breaking changes, compatibilidad, riesgos)
- Pruebas propuestas por área (benchmarks, regression tests)
- Orden de ejecución (dependencias entre mejoras)

### AUDIT_CODE (Hallazgos)

Para cada hallazgo, reportar:

```markdown
### Hallazgo: [Nombre]
**Severidad**: CRÍTICA | ALTA | MEDIA | BAJA | INFO
**Área**: [1-10 de áreas arriba]
**Archivo/Función**: [ruta exacta + líneas]
**Descripción**: [qué es el problema y por qué afecta rendimiento]
**Impacto estimado**: [% mejora teórica si se soluciona]
**Confirmación**: [CONFIRMADA | HIPÓTESIS | DEPENDE_DE_BBDD]

#### Evidencia
- Código actual: [snippet]
- Referencia/benchmark: [link internet si aplica]
- Cálculo de impacto: [matemática o benchmarks comparativos]

#### Remediación propuesta
- Cambios de código: [diff conceptual]
- Tests requeridos: [qué verificar para no regresionar]
- Compatibilidad: [breaking changes, deprecations]
- Overhead de cambio: [complejidad, maintainability impact]
```

### VERSION
- Veredicto final: **CRÍTICO | SIGNIFICATIVO | MODERADO | LIMPIO**
- Resumen: top 5 mejoras de mayor impacto
- Quick wins (< 1h, 5%+ mejora, sin breaking changes)
- Fases de implementación recomendadas
- Métricas de éxito (antes/después en benchmark)

---

## 🎯 Criterios de prioridad

| Prioridad     | Criterio de entrada                                      | Impacto esperado | Riesgo     | Quick-win? |
|---------------|----------------------------------------------------------|------------------|------------|-----------|
| **CRÍTICA**   | > 50% slow-down, afecta todo INSERT/UPDATE/DELETE        | > 50%↑           | ALTO       | ❌        |
| **ALTA**      | 20-50% slow-down, común en cargas > 100K registros       | 20-50%↑          | MEDIO      | ⚠️        |
| **MEDIA**     | 5-20% slow-down, depende de BBDD/tamaño datos           | 5-20%↑           | BAJO       | ✅        |
| **BAJA**      | < 5% slow-down, optimización específica o edge case      | < 5%↑            | MUY BAJO   | ✅        |
| **INFO**      | Mejora de maintainability, sin impacto directo en tiempo | N/A              | NONE       | ✅        |

---

## ✅ Reglas obligatorias

1. **Emitir veredicto final**: CRÍTICO | SIGNIFICATIVO | MODERADO | LIMPIO (con justificación)
2. **Evidencias concretas**: archivo, función, línea de código exacta — NO hipótesis sin datos
3. **Diferenciar confirmado de hipótesis**: si no puedes probar directamente, marcar como [HIPÓTESIS]
4. **Consultar internet**: Buscar benchmarks, best practices, release notes de SQLAlchemy/pandas/databases actuales
5. **Compatibilidad y breaking changes**: Declarar explícitamente si la solución rompe backward compatibility
6. **Asumir contraints reales**: No proponer cambios que violen requisitos de auditoría, integridad o cross-BBDD
7. **No mezclar auditoría con implementación**: AUDIT_CODE es análisis; IMPLEMENT va en fase separada si se aprueba

---

## 🔗 Contexto compartido

- **Patrón de arquitectura**: niveles y capas de `.ai/architecture.md` § «Capas (Regla #6)»
- **Base de datos soportadas**: Oracle, MySQL/MariaDB, PostgreSQL, SQLite, SQL Server, HSQLDB
- **Frameworks**: SQLAlchemy core + Pandas
- **Python version**: 3.12+ (`requires-python` en `pyproject.toml`)
- **Objetivo negocio**: Carga de datos **lo más rápido posible**

---

## 🚀 Cómo usar este prompt

```markdown
**[En Copilot Chat o Claude Code]**

Eres un arquitecto de software senior experto en Python y optimización de BD.

Lee .github/prompts/performance_audit_bulk.prompt.md

Objetivo: Auditar src/util_bbdd/bulk/ para proponer mejoras de rendimiento.
Alcance: Velocidad de INSERT/UPDATE/DELETE masivos, batching, paralelización.
Conjuntos de datos: Benchmarks con 1K, 10K, 100K, 1M registros (si disponible).
Bases de datos: Oracle, MySQL, PostgreSQL, SQL Server, SQLite.
Restricciones: Mantener compatibilidad multi-BBDD y auditoría integrada.

Devuelve: PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION

Puedes consultar información en internet para best practices y benchmarks.
```

---

## 📚 Referencias sugeridas (búsquedas recomendadas)

- "SQLAlchemy bulk insert performance best practices 2024"
- "Python concurrent.futures thread pool optimal size database"
- "Database bulk load optimization Oracle MySQL PostgreSQL SQL Server"
- "Pandas to_sql performance tuning"
- "Connection pool sizing for concurrent database operations"
- "SQL audit logging async patterns"
- "Memory profiling Python bulk operations tracemalloc"
- "Database transaction commit strategies performance"

---

*Prompt v0.1 — Auditoría de rendimiento del módulo bulk*
*Creado: 2026-09-23*
