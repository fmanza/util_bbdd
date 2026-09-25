# 🚀 QUICK START: Análisis de Reutilización de Código

**⏱️ 5 minutos para empezar | 20-40 minutos para resultado**

---

## 📍 Ubicación de Prompts

```
.github/prompts/
├── code_reusability_architecture.prompt.md        ← Completo (350+ líneas)
└── code_reusability_architecture_quick.prompt.md  ← Quick (50 líneas)
```

---

## 🎯 Elige TU Camino

### 🔵 Camino A: "Quiero hacerlo ahora mismo" (10 min setup)
```bash
# 1. Copiar prompt quick
cat .github/prompts/code_reusability_architecture_quick.prompt.md

# 2. Abrir Claude Code (o tu IA favorita)
# 3. Pegar el contenido
# 4. Agregar objetivo:
#
#    Objetivo: Analizar bulk/ y dump/ para reutilización de código.
#    Alcance: src/util_bbdd/bulk/ y src/util_bbdd/dump/
#    Contexto: .ai/architecture.md, .ai/CURRENT_STATE.md
#
# 5. Esperar 15-30 minutos
```

**Ventaja**: Rápido  
**Desventaja**: Menos contexto

---

### 🟠 Camino B: "Quiero análisis profundo" (20 min setup)
```bash
# 1. Leer primero (5 min):
cat .ai/architecture.md                    # Visión
cat .ai/CURRENT_STATE.md                   # Estado actual
cat .github/SHARED_INSTRUCTIONS.md | head -100

# 2. Copiar prompt completo (5 min)
cat .github/prompts/code_reusability_architecture.prompt.md

# 3. Abrir Claude Code (o Copilot Chat con @Plan Architect)
# 4. Pegar el contenido (el prompt ya tiene contexto)
# 5. Agregar objetivo específico
# 6. Esperar 20-40 minutos
```

**Ventaja**: Análisis más preciso y contextualizado  
**Desventaja**: Más tiempo de setup

---

### 🟢 Camino C: "Usar Copilot Chat con agente" (5 min setup)
```bash
# 1. Abrir Copilot Chat (Ctrl+Shift+I en VS Code)
# 2. Escribir:

@Plan Architect

Lee .github/prompts/code_reusability_architecture.prompt.md

Objetivo: Analizar reutilización de código en bulk/ y dump/
Alcance: src/util_bbdd/bulk/ (5-10 archivos) y dump/ (5-7 archivos)
Fase: PLAN (análisis estático, sin cambios de código)

# 3. Esperar 25-45 minutos
```

**Ventaja**: Agente integrado con contexto del proyecto  
**Desventaja**: Más lento

---

## 📥 Entrada Mínima Requerida

```yaml
Contexto obligatorio que debe leer:
  1. .github/SHARED_INSTRUCTIONS.md (5 min) — Arquitectura base
  2. .ai/architecture.md (5 min) — Estructura 3 niveles
  3. .ai/CURRENT_STATE.md (5 min) — Estado actual, versiones

Lectura del código (automática):
  - src/util_bbdd/bulk/ (12 archivos)
  - src/util_bbdd/dump/ (8 archivos)

Búsqueda externa (permitida):
  - SQLAlchemy best practices
  - Patrones de diseño Python
  - Refactoring patterns
```

---

## 📤 Salida Esperada

**Un archivo Markdown con 9 secciones:**

```
1. 🎯 Ejecutivo                  → Resumen 5 min (3-5 puntos)
2. 🔄 Duplicación               → Tabla de código duplicado
3. ⚖️ Violaciones SOLID          → Por principio (SRP, OCP, etc.)
4. 🧩 Patrones Reutilizables    → Strategy, Factory, etc.
5. 📈 Mantenibilidad            → Por módulo (complejidad, cobertura)
6. 🔧 Propuestas Refactoring    → Top 5 priorizadas
7. 📋 Comparativa Antes/Después → Código ejemplo
8. 🛣️ Roadmap                    → Fase 1 (horas) → Fase 2 (días) → Fase 3 (semanas)
9. 📚 Referencias               → Commits, issues, decisiones
```

---

## 💾 Guardar Resultado (1 min)

```bash
# Opción 1: Historial simple
mkdir -p doc_old
FECHA=$(date +%Y%m%d)
echo "# Análisis de Reutilización - $FECHA" > doc_old/analysis_reusability_$FECHA.md
# Pegar contenido del chat

# Opción 2: Sesión con trazabilidad
mkdir -p .ai/sessions/$(date +%Y-%m-%d)-reusability-analysis
# Pegar en analysis.md
git add .ai/sessions/
git commit -m "docs: análisis de reutilización de código bulk/dump"
```

---

## 🎯 Después: ¿Qué Hacer?

### Paso 1: Revisar Hallazgos (10 min)
- Leer sección 1 (Ejecutivo)
- Leer sección 2 (Duplicación)
- Presentar a tu equipo

### Paso 2: Priorizar Refactorings (15 min)
- Leer sección 6 (Propuestas)
- Elegir Top 1-3 por beneficio/esfuerzo
- Crear issues en GitHub

### Paso 3: Implementar (1-5 días)
```bash
git checkout -b refactor/bulk-dump-reusability

# Usar @Feature Implementer:
@Feature Implementer

Objetivo: Implementar Propuesta 1 del análisis (Extraer SQLNormalizer)
Alcance: Crear _support/sql_normalizer.py, actualizar imports
Validación: pytest -xvs, ruff check, mypy src
```

### Paso 4: Validar (30 min)
```bash
# Usar @Code Auditor:
@Code Auditor

Cambios: Rama refactor/bulk-dump-reusability
Enfoque: Validar cobertura, compatibilidad, tests, change incompatible
Restricción: Cambio debe ser 100% transparente
```

### Paso 5: Merge
```bash
git push origin refactor/bulk-dump-reusability
# Crear PR en GitHub
# Merge a develop
```

---

## 🔑 Claves de Éxito

✅ **Haz**:
- Ejecutar análisis después de cerrar una versión
- Compartir hallazgos con equipo
- Priorizar por beneficio/esfuerzo
- Guardar resultado para futura referencia
- Crear una PR por propuesta

❌ **Evita**:
- Ejecutar análisis sin contexto previo (lee los 3 archivos obligatorios)
- Implementar todas las propuestas de una vez (priorizar)
- Cambiar API pública sin análisis de impacto
- Ignorar el roadmap (Fase 1 primero, luego Fase 2, etc.)

---

## ⏱️ Cronograma Típico

```
Hora 0:00   → Ejecutar análisis en Claude Code
Hora 0:30   → Resultado listo (si no, esperar)
Hora 1:00   → Revisar hallazgos
Hora 1:30   → Presentar al equipo
Hora 2:00   → Crear issues de refactoring
Día +1      → Implementar Propuesta 1 con Feature Implementer
Día +2-3    → Validar con Code Auditor
Día +3-5    → Merge a develop y tag release
```

---

## 📞 Ayuda Rápida

| Pregunta | Respuesta |
|----------|-----------|
| ¿Cuánto tarda? | 15-40 minutos según plataforma |
| ¿Necesito internet? | Sí, el prompt consulta best practices |
| ¿Puedo confiar en beneficios? | Estimación cualitativa; validar en PR |
| ¿Cuándo re-ejecutar? | Cada 2-4 semanas o antes de versión mayor |
| ¿Funciona sin cambios de código? | Sí, 100% análisis estático |

---

## 🎓 Ejemplo Real: De Cero a Merge en 2 Días

**Día 1, Mañana (30 min)**
```
1. Ejecutar análisis (30 min)
2. Guardar en doc_old/
3. Leer sección 1-2
→ Identificar: "12 funciones duplicadas en quote/escape"
```

**Día 1, Tarde (1 hora)**
```
1. Revisar con equipo (30 min)
   → Aprobar Propuesta 1: SQLNormalizer
2. Crear rama (5 min)
   → git checkout -b refactor/sql-normalizer
3. Invocar Feature Implementer (25 min)
   → Ver sección 6 propuesta 1
   → Pasar plan de implementación
```

**Día 2, Mañana (2 horas)**
```
1. Feature Implementer termina cambios (45 min)
2. Ejecutar tests (15 min)
   → pytest -xvs: OK
3. Invocar Code Auditor (30 min)
   → Validar cobertura, compatibilidad
   → Verdict: "APROBADO"
4. Crear PR (5 min)
```

**Día 2, Tarde (30 min)**
```
1. Review en GitHub (20 min)
2. Merge a develop (5 min)
3. Tag release v0.16.0 (5 min)
```

**Total: ~2 días, +15% mantenibilidad, -10% LOC**

---

## 🗂️ Estructura de Directorios

```
util_bbdd/
├── .github/
│   ├── prompts/
│   │   ├── code_reusability_architecture.prompt.md       ← Completo
│   │   └── code_reusability_architecture_quick.prompt.md ← Quick
│   ├── ANALYSIS_PROMPTS_README.md                        ← Este archivo
│   └── SHARED_INSTRUCTIONS.md                            ← Contexto obligatorio
│
├── docs/guides/
│   └── code_reusability_analysis_guide.md                ← Guía detallada
│
├── .ai/
│   ├── architecture.md                                   ← Contexto 1
│   ├── CURRENT_STATE.md                                  ← Contexto 2
│   └── DECISIONS_LOG.md                                  ← Contexto 3
│
└── doc_old/
    └── analysis_reusability_20260926.md                  ← Resultado análisis
```

---

**¿Listo para empezar? Elige tu camino (A, B o C) arriba. ⬆️**
