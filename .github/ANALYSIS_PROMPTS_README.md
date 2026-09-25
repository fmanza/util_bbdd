# Análisis de Reutilización: Referencia Rápida

## ⚡ TL;DR
Dos prompts para analizar código duplicado y oportunidades de refactoring en `bulk/` y `dump/`:

| Qué | Dónde | Tamaño | Tiempo |
|-----|-------|--------|--------|
| **Análisis profundo** | `.github/prompts/code_reusability_architecture.prompt.md` | 350+ líneas | 20-40 min |
| **Copiar/pegar rápido** | `.github/prompts/code_reusability_architecture_quick.prompt.md` | 50 líneas | 10-30 min |

**Salida**: Informe Markdown de 9 secciones (Ejecutivo, Duplicación, SOLID, Patrones, Mantenibilidad, Refactorings, Comparativa, Roadmap, Referencias)

---

## 🚀 Tres Formas de Usar

### 1️⃣ **Claude Code** (Más profundo)
```
1. Copiar .github/prompts/code_reusability_architecture.prompt.md
2. Pegar en Claude Code Chat
3. Agregar objetivo específico
4. Esperar 15-30 minutos
5. Guardar en doc_old/analysis_reusability_YYYYMMDD.md
```

### 2️⃣ **Copilot Chat** (Con agente)
```
@Plan Architect

Lee .github/prompts/code_reusability_architecture.prompt.md

Objetivo: Analizar bulk/ y dump/ para reutilización de código y mantenibilidad.

Alcance: src/util_bbdd/bulk/ y src/util_bbdd/dump/

Fase: PLAN (análisis estático, sin cambios de código).
```

### 3️⃣ **Gemini/Cursor/Codex** (Más rápido)
```
1. Copiar .github/prompts/code_reusability_architecture_quick.prompt.md
2. Pegar en plataforma
3. Agregar contexto (opcional: .ai/CURRENT_STATE.md)
4. Esperar 10-25 minutos
5. Guardar resultado
```

---

## 📊 Qué Esperar en el Análisis

| Sección | Contenido | Uso |
|---------|-----------|-----|
| 1. **Ejecutivo** | 3-5 hallazgos principales | Presentar a stakeholders |
| 2. **Duplicación** | Tabla: ubicación, patrón, candidato a extraer | Priorizar refactorings rápidos |
| 3. **Violaciones SOLID** | SRP, OCP, LSP, ISP, DIP | Mejorar arquitectura |
| 4. **Patrones Reutilizables** | Strategy, Factory, etc. | Diseño futuro |
| 5. **Análisis Mantenibilidad** | Complejidad, cobertura, docs, type hints | Roadmap de calidad |
| 6. **Propuestas Refactoring** | Top 5 ordenadas por beneficio/esfuerzo | Plan de implementación |
| 7. **Comparativa Antes/Después** | Código ejemplo | Validar propuestas |
| 8. **Roadmap** | Fase 1 (horas) → Fase 2 (días) → Fase 3 (semanas) | Estimación de trabajo |
| 9. **Referencias** | Commits, issues, decisiones | Trazabilidad |

---

## 🎯 Caso de Uso: SQLNormalizer

**Del análisis esperarías ver algo así:**

```markdown
## Propuesta 1: Extraer SQLNormalizer (ALTA PRIORIDAD)

Ubicación: bulk/_support/..., dump/_sql_utils.py
Patrón: Duplicación de quote/escape (12 funciones casi idénticas)
Líneas: 15 líneas × 2 ubicaciones = 30 líneas totales a eliminar
Candidato: SQLNormalizer.quote_identifier(), quote_table(), etc.

Beneficio: +15% mantenibilidad, -10% LOC
Riesgo: Bajo (refactor transparente, sin cambio de API pública)
Esfuerzo: Pocas horas (2-4 horas)

Plan:
  1. Crear src/util_bbdd/_support/sql_normalizer.py
  2. Mover 12 funciones (eliminar duplicación)
  3. Actualizar imports en bulk/ y dump/
  4. Ejecutar pytest -xvs (validar 100% cobertura)
  5. Merge a develop
```

**Luego, invocar Feature Implementer:**
```
@Feature Implementer

Objetivo: Implementar Propuesta 1 (SQLNormalizer) del análisis de reutilización

Plan: Ver .ai/sessions/.../analysis.md sección 6 propuesta 1

Validación: pytest, ruff, mypy sin errores
```

---

## 📋 Checklist: Antes de Ejecutar Análisis

- [ ] ¿Lenaste `.github/SHARED_INSTRUCTIONS.md`?
- [ ] ¿Tienes acceso a `.ai/architecture.md` y `.ai/CURRENT_STATE.md`?
- [ ] ¿Tienes 15-40 minutos de espera?
- [ ] ¿Plataforma IA con soporte de markdown large (Claude Code, Copilot, Gemini)?
- [ ] ¿Lugar donde guardar el resultado (doc_old/ o .ai/sessions/)?

---

## 💾 Guardar el Resultado

```bash
# Opción 1: Historial
cp analysis.md doc_old/analysis_reusability_20260926.md

# Opción 2: Sesión con trazabilidad
mkdir -p .ai/sessions/2026-09-26-reusability-analysis
cp analysis.md .ai/sessions/2026-09-26-reusability-analysis/
echo "# Análisis de Reutilización 2026-09-26" > .ai/sessions/2026-09-26-reusability-analysis/TRACEABILITY.md
git add .ai/sessions/
git commit -m "docs: análisis de reutilización de código en bulk/ y dump/"
```

---

## 🔗 Flujo: Análisis → Implementación → Validación

```
1. ANÁLISIS (este prompt)
   └─→ Resultado: 9 secciones, propuestas priorizadas

2. REVISIÓN (tu equipo)
   └─→ Aprueba/rechaza propuestas

3. IMPLEMENTACIÓN (Feature Implementer)
   └─→ Crea cambios en rama feature

4. VALIDACIÓN (Code Auditor)
   └─→ Verifica cobertura, compatibilidad, tests

5. MERGE (git flow)
   └─→ PR → develop → tag release
```

---

## ⏱️ Tiempo por Plataforma

| Plataforma | Setup | Análisis | Total |
|-----------|-------|----------|-------|
| Claude Code | 2 min | 15-30 min | 20-35 min |
| Copilot Chat | 2 min | 20-40 min | 25-45 min |
| Gemini | 1 min | 10-25 min | 15-30 min |
| Cursor | 1 min | 10-25 min | 15-30 min |
| Codex | 1 min | 10-25 min | 15-30 min |

---

## 🆘 Troubleshooting

**P: El análisis es muy largo, se corta en medio**  
R: Solicitar resumen ejecutivo (primeras 3 secciones) o dividir en dos análisis (bulk/, dump/ por separado)

**P: ¿Necesito internet?**  
R: Sí, el prompt incluye búsqueda de best practices en internet (SQLAlchemy, patrones Python, etc.)

**P: ¿Puedo confiar en el beneficio estimado (+15% mantenibilidad)?**  
R: Es una estimación cualitativa. Validar en PR midiendo cobertura, complejidad ciclomática antes/después.

**P: ¿Cuándo debería re-ejecutar?**  
R: Cada 2-4 semanas si hay cambios significativos en bulk/ o dump/, o antes de versión mayor.

---

## 📚 Documentación Relacionada

- **Análisis profundo**: `docs/guides/code_reusability_analysis_guide.md`
- **Prompts**: `.github/prompts/code_reusability_architecture*.prompt.md`
- **Arquitectura**: `.ai/architecture.md`
- **Estado actual**: `.ai/CURRENT_STATE.md`
- **Decisiones**: `.ai/DECISIONS_LOG.md`

---

**Última Actualización**: 2026-09-26
