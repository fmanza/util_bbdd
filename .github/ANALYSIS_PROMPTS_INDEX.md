# 📚 ÍNDICE: Análisis de Reutilización de Código — Documentación Completa

**Fecha**: 2026-09-26  
**Proyecto**: util_bbdd  
**Objetivo**: Documentar cómo analizar y mejorar reutilización de código en `bulk/` y `dump/`

---

## 🎯 Punto de Entrada

### ¿Por dónde empiezo?

| Perfil | Documento | Tiempo |
|--------|-----------|--------|
| **"Quiero hacerlo YA"** | [QUICK_START_ANALYSIS.md](.github/QUICK_START_ANALYSIS.md) | 5 min lectura + 20 min análisis |
| **"Quiero entender primero"** | [ANALYSIS_PROMPTS_README.md](.github/ANALYSIS_PROMPTS_README.md) | 10 min lectura |
| **"Soy líder técnico"** | [code_reusability_analysis_guide.md](docs/guides/code_reusability_analysis_guide.md) | 30 min lectura |
| **"Solo necesito el prompt"** | [code_reusability_architecture_quick.prompt.md](.github/prompts/code_reusability_architecture_quick.prompt.md) | 2 min copiar/pegar |

---

## 📁 Mapa de Archivos

```
util_bbdd/
│
├─── 🟢 PUNTO DE ENTRADA
│    └── .github/QUICK_START_ANALYSIS.md
│        ⮕ 3 caminos: Rápido | Profundo | Con Agente
│        ⮕ Cronograma, ejemplos, setup
│
├─── 📖 PROMPTS (Lo que usarás)
│    ├── .github/prompts/
│    │   ├── code_reusability_architecture.prompt.md         [350+ líneas]
│    │   └── code_reusability_architecture_quick.prompt.md   [50 líneas]
│    └── ⮕ Elige uno y pega en tu IA (Claude Code, Copilot, etc.)
│
├─── 📚 DOCUMENTACIÓN
│    ├── .github/ANALYSIS_PROMPTS_README.md
│    │   ⮕ Referencia rápida, tabla comparativa, troubleshooting
│    │
│    ├── .github/ANALYSIS_PROMPTS_INDEX.md
│    │   ⮕ Este archivo
│    │
│    └── docs/guides/code_reusability_analysis_guide.md
│        ⮕ Guía completa (8 páginas), paso a paso, integración workflow
│
├─── 📋 CONTEXTO (Lee ANTES de ejecutar análisis)
│    ├── .github/SHARED_INSTRUCTIONS.md              [Arquitectura base]
│    ├── .ai/architecture.md                          [Visión 3 niveles]
│    └── .ai/CURRENT_STATE.md                         [Estado actual]
│
└─── 💾 RESULTADOS (Donde guardarás análisis)
     ├── doc_old/analysis_reusability_YYYYMMDD.md
     └── .ai/sessions/YYYY-MM-DD-reusability-analysis/
```

---

## 🚀 Flujo Típico en 3 Pasos

### Paso 1️⃣: LECTURA (10-30 min)
```
Elige tu camino en QUICK_START_ANALYSIS.md:
  → Camino A: Rápido (10 min setup)
  → Camino B: Profundo (20 min setup, mejor análisis)
  → Camino C: Con Agente (5 min setup, más contexto)
```

### Paso 2️⃣: EJECUCIÓN (20-40 min)
```
Copiar prompt → Pegar en plataforma IA → Esperar análisis
Resultado: Markdown de 9 secciones
```

### Paso 3️⃣: ACCIÓN (1-5 días)
```
Revisar → Priorizar → Implementar → Validar → Merge
(Usar Feature Implementer + Code Auditor)
```

---

## 📖 Qué Hay en Cada Documento

### 🟢 `.github/QUICK_START_ANALYSIS.md` (COMIENZA AQUÍ)
**Longitud**: 1 página | **Tiempo**: 5 min lectura  
**Contenido**:
- 3 caminos según tus necesidades
- Ubicación de prompts
- Entrada mínima requerida
- Salida esperada (9 secciones)
- Guardar resultado (1 min)
- Después: ¿Qué hacer? (Paso a paso)
- Cronograma típico (2 días)
- Claves de éxito (qué sí, qué no)

**Cuándo leerlo**: PRIMERO, antes de cualquier otra cosa

---

### 📖 `.github/ANALYSIS_PROMPTS_README.md` (Referencia Rápida)
**Longitud**: 2 páginas | **Tiempo**: 10 min lectura  
**Contenido**:
- Overview (tabla comparativa)
- Cuándo usar (3 situaciones)
- Cómo usar por plataforma (Claude Code, Copilot, Gemini/Cursor)
- Estructura del análisis esperado (9 secciones con ejemplos)
- Integración con flujo de trabajo
- Cómo invocar Feature Implementer
- Limitaciones y consideraciones
- Exemplo: SQLNormalizer (de análisis a implementación)
- Checklist antes de ejecutar

**Cuándo leerlo**: Después de QUICK_START, si quieres más contexto

---

### 📚 `docs/guides/code_reusability_analysis_guide.md` (Guía Completa)
**Longitud**: 8 páginas | **Tiempo**: 30 min lectura  
**Contenido**:
- Overview (2 prompts gemelos)
- Cuándo usar (3 situaciones detalladas)
- Cómo usar por plataforma (paso a paso, screenshots mencionadas)
- Estructura del análisis (9 secciones con ejemplos completos de código)
- Dónde guardar resultado (3 opciones)
- Integración con flujo de trabajo (diagrama)
- Limitaciones y consideraciones (qué hace, qué no)
- Ejemplo completo: De análisis a implementación (6 pasos)
- Soporte y preguntas frecuentes

**Cuándo leerlo**: Si eres líder técnico, necesitas guiar al equipo, o implementarás muchos refactorings

---

### 🔧 `.github/prompts/code_reusability_architecture.prompt.md` (Prompt Completo)
**Longitud**: 350+ líneas | **Tiempo**: 2 min copiar  
**Contenido**:
- Rol: Arquitecto Senior Python
- Contexto: Proyecto util_bbdd, módulos bulk/ y dump/
- Objetivo: 5 búsquedas (duplicación, SOLID, patrones, mantenibilidad, refactorings)
- Fuentes: Lectura obligatoria (3 archivos) + búsqueda internet
- Artefactos de salida: 9 secciones Markdown
- Proceso: 7 pasos para ejecutar
- Invocación: Ejemplos para cada plataforma

**Cuándo usarlo**: Copiar y pegar COMPLETO en Claude Code o similar

---

### ⚡ `.github/prompts/code_reusability_architecture_quick.prompt.md` (Prompt Quick)
**Longitud**: 50 líneas | **Tiempo**: 1 min copiar  
**Contenido**:
- Objetivo (1 línea)
- Contexto obligatorio (3 archivos)
- Búsqueda permitida (checklist)
- Entrega esperada (9 secciones)
- Restricciones (qué sí, qué no)
- Invocación directa (copiar/pegar)

**Cuándo usarlo**: Si quieres ir rápido, sin lectura completa del prompt

---

### 📋 Este Archivo (ANALYSIS_PROMPTS_INDEX.md)
**Longitud**: Esta página | **Tiempo**: 3 min lectura  
**Contenido**:
- Punto de entrada (tabla perfil → documento)
- Mapa de archivos (árbol de directorios)
- Flujo típico (3 pasos)
- Resumen de cada documento
- Matriz: "¿Qué documento leer?" según necesidad
- Links rápidos

**Cuándo leerlo**: Cuando necesites navegar la documentación

---

## 📊 Matriz: ¿Cuál Documento Necesito?

| Necesidad | Documento | Tiempo | Razón |
|-----------|-----------|--------|-------|
| Empezar ya | QUICK_START | 5 min | 3 caminos claros |
| Entender flujo | ANALYSIS_PROMPTS_README | 10 min | Tabla comparativa, troubleshooting |
| Guiar equipo | code_reusability_analysis_guide | 30 min | Paso a paso, integración workflow |
| Solo prompt | code_reusability_architecture_quick | 1 min | Copiar/pegar directo |
| Prompt completo | code_reusability_architecture | 2 min | Contexto embebido |
| Buscar algo | Este índice (ANALYSIS_PROMPTS_INDEX) | 3 min | Navegar documentación |

---

## 🔗 Enlaces Rápidos

### Para EJECUTAR ahora
- [QUICK_START_ANALYSIS.md](.github/QUICK_START_ANALYSIS.md) — Elige tu camino (A/B/C)
- [code_reusability_architecture_quick.prompt.md](.github/prompts/code_reusability_architecture_quick.prompt.md) — Copiar/pegar

### Para ENTENDER mejor
- [ANALYSIS_PROMPTS_README.md](.github/ANALYSIS_PROMPTS_README.md) — Referencia rápida
- [code_reusability_analysis_guide.md](docs/guides/code_reusability_analysis_guide.md) — Guía completa

### Para IMPLEMENTAR cambios
- [ANALYSIS_PROMPTS_README.md](.github/ANALYSIS_PROMPTS_README.md#-integración-con-flujo-de-trabajo) — Cómo usar Feature Implementer
- [code_reusability_analysis_guide.md](docs/guides/code_reusability_analysis_guide.md#-integración-con-flujo-de-trabajo) — Workflow detallado

### Para CONTACTO
- Mantene: Equipo de util_bbdd
- Feedback: Issues de GitHub
- Actualización: Cuando cambie estructura de bulk/ o dump/

---

## ⏱️ Tiempos de Ejecución

| Fase | Tiempo |
|------|--------|
| Lectura contexto (.ai/) | 10-15 min |
| Setup y ejecución análisis | 5-10 min |
| Análisis (espera) | 15-40 min |
| Revisión hallazgos | 10-20 min |
| Presentación equipo | 20-30 min |
| Implementación (Prop 1) | 2-4 horas |
| Validación (Code Auditor) | 30-60 min |
| Merge y release | 10-20 min |
| **TOTAL: De cero a merge** | **2-3 días** |

---

## 🎓 Ejemplo: Cómo Leer Esta Documentación

### Escenario 1: "Soy dev, quiero mejorar bulk/ mañana"
```
1. Leer QUICK_START_ANALYSIS.md (5 min)
   → Elegir Camino A (rápido)
2. Copiar code_reusability_architecture_quick.prompt.md (1 min)
3. Pegar en Claude Code + objetivo (10 min)
4. Esperar análisis (20 min)
5. Guardar resultado y compartir con líder (5 min)
   → TOTAL: ~45 minutos
```

### Escenario 2: "Soy líder técnico, debo guiar refactoring"
```
1. Leer QUICK_START_ANALYSIS.md (5 min)
2. Leer ANALYSIS_PROMPTS_README.md (10 min)
3. Leer code_reusability_analysis_guide.md (30 min)
   → Entender integración, cómo invocar Feature Implementer
4. Ejecutar análisis con Copilot Chat @Plan Architect (30 min)
5. Revisar con equipo (30 min)
6. Crear roadmap de implementación (30 min)
   → TOTAL: ~2.5 horas de preparación
```

### Escenario 3: "Necesito análisis profundo para auditoría"
```
1. Leer .github/SHARED_INSTRUCTIONS.md (20 min)
2. Leer .ai/architecture.md (15 min)
3. Leer .ai/CURRENT_STATE.md (15 min)
4. Leer code_reusability_analysis_guide.md (30 min)
5. Copiar code_reusability_architecture.prompt.md (2 min)
6. Pegar en Claude Code (15 min)
7. Esperar análisis profundo (30 min)
8. Revisar 9 secciones + generar resumen ejecutivo (60 min)
   → TOTAL: ~3.5 horas de análisis + auditoría
```

---

## ✅ Checklist: Antes de Empezar

- [ ] ¿He leído QUICK_START_ANALYSIS.md?
- [ ] ¿He elegido mi camino (A/B/C)?
- [ ] ¿Tengo 15-40 minutos de espera?
- [ ] ¿He ubicado dónde guardaré el resultado?
- [ ] ¿Tengo acceso a Claude Code, Copilot Chat o similar?
- [ ] ¿He considerado el contexto obligatorio (3 archivos)?

---

## 🚀 Comienza Aquí

👉 **[QUICK_START_ANALYSIS.md](.github/QUICK_START_ANALYSIS.md)**

---

**Última Actualización**: 2026-09-26  
**Mantenedor**: Equipo de util_bbdd  
**Estado**: Completo y listo para usar
