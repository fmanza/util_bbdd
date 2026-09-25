# 📋 CHEAT SHEET: Análisis de Reutilización de Código

**Imprime o guarda este documento** para referencia rápida. Usa en combinación con los otros guías.

---

## 1️⃣ UBICACIÓN DE ARCHIVOS

```
.github/prompts/
├── code_reusability_architecture.prompt.md         ← COMPLETO (350+ líneas)
└── code_reusability_architecture_quick.prompt.md   ← QUICK (50 líneas)

.github/
├── QUICK_START_ANALYSIS.md                         ← Comienza aquí (5 min)
├── ANALYSIS_PROMPTS_README.md                      ← Referencia rápida (10 min)
├── ANALYSIS_PROMPTS_INDEX.md                       ← Índice/navegación (3 min)
└── SHARED_INSTRUCTIONS.md                          ← Contexto obligatorio

docs/guides/
└── code_reusability_analysis_guide.md              ← Guía completa (30 min)

.ai/
├── architecture.md                                 ← Contexto obligatorio
└── CURRENT_STATE.md                                ← Contexto obligatorio
```

---

## 2️⃣ TRES CAMINOS: ELIGE UNO

| Camino | Setup | Análisis | Mejor Para |
|--------|-------|----------|-----------|
| **A: Rápido** | 2 min | 15-30 min | "Quiero hacerlo ya" |
| **B: Profundo** | 15 min | 20-40 min | "Quiero análisis preciso" |
| **C: Con Agente** | 2 min | 25-45 min | "Quiero contexto del proyecto" |

### Camino A (Rápido)
```
1. cat .github/prompts/code_reusability_architecture_quick.prompt.md
2. Pegar en Claude Code
3. Agregar objetivo
4. Esperar 15-30 min
```

### Camino B (Profundo)
```
1. cat .ai/architecture.md (5 min)
2. cat .ai/CURRENT_STATE.md (5 min)
3. cat .github/prompts/code_reusability_architecture.prompt.md
4. Pegar en Claude Code
5. Esperar 20-40 min
```

### Camino C (Con Agente)
```
@Plan Architect
Lee .github/prompts/code_reusability_architecture.prompt.md
Objetivo: Analizar bulk/ y dump/
Fase: PLAN (análisis estático)
```

---

## 3️⃣ SALIDA ESPERADA: 9 SECCIONES

```
1. 🎯 Ejecutivo              → 3-5 hallazgos principales
2. 🔄 Duplicación            → Tabla: ubicación | patrón | candidato | beneficio | riesgo
3. ⚖️ SOLID Violations        → SRP | OCP | LSP | ISP | DIP
4. 🧩 Patrones Reutilizables → Strategy | Factory | Template Method
5. 📈 Mantenibilidad          → Complejidad | Cobertura | Docs | Type Hints
6. 🔧 Propuestas Refactoring  → Top 5 ordenadas por beneficio/esfuerzo
7. 📋 Comparativa             → Antes/Después (código ejemplo)
8. 🛣️ Roadmap                 → Fase 1 (horas) | Fase 2 (días) | Fase 3 (semanas)
9. 📚 Referencias             → Commits | Issues | Decisiones
```

---

## 4️⃣ ACCIÓN: DESPUÉS DEL ANÁLISIS

### Paso 1: Revisar (10 min)
```
1. Leer sección 1 (Ejecutivo)
2. Leer sección 2 (Duplicación)
3. Identificar Top 3 propuestas
```

### Paso 2: Implementar (2-4 horas)
```
git checkout -b refactor/[nombre]

@Feature Implementer
Objetivo: Implementar Propuesta 1
Plan: Ver sección 6 del análisis
Validación: pytest, ruff, mypy
```

### Paso 3: Validar (30 min)
```
@Code Auditor
Cambios: Rama refactor/[nombre]
Validación: Cobertura, compatibilidad, tests
```

### Paso 4: Merge (10 min)
```
git push origin refactor/[nombre]
# Crear PR en GitHub
# Merge a develop
```

---

## 5️⃣ GUARDAR RESULTADO

```bash
# Opción 1: Historial
echo "# Análisis Reutilización - $(date +%Y%m%d)" >> doc_old/analysis_YYYYMMDD.md
# Pegar análisis

# Opción 2: Sesión con trazabilidad
mkdir -p .ai/sessions/$(date +%Y-%m-%d)-analysis
# Pegar en analysis.md
git add .ai/sessions/ && git commit -m "docs: análisis reutilización"
```

---

## 6️⃣ PREGUNTAS FRECUENTES

| P | R |
|---|---|
| ¿Cuánto tarda? | 15-40 min análisis (sin setup) |
| ¿Necesito internet? | Sí, consulta best practices |
| ¿Puedo confiar en beneficios? | Estimación cualitativa; validar en PR |
| ¿Cuándo re-ejecutar? | Cada 2-4 semanas o antes de v-major |
| ¿Funciona sin cambios código? | Sí, 100% análisis estático |
| ¿Qué pasa si se corta el análisis? | Pedir resumen ejecutivo o dividir bulk/dump por separado |

---

## 7️⃣ CHECKLIST ANTES DE EJECUTAR

- [ ] Leí QUICK_START_ANALYSIS.md
- [ ] Elegí mi camino (A/B/C)
- [ ] Tengo 15-40 minutos de espera
- [ ] Tengo ubicación donde guardar resultado
- [ ] Tengo acceso a Claude Code / Copilot / similar
- [ ] Leí contexto (3 archivos: architecture, CURRENT_STATE, SHARED_INSTRUCTIONS)

---

## 8️⃣ CRONOGRAMA TÍPICO

```
Hora 0:00   → Ejecutar análisis
Hora 0:30   → Resultado listo
Hora 1:00   → Revisar hallazgos
Hora 1:30   → Presentar equipo
Día +1      → Implementar Propuesta 1 (Feature Implementer)
Día +2-3    → Validar (Code Auditor)
Día +3-5    → Merge y tag release
```

---

## 9️⃣ DOCUMENTOS EN ORDEN DE LECTURA

```
1. .github/QUICK_START_ANALYSIS.md              ← COMIENZA AQUÍ
2. .github/ANALYSIS_PROMPTS_README.md           ← (si quieres más contexto)
3. docs/guides/code_reusability_analysis_guide.md ← (si eres líder técnico)
4. .github/ANALYSIS_PROMPTS_INDEX.md            ← (para navegar documentación)
```

---

## 🔟 BENEFICIO TÍPICO

| Propuesta | LOC Eliminado | Mantenibilidad | Tiempo | Riesgo |
|-----------|---------------|----------------|---------| -------|
| SQLNormalizer | 30-50 | +15% | 2-4h | Bajo |
| Extraer ConstraintHandler | 100-200 | +25% | 4-8h | Medio |
| Estrategias compartidas | 200-300 | +30% | 1-2d | Medio |
| Rearquitectura L3 | 400-600 | +50% | 1w+ | Alto |

---

## 📞 CONTACTO Y FEEDBACK

- **Mantene**: Equipo de util_bbdd
- **Ubicación**: GitHub Issues
- **Actualizar**: Cuando cambie bulk/ o dump/

---

**¿Listo para comenzar?**

👉 **Copia prompt quick:**
```bash
cat .github/prompts/code_reusability_architecture_quick.prompt.md
```

👉 **O lee QUICK_START:**
```bash
cat .github/QUICK_START_ANALYSIS.md
```

---

**Versión**: 1.0 | **Fecha**: 2026-09-26 | **Estado**: Listo para usar
