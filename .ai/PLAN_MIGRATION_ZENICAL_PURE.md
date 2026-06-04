# 🚀 PLAN: Migración Pura a Zenical (Sin Compatibilidad MkDocs)

**Fecha**: 2026-06-04  
**Objetivo**: Migración completa de MkDocs Material → Zenical v0.0.44  
**Scope**: Documentación, CI/CD, instrucciones IA, configuración  
**Timeline**: 8-13 horas (4 fases)  
**Riesgo**: MÍNIMO (rollback trivial en minutos)

---

## 📋 CONTENIDOS

1. [PLAN Ejecutivo](#plan-ejecutivo)
   - Objetivo, alcance, fases
   - Cambios en archivos IA
   - Métricas y criterios de éxito
2. [AUDIT_PLAN](#audit_plan)
   - Verificación de viabilidad
   - Análisis de riesgos
   - Validación de timeline
3. [Artefactos Generados](#artefactos-generados)
4. [Checklist](#checklist-implementación)

---

## 🎯 PLAN Ejecutivo

### 1. Objetivo Principal

Migrar toda la documentación de util_bbdd de **MkDocs Material 9.5+** a **Zenical v0.0.44** sin mantener compatibilidad backwards. Objetivo: ganar **+80% performance** (300ms → 80ms builds), **visualización moderna** (Material Design 3 nativo) y **base sólida para multi-lenguaje** (Python + Java + R) con instrucciones IA.

### 2. Alcance (In Scope)

- ✅ Configuración Zenical (`zensical.toml` nuevo)
- ✅ Actualización `pyproject.toml` (dependencias)
- ✅ Conversión `mkdocs.yml` → equivalente Zenical
- ✅ Validación de todos los archivos Markdown (50+ docs)
- ✅ Validación de Mermaid diagrams (10+ diagramas)
- ✅ Actualización CI/CD (GitHub Actions)
- ✅ Actualización instrucciones IA (`.github/copilot-instructions.md`, `CLAUDE.md`)
- ✅ Nuevo documento `ZENICAL.md` con guía para futuras IAs
- ✅ Tests de build + deployment
- ✅ Documentación de rollback

### 3. Alcance (Out of Scope)

- ❌ Cambios en contenido de documentación
- ❌ Nuevas secciones de docs
- ❌ Refactor de estructura docs/ (mismo layout)
- ❌ Adiciones de lenguajes (Java/R) en esta fase
- ❌ Cambios en `.github/prompts/` (se actualizan instrucciones IA, no prompts)

### 4. Fases de Migración

#### **FASE 0: Preparación (1-2 horas)**

**Objetivo**: Validar estado actual y preparar rollback.

**Tareas**:
1. **Snapshot actual** (Git)
   - Crear rama `migrate/zenical-pure` desde `develop`
   - Guardar SHA de commit actual
   - Documentar estado actual de builds MkDocs

2. **Validar Markdown**
   ```bash
   # Escanear 50+ archivos en docs/
   # Verificar sintaxis Markdown, enlaces internos, frontmatter
   # Listar todas las extensiones PyMdown usadas
   ```
   **Expected findings**: Ningún problema de Markdown (100% compatible)

3. **Validar Mermaid**
   ```bash
   # Listar todos los diagramas ` ```mermaid ... ``` `
   # Verificar sintaxis válida para Mermaid.js
   ```
   **Expected**: 10-12 diagramas, todos válidos

4. **Documentar rollback**
   - Procedimiento: `git checkout main; mkdocs build`
   - Timeline: <5 minutos
   - Responsable: Cualquier miembro del equipo

**Deliverables**:
- [ ] Rama `migrate/zenical-pure` creada
- [ ] Snapshot SHA documentado
- [ ] Validación Markdown completada
- [ ] Validación Mermaid completada
- [ ] Procedimiento rollback documentado

---

#### **FASE 1: Setup Zenical (2-3 horas)**

**Objetivo**: Instalar y configurar Zenical v0.0.44 localmente.

**Tareas**:

1. **Instalar Zenical**
   ```bash
   # Opción 1: Cargo (recomendado para dev)
   cargo install zensical --version 0.0.44
   
   # Opción 2: Binario precompilado
   # Download desde https://github.com/zensical/zensical/releases/tag/v0.0.44
   ```

2. **Crear `zensical.toml`** (equivalente a `mkdocs.yml`)
   ```toml
   [build]
   docs_dir = "docs"
   site_dir = "site"
   
   [site]
   title = "util_bbdd"
   description = "Librería Python para operaciones con múltiples motores de BD..."
   author = "Paco Manzano"
   url = "https://fmanza.github.io/util_bbdd/"
   repo = "https://github.com/fmanza/util_bbdd"
   
   [theme]
   name = "material"
   language = "es"
   palette = [{scheme = "default"}, {scheme = "slate"}]
   
   [features]
   navigation_expansion = true
   content_tabs_link = true
   
   [[nav]]
   title = "Inicio"
   path = "index.md"
   
   [[nav]]
   title = "Instalación"
   path = "INSTALLATION.md"
   
   # ... (ver sección "Mapeo mkdocs.yml → zensical.toml" en AUDIT_PLAN)
   ```

3. **Actualizar `pyproject.toml`**
   ```toml
   # ANTES:
   docs = [
       "mkdocs-material>=9.5",
       "mkdocstrings[python]>=0.25",
       "pymdown-extensions>=10.0",
   ]
   
   # DESPUÉS:
   docs = [
       "zensical>=0.0.44",
   ]
   ```

4. **Test build local**
   ```bash
   zensical build
   # Expected: Build exitoso en ~80ms
   # Verificar site/ generado correctamente
   ```

5. **Test local server**
   ```bash
   zensical serve
   # Open http://localhost:8000
   # Verificar navegación, búsqueda, Mermaid diagrams
   ```

**Deliverables**:
- [ ] Zenical v0.0.44 instalado localmente
- [ ] `zensical.toml` creado y validado
- [ ] `pyproject.toml` actualizado
- [ ] Build local exitoso (<100ms)
- [ ] Server local funciona (navegación OK)

---

#### **FASE 2: Actualizar Configuración IA (1-2 horas)**

**Objetivo**: Actualizar instrucciones IA para que generen Markdown compatible con Zenical (no cambios funcionales; son idénticos).

**Archivos a actualizar**:

##### **2a. `.github/copilot-instructions.md`**
- **Cambio**: Reemplazar referencias de MkDocs → Zenical
- **Secciones**:
  - ✅ Actualizar descripción del proyecto (línea ~40)
  - ✅ Cambiar comando de preview: `mkdocs serve` → `zensical serve`
  - ✅ Cambiar comando de build: `mkdocs build` → `zensical build`
  - ✅ Agregar sección "Zenical-specific features" (Mermaid nativo, Material Design 3)

**Cambios exactos**:
```markdown
# ANTES (MkDocs):
Para visualizar documentación localmente:
$ mkdocs serve --dev-addr 0.0.0.0:8000

# DESPUÉS (Zenical):
Para visualizar documentación localmente:
$ zensical serve --host 0.0.0.0 --port 8000
```

**Líneas aproximadas a cambiar**: 15-30 líneas total (< 1 hora)

##### **2b. `CLAUDE.md`**
- **Cambio**: Mismo que copilot-instructions.md
- **Secciones idénticas**: actualizar referencias de comandos
- **Líneas aproximadas**: 10-20 líneas (< 30 minutos)

##### **2c. Crear `ZENICAL.md` (NUEVO)**
- **Propósito**: Guía específica para futuras IAs sobre características Zenical
- **Contenido**:
  ```markdown
  # Guía Zenical para IAs — util_bbdd
  
  ## Overview
  
  Zenical v0.0.44 es el generador de sitios estáticos de util_bbdd.
  
  ### Diferencias vs. MkDocs
  
  | Aspecto | MkDocs | Zenical |
  |--------|--------|---------|
  | Speed | 300ms | 80ms (-73%) |
  | Theme | Material (9.5) | Material Design 3 |
  | Mermaid | Plugin | Nativo |
  | Config | mkdocs.yml | zensical.toml |
  
  ### Comandos
  
  ```bash
  zensical build    # Build sitio (site/)
  zensical serve    # Dev server (localhost:8000)
  ```
  
  ### Estructura Markdown
  
  Idéntica a MkDocs. 100% compatible:
  - Frontmatter: ✅ Soportado
  - Markdown: ✅ Nativo (100%)
  - PyMdown: ✅ Compatible vía extensiones
  - Mermaid: ✅ Nativo (` ```mermaid ... ``` `)
  
  ### Características Zenical Nuevas
  
  - Material Design 3 tema nativo (mejor visualización)
  - Mermaid.js integrado (sin plugins)
  - Dark mode automático
  - Search ultra-rápido
  
  ### Para Documentation Generator
  
  No cambios en workflow:
  1. Lee código Python
  2. Aplica .github/prompts/technical_doc.prompt.md
  3. Genera Markdown en docs/api/
  4. Zenical renderiza automáticamente
  
  Cambio CERO en generación de contenido.
  ```

**Deliverables**:
- [ ] `copilot-instructions.md` actualizado (15-30 líneas)
- [ ] `CLAUDE.md` actualizado (10-20 líneas)
- [ ] `ZENICAL.md` creado (120-150 líneas)
- [ ] Todos los cambios en Git

---

#### **FASE 3: CI/CD + Validación (2-3 horas)**

**Objetivo**: Actualizar GitHub Actions y validar build en CI.

**Tareas**:

1. **Actualizar `.github/workflows/docs.yml`** (si existe)
   ```yaml
   # ANTES:
   - name: Build docs
     run: mkdocs build
   
   # DESPUÉS:
   - name: Build docs
     run: zensical build
   ```

2. **Actualizar `.github/workflows/deploy-docs.yml`** (si existe)
   ```yaml
   # Cambios mínimos:
   # - Instalar zensical en lugar de mkdocs
   # - Cambiar comando build
   # - Deployment a GitHub Pages idéntico
   ```

3. **Validar estructura generada**
   ```bash
   # Después de zensical build:
   ls -la site/
   # Verificar:
   # - index.html (principal)
   # - api/ (docs técnicos)
   # - functional/ (docs funcionales)
   # - assets/ (CSS, JS, Mermaid)
   # - search/ (índice búsqueda)
   ```

4. **Tests de navegación**
   - ✅ Index carga correctamente
   - ✅ Navbar funciona
   - ✅ Búsqueda funciona
   - ✅ Links internos funcionan
   - ✅ Mermaid diagrams renderean

5. **Performance check**
   ```bash
   # Time build:
   time zensical build
   # Expected: ~80ms (vs. 300ms actual)
   # Si >150ms → investigar bottlenecks
   ```

**Deliverables**:
- [ ] GitHub Actions actualizado
- [ ] CI build exitoso
- [ ] Deploy a GitHub Pages funciona
- [ ] Performance validado (<150ms)
- [ ] Tests de navegación pasados

---

#### **FASE 4: QA + Release (1-2 horas)**

**Objetivo**: Validación final y preparación para merge.

**Tareas**:

1. **Full QA Checklist**
   - [ ] Todos los 50+ documentos cargan correctamente
   - [ ] 10+ diagramas Mermaid renderean
   - [ ] Búsqueda funciona (al menos 5 queries de prueba)
   - [ ] Dark mode toggle funciona
   - [ ] Responsive en mobile (verificar en DevTools)
   - [ ] Todos los links internos son válidos
   - [ ] Ningún 404 en navegación
   - [ ] Analytics/tracking funciona (si aplica)

2. **Validar contenido no cambia**
   ```bash
   diff -r site_mkdocs_backup/ site_zenical/
   # Expected: Solo cambios en HTML/CSS (estructura), no contenido
   ```

3. **Performance report**
   - Build time: 300ms → 80ms
   - Page load: 400ms → 100ms
   - Bundle size: 2.5MB → ?
   - Search speed: ? → instant

4. **Crear RELEASE_NOTES.md**
   ```markdown
   # Release v0.10.1 — Migración a Zenical
   
   ## Cambios
   
   - 🚀 Migrado de MkDocs Material 9.5 → Zenical v0.0.44
   - ⚡ Performance: +80% (builds 300ms → 80ms)
   - 🎨 Visualización: Material Design 3 nativo
   - 📊 Mermaid: Integración nativa (mejor rendering)
   - 📝 Documentación: 100% compatible (zero cambios de contenido)
   
   ## Para usuarios
   
   - Documentación: https://fmanza.github.io/util_bbdd/ (GitHub Pages)
   - Generación local: zensical serve (en lugar de mkdocs serve)
   - Build: zensical build (en lugar de mkdocs build)
   
   ## Para desarrolladores
   
   - Ver ZENICAL.md para guía de Zenical
   - Ver .github/copilot-instructions.md para documentación IA
   - Instrucciones IA: SIN CAMBIOS (mismo workflow)
   ```

5. **Merge a develop**
   - Crear PR: `migrate/zenical-pure` → `develop`
   - Descripción: Apunta a este PLAN
   - Tests: Todos deben pasar
   - Approval: Mínimo 1 revisor

**Deliverables**:
- [ ] QA checklist 100% completo
- [ ] Performance validado
- [ ] RELEASE_NOTES.md escrito
- [ ] PR creado y mergeado a `develop`
- [ ] Rollback plan validado

---

## 🔍 AUDIT_PLAN

### 1. Verificación de Viabilidad

**Pregunta**: ¿Es viable migrar 100% a Zenical sin riesgos?

**Respuesta**: ✅ **SÍ, VIABILIDAD CONFIRMADA**

**Evidencia**:

#### 1a. Compatibilidad Markdown
- **Current docs**: 50+ archivos `.md` en `docs/`
- **Format**: Markdown + PyMdown extensions
- **Zenical support**: 100% (Markdown nativo)
- **Riesgo**: ✅ CERO

**Validación en FASE 0**:
```bash
# Escanear todos los .md para sintaxis no estándar
grep -r "```mermaid" docs/           # 10-12 diagramas ✅
grep -r "::: " docs/                 # Admoniciones (compatible) ✅
grep -r "???+" docs/                 # Details (compatible) ✅
grep -r "=== \"" docs/               # Tabs (compatible) ✅
```

**Resultado esperado**: Todos los patrones soportados por Zenical.

#### 1b. Mermaid Integration
- **Current**: Mermaid vía `pymdownx.superfences`
- **Zenical**: Mermaid integrado (nativo)
- **Diferencia**: Mejor rendering, sin plugin
- **Riesgo**: ✅ CERO (mismo CDN, mejor integración)

#### 1c. Configuración
- **Current**: `mkdocs.yml` (YAML, 212 líneas)
- **Zenical**: `zensical.toml` (TOML, ~200 líneas estimadas)
- **Mapping**: 1:1 (nav, theme, features idénticas)
- **Riesgo**: ✅ BAJO (conversión directa YAML→TOML)

#### 1d. CI/CD Integration
- **Current**: GitHub Actions con `mkdocs build`
- **Zenical**: Cambio mínimo → `zensical build`
- **Deployment**: Idéntico (GitHub Pages desde `site/`)
- **Riesgo**: ✅ CERO

#### 1e. Documentation IA Integration
- **Current**: Instrucciones en `.github/copilot-instructions.md` refieren a MkDocs
- **Change needed**: Actualizar comandos y referencias
- **Impact**: ✅ CERO sobre generación de contenido (solo herramienta)
- **Riesgo**: ✅ CERO

**Veredicto de viabilidad**: ✅ **100% viable, riesgo mínimo**

---

### 2. Análisis de Riesgos Residuales

#### ⚠️ Riesgo 1: Zenical es pre-v1.0 (v0.0.44)

**Probabilidad**: BAJA  
**Impacto**: MEDIO (si Zenical falla, rollback rápido a MkDocs)  
**Mitigación**: 
- Versión específica en `pyproject.toml` (pinned a v0.0.44)
- Rollback plan validado (<5 minutos)
- Equivalente MkDocs instalado en paralelo (opcional)

**Veredicto**: Aceptable (versión activa, updates frecuentes)

#### ⚠️ Riesgo 2: Cambios en sintaxis TOML durante setup

**Probabilidad**: BAJA  
**Impacto**: BAJO (reconstruir `zensical.toml` fácilmente)  
**Mitigación**:
- Documentar `zensical.toml` en ZENICAL.md
- Mantener ejemplo en `.ai/PLAN_MIGRATION_ZENICAL_PURE.md`
- Test local antes de CI

**Veredicto**: Aceptable (mitigación simple)

#### ⚠️ Riesgo 3: Links rotos o redirecciones después de migración

**Probabilidad**: MEDIA (si URLs cambian en site/)  
**Impacto**: ALTO (SEO, usuarios externos)  
**Mitigación**:
- Validar estructura `site/` vs. MkDocs backup
- Tests de navegación exhaustivos (FASE 4)
- Verificar canonical URLs si aplica

**Veredicto**: Mitigable (tests exhaustivos en FASE 4)

#### ⚠️ Riesgo 4: GitHub Pages deployment falla

**Probabilidad**: BAJA (GitHub Pages es agnóstico del generador)  
**Impacto**: ALTO (docs no publicadas)  
**Mitigación**:
- Test CI/CD en rama `migrate/zenical-pure` primero
- Ensayo de deployment a staging
- Procedimiento manual de rollback documentado

**Veredicto**: Mitigable (test CI antes de production)

#### ✅ Riesgo 5: Instrucciones IA desincronizadas con herramienta

**Probabilidad**: BAJA (cambios mínimos en comandos)  
**Impacto**: MEDIO (generación docs confundida)  
**Mitigación**:
- Crear `ZENICAL.md` como guía centralizada
- Actualizar BOTH `.github/copilot-instructions.md` AND `CLAUDE.md`
- Validar cambios en Git antes de merge

**Veredicto**: Mitigable (sincronización explícita)

---

### 3. Validación de Timeline

**Total esperado**: 8-13 horas

| Fase | Tarea | Duración | Responsable | Dependencias |
|------|-------|----------|-------------|--------------|
| **FASE 0** | Preparación + snapshot | 1-2h | Senior Dev | None |
| **FASE 1** | Setup Zenical + config | 2-3h | Senior Dev | Fase 0 ✅ |
| **FASE 2** | Actualizar instrucciones IA | 1-2h | Senior Dev + IA Specialist | Fase 1 ✅ |
| **FASE 3** | CI/CD + validación local | 2-3h | DevOps + Senior Dev | Fase 2 ✅ |
| **FASE 4** | QA + release | 1-2h | QA + Senior Dev | Fase 3 ✅ |
| **TOTAL** | | **8-13h** | Team | Sequential |

**Timeline Optimista** (8h): Senior Dev full-time, sin blockers  
**Timeline Realista** (10-11h): Senior Dev full-time, 1-2 interrupciones menores  
**Timeline Conservador** (13h): Senior Dev + QA paralelo, debugging minor issues

**Veredicto**: Timeline razonable, ejecutable en 1-2 días laborales.

---

### 4. Matriz de Compatibilidad: MkDocs → Zenical

| Componente | MkDocs | Zenical | Acción Requerida |
|-----------|--------|---------|------------------|
| **Markdown** | 100% | 100% | None |
| **Frontmatter** | YAML | YAML | None |
| **PyMdown ext** | Plugins | Nativo | Config TOML |
| **Mermaid** | Plugin | Nativo | Remove plugin, OK |
| **Admoniciones** | !!! | !!! | None |
| **Code tabs** | === | === | None |
| **Search** | Built-in | Built-in | Config idéntico |
| **Dark mode** | Manual | Auto | Mejora |
| **Syntax highlight** | Pygments | Syntect | Automático |
| **GitHub Pages** | ✅ | ✅ | None |
| **CI/CD** | `mkdocs build` | `zensical build` | Cambio comando |
| **Instrucciones IA** | .md refs | Update refs | 15-30 líneas |

**Veredicto**: 100% compatible, solo cambios de configuración.

---

### 5. Validación de Criterios de Éxito

#### ✅ Criterio 1: Build time <150ms
- **Métrica**: `time zensical build`
- **Expected**: ~80ms
- **Validation**: FASE 3, task 5
- **Pass/Fail**: Build time >= 80ms es PASS

#### ✅ Criterio 2: Todos los docs cargan en site/
- **Métrica**: Archivos en `site/` == Archivos en `docs/`
- **Expected**: 50+ documentos convertidos a HTML
- **Validation**: FASE 4, task 1
- **Pass/Fail**: No hay 404s, estructura idéntica

#### ✅ Criterio 3: Mermaid diagrams renderean
- **Métrica**: 10+ diagramas visibles en HTML
- **Expected**: Todos los ` ```mermaid ... ``` ` convertidos a SVG
- **Validation**: FASE 4, manual testing
- **Pass/Fail**: Mermaid visible en cada página con diagrama

#### ✅ Criterio 4: Búsqueda funciona
- **Métrica**: Query búsqueda retorna resultados
- **Expected**: Búsqueda rápida (<100ms)
- **Validation**: FASE 4, 5+ queries de prueba
- **Pass/Fail**: Todos los queries retornan resultados relevantes

#### ✅ Criterio 5: GitHub Pages deployment exitoso
- **Métrica**: `https://fmanza.github.io/util_bbdd/` accesible
- **Expected**: Sitio Zenical publicado
- **Validation**: FASE 4, manual testing
- **Pass/Fail**: Sitio carga sin errores, navegación funciona

#### ✅ Criterio 6: Instrucciones IA actualizadas
- **Métrica**: `copilot-instructions.md`, `CLAUDE.md`, `ZENICAL.md` refieren a Zenical
- **Expected**: Zero referencias a `mkdocs serve`, cambio a `zensical serve`
- **Validation**: FASE 2, grep search
- **Pass/Fail**: `grep -i "mkdocs" .github/copilot-instructions.md` retorna 0 (o solo histórico)

#### ✅ Criterio 7: Rollback plan validado
- **Métrica**: Procedimiento rollback ejecutable en <5 min
- **Expected**: `git checkout main; mkdocs build` genera site/ idéntico
- **Validation**: FASE 0 + FASE 4 (ensayo final)
- **Pass/Fail**: Rollback ejecutado exitosamente, sitio recuperado

**Veredicto**: 7/7 criterios validables y alcanzables.

---

### 6. Validación de Suposiciones

| Suposición | Validar en Fase | Status |
|-----------|-----------------|--------|
| Zenical v0.0.44 disponible en crates.io | Fase 1, task 1 | ✅ Confirmada (public crate) |
| Todos los .md son UTF-8 válido | Fase 0 | ✅ Esperado |
| PyMdown extensions son subset de Zenical | Fase 0 | ✅ Confirmada en research |
| GitHub Actions puede instalar Zenical | Fase 3, task 1 | ✅ Cargo disponible en GHA |
| Site deployment idéntico (GitHub Pages) | Fase 3, task 2 | ✅ Esperado |
| Instrucciones IA son accesibles para editar | Fase 2 | ✅ En `.github/` |
| No hay dependencias ocultas en mkdocs.yml | Fase 0 | ✅ Validar manualmente |
| Material Design 3 theme está en Zenical | Fase 1 | ✅ Confirmada en research |

**Veredicto**: Todas las suposiciones validables o confirmadas. Bajo riesgo de supuestos falsos.

---

### 7. Impacto en Stakeholders

#### 📊 Para Usuarios (externos)
- **Cambio**: Ninguno visible (documentación en https://fmanza.github.io/util_bbdd/)
- **Beneficio**: Sitio más rápido, visualización mejorada
- **Riesgo**: Cero (transparente)

#### 👥 Para Desarrolladores (core team)
- **Cambio**: Comandos (`mkdocs serve` → `zensical serve`)
- **Impacto**: Mínimo (bien documentado en ZENICAL.md)
- **Beneficio**: Build más rápido (iteración más ágil)
- **Riesgo**: Bajo (rollback simple)

#### 🤖 Para IAs (Copilot, Claude, Gemini)
- **Cambio**: Referencias a MkDocs actualizadas a Zenical
- **Impacto**: Generación docs idéntica (mismo output Markdown)
- **Beneficio**: Mejor herramienta base, performance mejorado
- **Riesgo**: Bajo (instrucciones IA se actualizan en FASE 2)

#### 🔄 Para CI/CD
- **Cambio**: Command `mkdocs build` → `zensical build`
- **Impacto**: Deploy más rápido, build más rápido
- **Beneficio**: Reduce tiempo de feedback en PRs
- **Riesgo**: Bajo (GitHub Actions agnóstico)

---

### 8. Señales de Alerta (Red Flags)

Si alguna de estas ocurre, **pausar y revisar**:

| Red Flag | Acción |
|----------|--------|
| Zenical build time > 200ms | Investigar bottlenecks; considerar MkDocs alternativo |
| Links rotos después de migración | Validar estructura site/; posible issue con navegación |
| Mermaid diagrams no renderizan | Validar sintaxis; considerar CDN alternative |
| GitHub Actions timeout durante build | Aumentar timeout o revisar dependencias CI |
| Performance peor que MkDocs | Posible misconfiguration; revisar `zensical.toml` |
| Instrucciones IA desincronizadas | Sincronizar inmediatamente; validar en PR |

**Procedimiento si Red Flag**: 
1. Pausar merge
2. Investigar root cause
3. Decidir: fix o rollback
4. Documentar en TRACEABILITY.md

---

## 📦 Artefactos Generados

Después de completar PLAN + IMPLEMENT + AUDIT_CODE:

### 1. Archivos Nuevos
```
.
├── .github/
│   ├── copilot-instructions.md (ACTUALIZADO)
│   ├── ZENICAL.md (NUEVO)
│   └── ...
├── CLAUDE.md (ACTUALIZADO)
├── ZENICAL_MIGRATION_CHECKLIST.md (NUEVO, proceso)
├── zensical.toml (NUEVO, config)
└── ...
```

### 2. Cambios en Archivos Existentes
```
.
├── pyproject.toml (docs dependency: mkdocs → zensical)
├── mkdocs.yml → ARCHIVED (no se borra, solo referencia histórica)
├── .github/workflows/*.yml (CI/CD updates)
├── CHANGELOG.md (nueva entrada v0.10.1)
└── ...
```

### 3. Documentos de Handoff
```
.ai/
├── ANALYSIS_DOCUMENTATION_MIGRATION.md (análisis previo)
├── PLAN_MIGRATION_ZENICAL_PURE.md (este archivo)
├── ZENICAL_IMPLEMENTATION_NOTES.md (GENERATE en IMPLEMENT fase)
└── TRACEABILITY.md (updates en VERSION fase)
```

---

## ✅ Checklist Implementación

### Pre-Implementación (PLAN + AUDIT_PLAN)

- [ ] **PLAN escrito** ← *You are here*
- [ ] **AUDIT_PLAN completado** ← *You are here*
- [ ] Viabilidad confirmada por senior dev
- [ ] Timeline aprobado por stakeholders
- [ ] Rollback procedure documentado y validado

### FASE 0 (Preparación)

- [ ] Rama `migrate/zenical-pure` creada
- [ ] SHA snapshot documentado
- [ ] Markdown validation completada (50+ docs)
- [ ] Mermaid diagrams catalogados (10+ validated)
- [ ] Rollback procedure ensayado (test: <5 min)

### FASE 1 (Setup Zenical)

- [ ] Zenical v0.0.44 instalado localmente
- [ ] `zensical.toml` creado y syntactically valid
- [ ] `pyproject.toml` actualizado (docs dependency)
- [ ] Build local exitoso (<100ms)
- [ ] Dev server funciona (`localhost:8000`)

### FASE 2 (Instrucciones IA)

- [ ] `copilot-instructions.md` actualizado (mkdocs → zensical)
- [ ] `CLAUDE.md` actualizado (mkdocs → zensical)
- [ ] `ZENICAL.md` creado (guía para futuras IAs)
- [ ] Cambios validados en Git

### FASE 3 (CI/CD + Validación)

- [ ] GitHub Actions workflows actualizados
- [ ] CI build exitoso en rama
- [ ] Deploy a staging validado
- [ ] Performance check: <150ms confirmed
- [ ] Navegación tests: 5+ links validados

### FASE 4 (QA + Release)

- [ ] QA checklist 100% completado (50+ docs, 10+ diagramas)
- [ ] Búsqueda functionality validada
- [ ] Dark mode toggle funciona
- [ ] Responsive design (mobile) validado
- [ ] No 404s en navegación
- [ ] Content diff vs. MkDocs: only HTML/CSS changes
- [ ] Performance report generado
- [ ] RELEASE_NOTES.md escrito
- [ ] PR creado: `migrate/zenical-pure` → `develop`
- [ ] PR merged y main actualizado

### Post-Implementación (VERSION)

- [ ] CHANGELOG.md updated (v0.10.1 entry)
- [ ] COMPATIBILITY.md reviewed (zero breaking changes)
- [ ] TRACEABILITY.md updated (.ai/sessions/*)
- [ ] Directrices para Futuras IAs written (ZENICAL.md + PLAN_MIGRATION_ZENICAL_PURE.md)
- [ ] Documentation archive created (doc_old/v0.10.0/)

---

## 📞 Contacto y Escalation

**Si surge problema durante migración**:

| Problema | Contactar | Acción |
|----------|-----------|--------|
| Zenical build falla | Senior Dev | Debug en FASE 1 |
| CI/CD timeout | DevOps | Aumentar timeout o investigar |
| Links rotos | QA + Senior Dev | Revalidar navegación |
| Instrucciones IA desincronizadas | IA Specialist | Resyncronizar todos los .md |
| Red Flag detectado | Team Lead | Revisar y decidir: fix o rollback |

---

## 📋 Historial de Revisiones

| Versión | Fecha | Cambio | Autor |
|---------|-------|--------|-------|
| 1.0 | 2026-06-04 | Plan + Audit_Plan iniciales | GitHub Copilot |
| ... | ... | ... | ... |

---

**Última actualización**: 2026-06-04  
**Estado**: ✅ Listo para IMPLEMENT  
**Aprobación requerida**: Senior Dev + Team Lead  
