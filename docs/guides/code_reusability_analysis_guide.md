# Guía: Análisis de Reutilización de Código y Mantenibilidad

**Versión**: 1.0  
**Fecha**: 2026-09-26  
**Objetivo**: Documentar cómo usar los prompts de análisis arquitectónico de `bulk/` y `dump/`  
**Audiencia**: Arquitectos, líderes técnicos, senior engineers

---

## 📌 Overview

Hay **dos prompts gemelos** para realizar un análisis arquitectónico profundo de los módulos `bulk/` y `dump/`:

| Prompt | Ubicación | Tamaño | Uso |
|--------|-----------|--------|-----|
| **Completo** | `.github/prompts/code_reusability_architecture.prompt.md` | ~290 líneas | Lectura completa, contexto detallado |
| **Quick** | `.github/prompts/code_reusability_architecture_quick.prompt.md` | 50 líneas | Copiar/pegar rápido en chat |

Ambos producen el **mismo análisis** de 9 secciones, solo difieren en presentación.

---

## 🎯 ¿Cuándo usar?

### Situación 1: Mejora de Mantenibilidad
**Objetivo**: Identificar código duplicado y oportunidades de refactoring  
**Momento ideal**: Después de cierre de una versión, antes de sprint de deuda técnica

```
Usa este análisis si:
✅ Necesitas reducir complejidad de bulk/ o dump/
✅ Quieres identificar patrones reutilizables
✅ Buscas mejoras sin cambios incompatibles
❌ NO usar para: bugs urgentes (P0/P1) o features nuevas sin análisis previo
```

### Situación 2: Refactoring Planificado
**Objetivo**: Proponer y priorizar cambios arquitectónicos  
**Momento ideal**: Planning de una versión mayor (v1.0.0)

```
Usa este análisis si:
✅ Planeas refactoring de bulk/ o dump/
✅ Necesitas roadmap de implementación
✅ Quieres estimar esfuerzo y riesgo
❌ NO usar para: cambios pequeños (1-2 archivos)
```

### Situación 3: Auditoría Técnica
**Objetivo**: Evaluación independiente de calidad  
**Momento ideal**: Antes de publicar versión a clientes

```
Usa este análisis si:
✅ Necesitas auditoría técnica independiente
✅ Buscas validar decisiones arquitectónicas
✅ Requieres evidencia para presentar a stakeholders
❌ NO usar para: validación de PRs (usa Code Auditor)
```

---

## 🚀 Cómo Usar por Plataforma

### **Opción A: Claude Code** (recomendado para análisis profundo)

#### Paso 1: Copiar prompt
```bash
# Desde terminal del proyecto:
cat .github/prompts/code_reusability_architecture.prompt.md
```

#### Paso 2: Pegar en Claude Code
En la ventana de chat de Claude Code, pega el contenido completo del prompt seguido de:

```
Objetivo: Analizar bulk/ y dump/ para reutilización de código y mantenibilidad.

Alcance: src/util_bbdd/bulk/ (41 archivos, ~8,7K líneas en v1.1.0)
         src/util_bbdd/dump/ (11 archivos, ~3,3K líneas en v1.1.0)

Contexto: .ai/architecture.md, .ai/CURRENT_STATE.md, .github/SHARED_INSTRUCTIONS.md

Entrega el informe de 9 secciones con ejemplos de código en los refactorings.
```

#### Paso 3: Esperar análisis
- **Duración estimada**: 15-30 minutos (dependiendo de carga)
- **Salida**: Markdown con 9 secciones en el chat

#### Paso 4: Guardar resultado
Copiar el análisis a un archivo:
```bash
# Crear archivo de resultado
echo "# Análisis de Reutilización - [fecha]" > doc_old/analysis_reusability_YYYYMMDD.md
# Pegar el contenido del chat
```

---

### **Opción B: Copilot Chat** (recomendado para usuarios VS Code)

#### Paso 1: Abrir Copilot Chat
Ctrl+Shift+I (o icono de Chat en VS Code)

#### Paso 2: Invocar con agente
Escribe en el chat:

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

#### Paso 3: Esperar análisis
- **Duración**: 20-40 minutos (agente más lento que Claude Code)
- **Ventaja**: Usa agente Plan Architect con contexto del proyecto

#### Paso 4: Guardar resultado
Copiar del chat a archivo (mismo que Opción A)

---

### **Opción C: Gemini / Cursor / Codex** (alternativa rápida)

#### Paso 1: Copiar prompt quick
```bash
cat .github/prompts/code_reusability_architecture_quick.prompt.md
```

#### Paso 2: Pegar en plataforma
Abre el chat y pega el prompt quick + objetivo específico

#### Paso 3: Completar si es necesario
El prompt quick es compacto, así que agrega:

```
Consulta también:
- .ai/decisions_log.md (decisiones arquitectónicas pasadas)
- tests/unit/bulk/ (para entender cobertura actual)
- tests/unit/dump/ (para entender cobertura actual)
```

#### Paso 4: Esperar análisis
- **Duración**: 10-25 minutos (plataformas más rápidas)
- **Salida**: Igual que opciones anteriores

---

## 📊 Estructura del Análisis Esperado

El análisis siempre entrega **9 secciones** en Markdown:

!!! warning "Ejemplos ilustrativos"
    Los fragmentos de salida de esta sección y de «Ejemplo Completo» (hallazgos, porcentajes, `SQLNormalizer`,
    funciones duplicadas) muestran el **formato** del informe. No son hallazgos medidos sobre el código: ni
    `util_bbdd._support.sql_normalizer` existe ni las cifras proceden de una medición.

### 1. 🎯 **Ejecutivo**
Resumen de 3-5 hallazgos principales + impacto en mantenibilidad

```markdown
## Hallazgos Principales

- **Duplicación de quote/escape**: 12 funciones casi idénticas en bulk/ y dump/
  Impacto: +15% mantenibilidad, -10% LOC
  
- **Violación SRP**: `DumpOrchestrator` maneja 5 responsabilidades
  Impacto: +25% testabilidad tras refactor
  
- [Más hallazgos...]
```

### 2. 🔄 **Duplicación de Código**
Tabla con ubicación exacta, patrón y candidato a extraer

```markdown
| Localización | Patrón | Líneas | Candidato a Extraer | Beneficio | Riesgo |
|---|---|---|---|---|---|
| bulk/crud.py:L42-L56 | Normalizacion DF | 15 | DataFrameNormalizer | Reutilizable | Bajo |
| dump/orchestrator.py:L89-L103 | Normalizacion DF | 15 | DataFrameNormalizer | Reutilizable | Bajo |
```

### 3. ⚖️ **Violaciones de SOLID**
Por principio (SRP, OCP, LSP, ISP, DIP)

```markdown
## SRP (Single Responsibility Principle)

**Ubicación**: `DumpOrchestrator` (src/util_bbdd/dump/orchestrator.py)
**Problema**: Maneja 5 responsabilidades:
  1. Análisis de dependencias FK
  2. Desactivación de constraints
  3. Limpieza de datos
  4. Orquestación de carga
  5. Rehabhabilitación de constraints

**Impacto**: Testing frágil, cambios arriesgados, coherencia baja
**Propuesta**: Extraer a `ConstraintHandler`, `DumpAnalyzer`, `DataCleaner`
```

### 4. 🧩 **Patrones Reutilizables**
Strategy, Factory, Template Method, Observer, etc.

```markdown
## Strategy Pattern

**Dónde aparece**: 
- `bulk/_execution/insert_strategies.py`: `InsertStrategyResolver` (PostgreSQL COPY, MySQL multi-row, etc.)
- `dump/_sql_utils.py`: Quote strategies por motor

**Oportunidad**: Extraer a `SQLGenerationStrategy` compartida entre bulk/ y dump/
```

### 5. 📈 **Análisis de Mantenibilidad**
Por módulo (complejidad, cobertura, docs, type hints)

```markdown
| Módulo | Compl. Ciclomática | Cobertura Tests | Docstrings | Type Hints | Verdict |
|---|---|---|---|---|---|
| bulk/crud.py | 8 | 92% | 95% | 100% | ✅ Sano |
| dump/orchestrator.py | 15 | 78% | 80% | 85% | ⚠️ Mejorable |
```

### 6. 🔧 **Propuestas de Refactoring**
Top 5 ordenadas por beneficio/esfuerzo

```markdown
## Propuesta 1: Extraer `SQLNormalizer` (ALTA PRIORIDAD)

**Objetivo**: Eliminar duplicación de quote/escape
**Alcance**: bulk/_support/, dump/_sql_utils.py
**Cambio incompatible**: No
**Esfuerzo**: Pocas horas
**Beneficio**: +20% mantenibilidad, -15% LOC
**Plan**:
  1. Crear src/util_bbdd/_support/sql_normalizer.py
  2. Extraer 12 funciones
  3. Actualizar imports en bulk/ y dump/
  4. Ejecutar tests
```

### 7. 📋 **Comparativa Antes/Después**
Código ejemplo de refactorings principales

```python
# ANTES: Duplicado en bulk/ y dump/
def quote_identifier(name: str, motor: str) -> str:
    if motor in ("mysql", "mariadb"):
        return f"`{name}`"
    elif motor == "postgresql":
        return f'"{name}"'
    # ...

# DESPUÉS: Centralizado
from util_bbdd._support.sql_normalizer import SQLNormalizer
normalizer = SQLNormalizer(motor)
quoted = normalizer.quote_identifier(name)
```

### 8. 🛣️ **Roadmap de Implementación**
Fases temporales

```markdown
## Fase 1: Extracciones Rápidas (2-4 horas)
- SQLNormalizer
- DataFrameNormalizer

## Fase 2: Refactoring Modular (1-2 días)
- Extraer ConstraintHandler de DumpOrchestrator
- Crear DumpAnalyzer

## Fase 3: Rearquitectura (1+ semana)
- Unificar estrategias de ejecución (bulk/ y dump/)
- Crear capa de abstracción compartida
```

### 9. 📚 **Referencias**
Commits, issues, decisiones pasadas

```markdown
- Commit abc1234: "feat: InsertStrategyResolver" (2026-05-31)
- Issue #18: "MySQL variable auto-config" (abierta)
- .ai/DECISIONS_LOG.md: Decisión de 3 niveles (2026-06-05)
```

---

## 💾 Dónde Guardar el Resultado

### Opción 1: Historial del Proyecto
```bash
doc_old/analysis_reusability_YYYYMMDD.md
```

### Opción 2: Sesión del Proyecto (.ai)
```bash
.ai/sessions/YYYY-MM-DD-reusability-analysis/analysis.md
```

### Opción 3: Artefacto de PR
Si vas a crear PR con refactorings:
```bash
.ai/sessions/YYYY-MM-DD-refactor-bulk-dump/
  ├── analysis.md         (este análisis)
  ├── roadmap.md          (plan detallado)
  └── TRACEABILITY.md     (mapeo cambios → análisis)
```

---

## 🔗 Integración con Flujo de Trabajo

### Secuencia típica

```
1. Ejecutar este análisis
   ↓
2. Revisar hallazgos con equipo técnico
   ↓
3. Priorizar refactorings (usar sección 6)
   ↓
4. Crear rama feature: git checkout -b refactor/bulk-dump-reusability
   ↓
5. Usar agente @Feature Implementer para aplicar cambios
   ↓
6. Ejecutar tests: pytest -xvs
   ↓
7. Usar agente @Code Auditor para validar
   ↓
8. Crear PR con referencia al análisis
```

### Cómo invocar Feature Implementer

```
@Feature Implementer

Objetivo: Implementar extractción de SQLNormalizer (del análisis de reutilización)

Cambios:
  1. Crear src/util_bbdd/_support/sql_normalizer.py
  2. Extraer 12 funciones de bulk/_support/ y dump/_sql_utils.py
  3. Actualizar imports
  4. Ejecutar tests

Plan: Usar el roadmap de "Propuesta 1" del análisis de reutilización.

Restricciones: No cambiar API pública, mantener 100% cobertura de tests.
```

---

## ⚠️ Limitaciones y Consideraciones

### ✅ Qué hace bien
- Análisis estático profundo sin ejecutar código
- Identificación de patrones duplicados
- Propuestas de refactoring con beneficio estimado
- Consulta de best practices en internet

### ⚠️ Limitaciones
- No mide rendimiento real (solo análisis teórico)
- No detecta todos los edge cases
- Beneficio estimado es aproximado
- Requiere validación en PR antes de merge

### ❌ Qué NO debe hacer
- No ejecutar cambios automáticos
- No modificar código sin aprobación
- No cambiar API pública sin análisis de impacto
- No romper tests existentes

---

## 🎓 Ejemplo Completo: De Análisis a Implementación

### Paso 1: Ejecutar análisis
```bash
# En Copilot Chat o Claude Code, pegar prompt
# Esperar 20-30 minutos
# Guardar resultado en doc_old/analysis_reusability_20260926.md
```

### Paso 2: Revisar hallazgos
```bash
# Leer secciones 1-2 (Ejecutivo, Duplicación)
# Identificar que hay 12 funciones duplicadas de quote/escape
# Calcular: Si eliminas 500 LOC duplicado → +15% mantenibilidad
```

### Paso 3: Crear rama de refactor
```bash
git checkout -b refactor/sql-normalizer
```

### Paso 4: Usar Feature Implementer
```
@Feature Implementer

Objetivo: Extraer SQLNormalizer (Propuesta 1 del análisis)

Alcance:
  - Crear src/util_bbdd/_support/sql_normalizer.py
  - Mover 12 funciones de quote/escape
  - Actualizar imports en bulk/ y dump/

Validación:
  - pytest -xvs (cobertura 100%)
  - ruff check src tests
  - mypy src
```

### Paso 5: Validar con Code Auditor
```
@Code Auditor

Cambios: Refactor de SQLNormalizer (rama refactor/sql-normalizer)

Enfoque: 
  - Verificar cobertura tests
  - Validar que no hay cambios de behavior
  - Revisar cambios de API pública

Restricciones: Cambio debe ser 100% transparente (sin ruptura de API).
```

### Paso 6: Crear PR
```bash
git push origin refactor/sql-normalizer

# Crear PR con descripción:
# - Referencia a análisis de reutilización
# - Link a propuesta 1 de la sección 6
# - Beneficio estimado: +15% mantenibilidad
# - Tests: 100% cobertura
```

---

## 📞 Soporte y Preguntas

### ¿Qué hago si el análisis es muy grande?
1. Dividir en dos análisis (bulk/, dump/ por separado)
2. Usar formato quick en lugar del completo
3. Pedir resumen ejecutivo (primeras 2-3 secciones)

### ¿Cuánto tiempo tarda?
- **Claude Code**: 15-30 minutos (más preciso)
- **Copilot Chat**: 20-40 minutos (con agente Plan Architect)
- **Gemini/Cursor**: 10-25 minutos (más rápido, menos contexto)

### ¿Puedo reutilizar el análisis anterior?
Sí, si han pasado menos de 2 semanas y no hay cambios importantes en bulk/ o dump/. Después, ejecutar nuevamente.

### ¿Depende de la versión de la librería?
No, el prompt es agnóstico a versión. Actualizarlo a mano si cambia la estructura de directorios de `bulk/` o `dump/`.

---

**Última Actualización**: 2026-09-26  
**Mantenedor**: Equipo de util_bbdd
