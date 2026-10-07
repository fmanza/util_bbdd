# ✅ RESUMEN: Prompts para Auditoría de Rendimiento — Desactivación de Constraints

**Fecha**: 2026-09-26  
**Estado**: ✅ COMPLETADO  
**Archivos creados**: 6 documentos nuevos  

---

## 📦 ¿Qué se creó?

### 1️⃣ Prompts Principales (2 archivos)

#### `.github/prompts/performance_audit_constraints.prompt.md`
- **Tipo**: 📘 Reference Prompt (técnico detallado)
- **Contenido**: 10 áreas de auditoría, estrategias por BBDD, matriz de impactos, riesgos
- **Tamaño**: ~8,000 palabras
- **Para quién**: Arquitectos, DBAs, especialistas técnicos
- **Duración de lectura**: 2-4 horas

**Qué contiene**:
```
✅ Identificación de constraints (FK, UK, CHECK, DEFAULT, etc.)
✅ Análisis de costo por constraint
✅ Estrategias de desactivación (PostgreSQL, MySQL, Oracle, SQL Server, SQLite)
✅ Estrategia de re-habilitación segura
✅ Medición de impacto (benchmark recomendado)
✅ Validación de integridad post-carga
✅ Clasificación de constraints (críticos vs. opcionales)
✅ Overhead de auditoría y triggers
✅ Alternativas a desactivar constraints
✅ Riesgos residuales
✅ Criterios de prioridad (matriz severidad/impacto)
```

---

#### `.github/prompts/performance_audit_constraints_agent.prompt.md`
- **Tipo**: 🤖 Agent Prompt (workflow operativo)
- **Contenido**: 5 fases estructuradas de ejecución
- **Tamaño**: ~6,000 palabras
- **Para quién**: Agentes LLM (Claude, GPT, Gemini), o ejecución manual
- **Duración de ejecución**: 6-10 horas

**Estructura de 5 fases**:
```
FASE 1: PLAN
  ↓ Inventario de constraints + matriz de impacto teórico

FASE 2: AUDIT_PLAN
  ↓ Viabilidad por BBDD, riesgos, alternativas, tests

FASE 3: AUDIT_CODE
  ↓ Hallazgos técnicos (impacto %, vulnerabilidades, recomendaciones)

FASE 4: IMPROVEMENT_PLAN
  ↓ Roadmap: quick wins + fases de implementación + métricas

FASE 5: VERSION
  ↓ Veredicto, checklist de validación, recomendaciones finales
```

---

### 2️⃣ Guías de Usuario (4 archivos)

#### `docs/constraints_quick_reference.md`
- **Tipo**: ⚡ Cheatsheet (referencia rápida)
- **Tiempo**: 5 minutos
- **Para quién**: Todos (developers, architects, managers)
- **Contenido**: Quick wins sin riesgo, código SQL por BBDD, riesgos comunes, referencias

---

#### `docs/performance_audit_constraints_guide.md`
- **Tipo**: 📗 User Guide (completa)
- **Tiempo**: 30 minutos
- **Para quién**: Developers, architects, performance engineers
- **Contenido**: Cómo usar, prep de inputs, interpretación de salidas, 3 casos prácticos, validación, troubleshooting

---

#### `docs/constraints_audit_index.md`
- **Tipo**: 📋 Índice de navegación
- **Tiempo**: 5 minutos
- **Para quién**: Todos (encontrar rápidamente qué leer)
- **Contenido**: Resumen de todo, estructura de archivos, estructura de cada documento, referencias

---

#### `docs/constraints_reading_guide.md`
- **Tipo**: 📍 Guía de lectura por rol
- **Tiempo**: Variable según rol
- **Para quién**: Todos
- **Contenido**: Paths recomendados por rol (Dev, Architect, LLM, DBA), timelines, flujos, matriz de documentos

---

## 🎯 Dónde están los archivos

```
.github/prompts/
├── performance_audit_constraints.prompt.md ✨ Leer primero si eres técnico
└── performance_audit_constraints_agent.prompt.md ✨ Tu prompt si eres agente LLM

docs/
├── constraints_quick_reference.md ⭐ EMPEZAR AQUÍ (5 min)
├── performance_audit_constraints_guide.md ✨ Leer si quieres casos prácticos
├── constraints_audit_index.md ✨ Índice/resumen ejecutivo
└── constraints_reading_guide.md ✨ Mapa de lectura por rol
```

---

## 🚀 CÓMO EMPEZAR (Elige Uno)

### Opción A: Lectura Rápida (5 min)
```
Lee: docs/constraints_quick_reference.md

Resultado: Resumen ejecutivo + quick wins de bajo riesgo
```

### Opción B: Lectura Completa (30 min)
```
1. Lee: docs/constraints_quick_reference.md (5 min)
2. Lee: docs/performance_audit_constraints_guide.md (25 min)

Resultado: Entender casos prácticos + cómo usar prompts
```

### Opción C: Análisis Técnico Profundo (4-10 horas)
```
1. Lee: docs/constraints_quick_reference.md (5 min)
2. Lee: .github/prompts/performance_audit_constraints.prompt.md (2-4 horas)
3. Lee: .github/prompts/performance_audit_constraints_agent.prompt.md (30 min)
4. Ejecuta análisis manual O invoca LLM (6-10 horas)

Resultado: Plan técnico detallado + implementación
```

### Opción D: Usar Agente LLM (6-10 horas)
```
Invoca: /performance-audit-constraints en Claude Code
   o pega: .github/prompts/performance_audit_constraints_agent.prompt.md
           en ChatGPT/Gemini/Copilot

Resultado: 5 documentos automáticos + benchmark
```

---

## 💡 ¿Para Qué Sirve?

**Problema**: Mis operaciones INSERT/UPDATE/DELETE masivas son lentas.

**Preguntas que responde**:
- ✅ ¿Qué constraints ralentizan mi carga?
- ✅ ¿Cuánto mejora si los desactivo? (%)
- ✅ ¿Cuál es el riesgo de integridad de datos?
- ✅ ¿Hay alternativas más seguras?
- ✅ ¿Cómo validar que no rompo nada?
- ✅ ¿En qué orden priorizo las mejoras?

**Beneficio**: Mejora de velocidad de 5% (quick wins) a 50% (desactivación completa) + estrategia segura de implementación.

---

## 📊 Qué Esperar: Resultados Típicos

### Quick Wins (Fase 1, sin riesgo)
```
Batch size 1000 → 5000:          +8% ganancia
Logging asincrónico:              +5% ganancia
Desactivar CHECK constraints:     +2% ganancia
───────────────────────────
TOTAL Fase 1:                    +8-10% ✅ (1 hora)
```

### Optimizaciones Medium (Fase 2, riesgo medio)
```
Usar COPY (PostgreSQL):          +40-60% ganancia ✅
Índices deshabilitados (MSSQL):  +20% ganancia
FK pre-fetching:                 +10% ganancia
───────────────────────────
TOTAL Fase 2:                    +20-30% (1-3 días, requiere validación)
```

### Optimizaciones Complex (Fase 3, riesgo alto)
```
Desactivar FKs + validar:        +25-35% ganancia (requiere testing exhaustivo)
Paralelización:                  +35% ganancia (complejidad alta)
───────────────────────────
TOTAL Fase 3:                    +30-50% (1-2 semanas, muy testing-heavy)
```

**Mejora total combinada**: Hasta 60% si aplicas todas las fases.

---

## 🎓 ¿Qué aprenderás?

Después de leer los prompts:

✅ Cómo identificar constraints que ralentizan  
✅ Impacto teórico de cada constraint por BBDD  
✅ Estrategias de desactivación segura en PostgreSQL, MySQL, Oracle, SQL Server, SQLite  
✅ Cómo validar integridad post-carga  
✅ Alternativas sin desactivar (COPY, batch tuning, índices, etc.)  
✅ Matriz de riesgo/beneficio para tomar decisiones  
✅ Checklist de validación por BBDD  
✅ Casos de uso reales (100K INSERT, 1M UPDATE, bulk dump)  

---

## ⚠️ Punto Importante

**Desactivar constraints = faster INSERT pero riesgo de corrupción de datos**

**Recomendación**: 
1. ✅ Implementa quick wins PRIMERO (batch tuning, logging async) → 5-10% sin riesgo
2. ⚠️ Evalúa medium optimizations (COPY, índices) → 20-30% con riesgo bajo-medio
3. 🔴 Solo desactiva constraints si impacto > 20% y tienes validación robusta

---

## 📋 Checklist: Lo Que Necesitas Hacer

- [ ] **Paso 1**: Lee `docs/constraints_quick_reference.md` (5 min)
- [ ] **Paso 2**: Elige tu rol en `docs/constraints_reading_guide.md`
- [ ] **Paso 3**: Lee los documentos recomendados para tu rol
- [ ] **Paso 4**: Prepara inputs (tabla DDL, volumen, BBDD)
- [ ] **Paso 5**: Ejecuta auditoría (manual o invoca LLM)
- [ ] **Paso 6**: Implementa Fase 1 (quick wins, < 1 hora)
- [ ] **Paso 7** (opcional): Benchmark + valida mejoras

---

## 🔗 Links Rápidos

**Para iniciar**:
- 🚀 [`docs/constraints_quick_reference.md`](./docs/constraints_quick_reference.md) ← EMPEZAR AQUÍ
- 📍 [`docs/constraints_reading_guide.md`](./docs/constraints_reading_guide.md) ← Elige tu rol
- 📋 [`docs/constraints_audit_index.md`](./docs/constraints_audit_index.md) ← Índice completo

**Para análisis técnico**:
- 📘 [`.github/prompts/performance_audit_constraints.prompt.md`](./.github/prompts/performance_audit_constraints.prompt.md) ← Técnico detallado
- 🤖 [`.github/prompts/performance_audit_constraints_agent.prompt.md`](./.github/prompts/performance_audit_constraints_agent.prompt.md) ← Para agentes LLM

**Casos prácticos**:
- 📗 [`docs/performance_audit_constraints_guide.md`](./docs/performance_audit_constraints_guide.md) ← 3 casos reales

---

## 🎉 ¿Listo?

Empieza por: **[`docs/constraints_quick_reference.md`](./docs/constraints_quick_reference.md)** (5 minutos)

Luego: Elige tu rol en [`docs/constraints_reading_guide.md`](./docs/constraints_reading_guide.md)

---

## 📞 Soporte

Si tienes preguntas:
1. Consulta `docs/constraints_quick_reference.md` (sección "Riesgos Comunes")
2. Lee `docs/performance_audit_constraints_guide.md` (sección "Preguntas Frecuentes")
3. Revisa `.ai/sessions/` para auditorías previas en el repo

---

*Creado: 2026-09-26 | Versión 1.0.0 | Estado: ✅ Listo para usar*

**Próximo paso**: 👉 Abre [`docs/constraints_quick_reference.md`](./docs/constraints_quick_reference.md)
