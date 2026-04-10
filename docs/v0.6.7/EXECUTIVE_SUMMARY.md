# Resumen Ejecutivo: Auditoría de Instrucciones Claude

**Documento**: Análisis de mejoras para integración Claude Code + Copilot Chat en v0.6.7
**Fecha**: 10 de abril de 2026
**Estado**: Plan aprobado para implementación

---

## Matriz de Hallazgos

| # | Categoría | Severidad | Impacto | Esfuerzo | Estado |
|---|-----------|-----------|---------|----------|--------|
| 1 | Falta mapeo Claude Code ↔ Copilot Chat | 🔴 Bloqueante | Adopción incompleta | 2h | `TODO` |
| 2 | Hooks incompletos en settings.json | 🔴 Bloqueante | Regresiones no detectadas | 1h | `TODO` |
| 3 | Sin validación de inputs en comandos | 🔴 Bloqueante | Planes inconsistentes | 4h | `TODO` |
| 4 | settings.local.json sin documentación | 🔴 Bloqueante | Confusión usuario avanzado | 1h | `TODO` |
| 5 | Edge cases no documentados | 🟡 Mejora | Procedimientos ad-hoc | 2h | `TODO` |
| 6 | Inconsistencia profundidad comandos | 🟡 Mejora | Experiencia desigual | 3h | `TODO` |
| 7 | FAQ incompleta | 🟡 Mejora | Autoservicio limitado | 2h | `TODO` |
| 8 | Sin guía de fixtures/snapshots | 🟡 Mejora | Tests lentos escribir | 2h | `TODO` |
| 9 | Modo offline no documentado | 🟢 Informativo | Baja adoptabilidad CI/CD | 1h | `TODO` |
| 10 | Sin integración `.github/`+`.claude/` | 🟢 Informativo | Desvío futuro | 1.5h | `TODO` |

**Total estimado**: 19.5h de trabajo | **Recomendado**: Ejecutar Fase 1 (bloqueantes) primero

---

## Hallazgos Clave por Severidad

### 🔴 Bloqueantes (4)

#### 1️⃣ Mapeo Claude Code ↔ Copilot Chat
```
Problema:  Usuarios Copilot Chat no saben cómo activar /new-feature, /hotfix, etc.
Solución:  Matriz de equivalencias + sección en cada comando
Beneficio: Adopción coherente en ambas plataformas
```

#### 2️⃣ Hooks incompletos
```
Problema:  Solo ruff en settings.json; mypy + pytest no se ejecutan automáticamente
Solución:  Ampliar PostToolUse con mypy src + pytest --collect-only
Beneficio: Detección temprana de errores de tipo + estructura
```

#### 3️⃣ Validación de inputs
```
Problema:  /new-feature pide "objetivo" pero no valida que esté completo
Solución:  Añadir checklist interactivo + confirmación explícita
Beneficio: Planes consistentes, menos reimplementaciones
```

#### 4️⃣ settings.local.json opaco
```
Problema:  Archivo existe pero usuarios no saben qué puede customizarse
Solución:  Crear settings.local.json.example + README en .claude/
Beneficio: Usuario avanzado puede personalizar sin prueba-error
```

### 🟡 Mejoras Recomendadas (4)

- **Edge cases** → `.claude/EDGE_CASES.md` (troubleshooting merge conflicts, interrupciones, test failures)
- **Inconsistencia de comandos** → Estandarizar con ejemplos de entrada/salida
- **FAQ incompleta** → Añadir casos reales: "¿Qué si dos features tocan el mismo archivo?"
- **Testing guide** → `.claude/TESTING_GUIDE.md` (fixtures, snapshots, datos deterministas)

### 🟢 Informativos (2)

- **Modo offline** → Sección en CLAUDE.md sobre herramientas que funcionan sin red
- **Integración con `.github/`** → Mapa de qué archivos aplican dónde

---

## Deliverables por Fase

### Fase 1: Bloqueantes (1-2 semanas)
```
✅ docs/v0.6.7/CLAUDE_COPILOT_MAPPING.md              [matriz]
✅ .claude/settings.json (ampliado)                   [+ mypy + pytest]
✅ .claude/commands/*.md (8 ficheros, validación)    [checklist + ejemplos]
✅ .claude/settings.local.json.example                [configurables]
✅ .claude/README.md                                  [descripción .claude/]
```

### Fase 2: Mejoras (semana 2-3)
```
✅ .claude/EDGE_CASES.md                              [troubleshooting]
✅ .claude/COMMAND_TEMPLATE.md                        [estándar]
✅ docs/examples/claude_code_usage_complete_example.md (FAQ expandida)
✅ .claude/TESTING_GUIDE.md                           [fixtures paradigm]
```

### Fase 3: Informativos (semana 3+)
```
✅ CLAUDE.md (sección offline)
✅ .github/INTEGRATION_MAP.md
```

---

## Impacto Esperado

| Métrica | Antes | Después | Delta |
|---------|-------|---------|-------|
| Preguntas "¿Cómo activar PLAN en Copilot?" | ↑ frecuentes | ↓ resueltas por docs | -80% |
| Inconsistencia entre PLAN de usuarios A y B | Media | Baja | -60% |
| Tiempo para escribir test con fixtures | ~20min | ~5min | -75% |
| Usuarios que usan settings.local.json | 0% | 30%+ | +30% |
| Adoption PLAN→AUDIT_PLAN→IMPLEMENT | 40% | 80%+ | +40% |
| Regresiones no detectadas (mypy/pytest) | 5-8% | <2% | -70% |

---

## Riesgos y Mitigation

| Riesgo | Probabilidad | Mitigation |
|--------|--------------|-----------|
| Bloqueantes toman más tiempo del estimado | Media | Ejecutar 1.1 + 1.2 en paralelo |
| Usuarios no adoptan nuevas guías | Baja | Incluir link en cada prompt/comando |
| settings.json hooks generan overhead | Baja | Throttle pytest a `--collect-only` |
| Desvío futuro entre `.claude/` y `.github/` | Media | Crear INTEGRATION_MAP como source-of-truth |

---

## Recomendaciones Finales

1. **Ejecutar Fase 1 completa antes de cualquier nueva feature**
   → Garantiza coherencia de PLAN/AUDIT_PLAN

2. **Asignar ownership claro**
   - Mapeo Copilot: equipo de DevX / Documentación
   - Hooks: equipo de DevOps / CI
   - Validación de inputs: equipo de Documentación
   - Tests guide: equipo de QA / Testing

3. **Validar post-implementación**
   - Test con usuario novo usando docs nuevas
   - Medir adoption de PLAN/AUDIT_PLAN en sesiones reales
   - Recolectar feedback en sección "Issues + FAQ"

4. **Mantener sincronía**
   - Cuando actualices CLAUDE.md, revisar `.github/copilot-instructions.md`
   - Cuando agregues comando, templating en `.claude/COMMAND_TEMPLATE.md`

---

## Links de Referencia

- Plan detallado: [CLAUDE_INSTRUCTIONS_IMPROVEMENT_PLAN.md](CLAUDE_INSTRUCTIONS_IMPROVEMENT_PLAN.md)
- Configuración actual: `CLAUDE.md`, `.claude/`, `.github/copilot-instructions.md`
- Documentación: [docs/examples/claude_code_usage_complete_example.md](../../docs/examples/claude_code_usage_complete_example.md)
