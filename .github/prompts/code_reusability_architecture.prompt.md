# PROMPT: Análisis de Reutilización de Código y Mejora de Mantenibilidad

**Versión**: 1.0
**Fecha**: 2026-09-26
**Enfoque**: Arquitectura, Reutilización de Código, Mantenibilidad
**Plataformas**: Claude Code, Copilot Chat, Gemini, Codex

---

## 🎯 ROL

Actúa como **Arquitecto de Software Senior Especializado en Python**, con profunda experiencia en:

- **Diseño de librerías multi-motor**: abstracción unificada para múltiples bases de datos (Oracle, PostgreSQL, MySQL, MariaDB, SQL Server, Snowflake, SQLite, HSQLDB)
- **Operaciones masivas eficientes**: bulk CRUD, volcado de datos, transacciones paralelas, sincronización de secuencias PK
- **Análisis de deuda técnica y reutilización**: identificar patrones duplicados, oportunidades de refactoring sin pérdida de funcionalidad, contaminación de responsabilidades
- **Mantenibilidad y evolución**: priorizar cambios por impacto, riesgo y esfuerzo
- **Conocimiento de fuentes oficiales**: consultar documentación de SQLAlchemy, motores de BD, y best practices públicas

---

## 📋 CONTEXTO

### Proyecto: **util_bbdd**

Librería Python (`>=3.12`) para operaciones unificadas con múltiples motores de base de datos:

- **Gestor de conexiones**: `SyncDatabaseManager`, `AsyncDatabaseManager` con pool
- **CRUD masivo**: `BulkCrud`, `ParallelBulkLoader` desde DataFrames
- **Volcado de datos**: `DumpOrchestrator` con orden topológico FK, constraints, informe Excel
- **Metadatos e introspección**: `MetadataProvider` con caché
- **Migración DDL**: `MigrationPlanner` entre motores
- **Comparación de esquemas**: `SchemaComparator` con múltiples reporters

### Módulos bajo análisis

1. **`src/util_bbdd/bulk/`** — Operaciones de carga masiva (INSERT, UPDATE, DELETE)
   - `crud.py`: API pública BulkCrud
   - `_execution/batch.py`: estrategias por motor (PostgreSQL COPY, MySQL multi-row, etc.)
   - `_support/`: helpers SQL, validación, sincronización PK, auditoría
   - `audit.py`: AuditManager para validación post-escritura

2. **`src/util_bbdd/dump/`** — Volcado de datos entre esquemas/motores
   - `orchestrator.py`: orquestador principal (análisis, desactivación constraints, carga, rehabhabilitación)
   - `_constraints.py`: gestor de FK y constraints
   - `_indexes.py`: gestor de índices
   - `reporters.py`: generación de informe Excel
   - `_sql_utils.py`: helpers de quote/escape

### Versión canónica

- **Última release**: `v0.15.0` (2026-09-25)
- **Historial arquitectónico**: `.ai/architecture.md`, `.ai/CURRENT_STATE.md`, `.ai/DECISIONS_LOG.md`
- **Instrucciones del proyecto**: `.github/SHARED_INSTRUCTIONS.md` (fuente canónica), `.github/instructions/architecture.instructions.md`

---

## 🔍 OBJETIVO

**Analizar `bulk/` y `dump/`** en busca de:

1. **Código duplicado o casi duplicado**
   - Lógica de quote/escape/normalizacion
   - Generación de SQL (DDL, DML)
   - Gestión de transacciones y commit
   - Manejo de errores y logging

2. **Patrones reutilizables no extraídos**
   - Estrategias de ejecución (batch, paralelismo, chunking)
   - Caché y memoria (BulkPersistenceManager, MetadataCache)
   - Validación de DataFrames
   - Construcción de parámetros SQL
   - Estadísticas y auditoría

3. **Violaciones de SOLID identificadas**
   - Responsabilidades que se solapan
   - Clases/módulos con demasiadas razones para cambiar
   - Dependencias circulares o frágiles
   - API pública vs. privada confusa

4. **Oportunidades de mejora de mantenibilidad**
   - Abstracciones faltantes (interfaces/protocolos)
   - Nombres confusos o no descriptivos
   - Documentación incompleta o desalineada del código
   - Casos límite (edge cases) sin cobertura
   - Configuración hardcodeada o sin defaults claros

5. **Propuestas de refactoring concretas**
   - Modelos de extracción (qué extraer, dónde, cómo)
   - Beneficio estimado (mantenibilidad +X%, performance ±Y%)
   - Riesgo de compatibilidad (cambio incompatible sí/no)
   - Esfuerzo estimado (pocas horas, días, semanas)

---

## 📚 FUENTES DE INFORMACIÓN

### Lectura obligatoria (proyecto)

1. **`.github/SHARED_INSTRUCTIONS.md`** — Arquitectura canónica, SOLID, calidad, comandos
2. **`.ai/architecture.md`** — Visión de 3 niveles (Foundation, Services, Specialization), responsabilidades
3. **`.ai/CURRENT_STATE.md`** — Estado actual, versiones, tests, deuda técnica conocida
4. **`.ai/DECISIONS_LOG.md`** — Decisiones arquitectónicas pasadas y razones

### Código fuente (lectura profunda)

- `src/util_bbdd/bulk/` (5-10 archivos, ~2K LOC)
- `src/util_bbdd/dump/` (5-7 archivos, ~1K LOC)
- `src/util_bbdd/managers/` (para entender ciclo de vida)
- `src/util_bbdd/metadata/` (para entender caché y normalización)
- `src/util_bbdd/_core/` (tipos base, excepciones)

### Consulta en internet permitida

- ✅ Documentación oficial: SQLAlchemy ORM/Core, drivers async (asyncpg, aiomysql, aiosqlite)
- ✅ Best practices Python: dataclasses, type hints, protocolos, factory patterns
- ✅ Patrones de diseño aplicables: Strategy, Template Method, Factory, Observer
- ✅ Rendimiento BD: batch processing, paralelismo, caché multi-nivel
- ✅ Auditoría y compliance: logging estructurado, trazabilidad de cambios

### NO consultar

- ❌ Código de competidores (SQLAlchemy en sí, no servir de base para reescrituras)
- ❌ LLMs o APIs externas (todo debe ser verificable y public)

---

## 📊 ARTEFACTOS DE SALIDA

Entrega un análisis estructurado en **Markdown** con las siguientes secciones:

### 1. **Ejecutivo**
- Hallazgos principales (3-5 puntos clave)
- Impacto estimado en mantenibilidad (porcentaje o escala cualitativa)
- Prioridad global (ALTA / MEDIA / BAJA)

### 2. **Duplicación y Oportunidades de Extracción**
Tabla con columnas:
| Localización | Patrón | Líneas | Candidato a Extraer | Beneficio | Riesgo |
|---|---|---|---|---|---|
| `bulk/crud.py:L42-L56` | Normalizacion DataFrame | 15 | `DataFrameNormalizer.normalize_column_identifiers()` | Reutilizable en dump/ | Bajo |
| ... | ... | ... | ... | ... | ... |

### 3. **Violaciones de SOLID**
Por principio (SRP, OCP, LSP, ISP, DIP) — para cada violación:
- **Ubicación**: archivo(s) y función(es)
- **Descripción**: qué responsabilidades se solapan
- **Impacto**: dificultad de testing, cambios frágiles, etc.
- **Propuesta**: cómo refactorizar

### 4. **Patrones Reutilizables No Extraídos**
Por patrón (Strategy, Template Method, Factory, etc.):
- **Dónde aparece**: módulos/clases
- **Variantes**: cómo difieren las implementaciones
- **Abstracción propuesta**: protocolo/clase base/función genérica
- **Ubicación sugerida**: módulo nuevo o existente

### 5. **Análisis de Mantenibilidad por Módulo**
Para `bulk/` y `dump/`:
- **Complejidad ciclomática**: funcs > 10
- **Cobertura de tests**: actual vs. recomendada
- **Documentación**: docstrings presentes/completos
- **Type hints**: coverage %
- **Nombres y claridad**: confusos o no descriptivos

### 6. **Propuestas de Refactoring (Priorizado)**
Máximo 5 propuestas ordenadas por beneficio/esfuerzo:

#### Propuesta N: [Nombre Descriptivo]
- **Objetivo**: qué se mejora
- **Alcance**: archivos/módulos afectados
- **Cambio incompatible**: sí/no
- **Esfuerzo estimado**: pocas horas / 1-2 días / 1 semana
- **Beneficio**: +X% mantenibilidad, ±Y% performance, Z nuevas capacidades
- **Plan de implementación**: pasos secuenciales
- **Tests impactados**: qué necesita reescrituras
- **Rollback plan**: cómo revertir si falla

### 7. **Comparativa Antes/Después**
Ejemplo de código refactorizado para las propuestas más impactantes:
```python
# ANTES
def bulk_insert(...):
    # 40 líneas de SQL building + error handling

# DESPUÉS
def bulk_insert(...):
    strategy = InsertStrategyResolver(db_type).resolve()
    generator = SQLGenerator(strategy)  # Nueva extracción
    result = generator.execute(...)
```

### 8. **Roadmap de Implementación**
- **Fase 1** (corto plazo, pocas horas): extracciones rápidas de bajo riesgo
- **Fase 2** (mediano plazo, 1-2 días): refactorings con cambio mínimo
- **Fase 3** (largo plazo, 1+ semana): rearquitectura profunda (si aplica)

### 9. **Referencias**
- Commit SHAs de decisiones pasadas (si aplica)
- URLs a issues/PRs relacionadas
- Secciones de `.ai/DECISIONS_LOG.md` relevantes

---

## 🚀 PROCESO RECOMENDADO

1. **Lee** `.github/SHARED_INSTRUCTIONS.md`, `.ai/architecture.md`, `.ai/CURRENT_STATE.md` en ese orden
2. **Explora** `src/util_bbdd/bulk/` y `src/util_bbdd/dump/` línea por línea
3. **Busca patrones** en internet para best practices de refactoring en Python
4. **Mapea** duplicación y solapamientos
5. **Classifica** hallazgos por SOLID y mantenibilidad
6. **Prioriza** propuestas por beneficio/esfuerzo/riesgo
7. **Entrega** informe estructurado con ejemplos de código

---

## ⚠️ RESTRICCIONES

- ✅ Puedes leer cualquier archivo del proyecto (todos públicos)
- ✅ Consulta oficial de internet para best practices
- ✅ Propón cambios sin ejecutar (análisis estático)
- ❌ No hagas commits ni cambios reales en esta sesión
- ❌ No generes PR sin aprobación explícita
- ❌ Mantén compatibilidad con Python ≥3.12

---

## 📞 CÓMO INVOCAR ESTE PROMPT

**En Claude Code** (slash command futuro, por ahora):
```
Lee .github/prompts/code_reusability_architecture.prompt.md
Analiza bulk/ y dump/ en busca de código reutilizable.
Consulta .ai/architecture.md y .ai/CURRENT_STATE.md para contexto.
Puedes consultar internet para best practices.
Entrega un informe Markdown con las 9 secciones especificadas.
```

**En Copilot Chat** (con agentes):
```
@Plan Architect

Lee .github/prompts/code_reusability_architecture.prompt.md

Objetivo: Analizar reutilización de código y mantenibilidad de bulk/ y dump/

Alcance: src/util_bbdd/bulk/ (5-10 archivos) y src/util_bbdd/dump/ (5-7 archivos)

Enfoque:
  1. Identificar duplicación de código
  2. Detectar violaciones de SOLID
  3. Extraer patrones reutilizables
  4. Proponer refactorings con beneficio estimado

Contexto: Lee .ai/architecture.md, .ai/CURRENT_STATE.md, .github/SHARED_INSTRUCTIONS.md

Puedes consultar internet para best practices.

Fase: PLAN (análisis estático, sin cambios de código).
```

**En Gemini/Cursor/Codex**:
```
Eres un arquitecto de software senior experto en Python.

Contexto: Proyecto util_bbdd, librería para operaciones con múltiples motores de BD.

Objetivo: Analizar src/util_bbdd/bulk/ y src/util_bbdd/dump/ buscando:
  - Código duplicado o casi duplicado
  - Patrones reutilizables no extraídos
  - Violaciones de SOLID
  - Oportunidades de mejora de mantenibilidad

Lee:
  1. .github/SHARED_INSTRUCTIONS.md (arquitectura)
  2. .ai/architecture.md (visión)
  3. .ai/CURRENT_STATE.md (estado actual)

Consulta internet para best practices de refactoring en Python y SQLAlchemy.

Entrega: Informe Markdown con 9 secciones (Ejecutivo, Duplicación, SOLID, Patrones,
Mantenibilidad, Refactorings, Comparativa, Roadmap, Referencias).
```

---

**Última Actualización**: 2026-09-26
**Mantenedor**: Arquitecto/Líder Técnico de util_bbdd
