# 📚 Especificación de Estandarización de Documentación

Objetivo: Unificar la estructura de documentación técnica, funcional y general en **util_bbdd**
y definir un flujo de trabajo repetible para otros proyectos con IA.

---

## 1. Objetivo

Estandarizar instrucciones de documentación para asegurar:
- **Claridad de usuario**: Documentación funcional orientada a "qué puedo hacer"
- **Claridad de desarrollador**: Documentación técnica orientada a "cómo funciona internamente"
- **Mantenibilidad**: Estructura agnóstica al lenguaje, fácil de auditar y actualizar
- **Automatización**: Generación de docs con agentes, validación con CI/CD
- **Versionamiento**: Sincronización CHANGELOG.md y COMPATIBILITY.md con releases

---

## 2. Estado Actual

### 2.1 Estructura MkDocs
- **Site**: `mkdocs.yml` (v1.5+, Material theme)
- **Secciones existentes**:
  - ✅ Guías (DUPLICATE_PROJECT_GUIDE, NEXT_STEPS, README_DUPLICADOR, ARCHITECTURE_VISUAL)
  - ✅ Funcional (`docs/functional/`) — 8 módulos
  - ✅ Ejemplos (`docs/examples/`) — 10+ ejemplos de uso
  - ✅ API/Referencias (`docs/api/`) — 8 módulos técnicos
  - ✅ Compatibilidad y Changelog

### 2.2 Archivos Generados
- Funcional: 8 archivos en `docs/functional/`
- Técnico: 8 archivos en `docs/api/`
- Generador: mkdocstrings integrado (Python docstrings → HTML)

### 2.3 Herramientas y Agentes
| Componente | Ubicación | Estado |
|------------|-----------|--------|
| **Configuración IA** | `CLAUDE.md`, `copilot-instructions.md` | ✅ Existente |
| **Agent: config-reviewer** | `.github/agents/config-reviewer.agent.md` | ✅ Existente |
| **Agent: documentation-generator** | `.github/agents/documentation-generator.agent.md` | ✅ Existente |
| **Agent: documentation-reviewer** | `.github/agents/documentation-reviewer.agent.md` | ✅ Existente |
| **Prompt: config_review** | `.github/prompts/config_review.prompt.md` | ✅ Existente |
| **Prompt: functional_doc** | `.github/prompts/functional_doc.prompt.md` | ✅ Existente |
| **Prompt: technical_doc** | `.github/prompts/technical_doc.prompt.md` | ✅ Existente |
| **Prompt: documentation_review** | `.github/prompts/documentation_review.prompt.md` | ✅ Existente |

### 2.4 Gaps Actuales
- ✅ Referencia OneDrive → reemplazada por referencias internas al repositorio (§4)
- ✅ Estructura funcional y técnica → mapeada explícitamente en §4.2
- ✅ Roles de agentes → documentados en orden de ejecución en §5
- ⚠️ Seguridad y Rendimiento → cubiertos como opcionales en §3.2 y §4.3; excluidos del nav por defecto

---

## 3. Propuesta de Cambios

### 3.1 Documentación Funcional (Usuario)

**Propósito**: Responder "¿Qué puedo hacer con el software?"

**Ubicación**: `docs/functional/[módulo].md`

**Estructura obligatoria por módulo**:
- **Resumen Ejecutivo** — Descripción breve (2-3 líneas) y casos de uso principales
- **Características Principales** — Capacidades clave con ejemplos cortos
- **Objetivo de Negocio** — Problema resuelto y valor agregado
- **Precondiciones y Requisitos** — Dependencias y configuración necesaria
- **Flujo Principal del Usuario** — Pasos con código de ejemplo
- **Reglas de Negocio Críticas** — Restricciones y validaciones obligatorias
- **Límites y Exclusiones** — Qué NO hace y edge cases
- **Flujos de Trabajo de Usuario** — Casos de uso detallados
- **Referencias** — Enlaces a doc técnica, ejemplos y tests

**Diagramas recomendados**:
- User Journey (flujo del usuario)
- Flowchart (decisiones)
- Sequence Diagram (interacción entre actores)

---

### 3.2 Documentación Técnica (Desarrollador)

**Propósito**: Responder "¿Cómo funciona internamente?"

**Ubicación**: `docs/api/[módulo].md`

**Estructura obligatoria**:
- **Resumen de la Arquitectura** — Rol en la arquitectura, relaciones, patrón de diseño
- **Arquitectura del Sistema**:
  - Diagrama de Contexto (C4 nivel 1)
  - Diagrama de Contenedores (C4 nivel 2)
  - Diagrama de Componentes (C4 nivel 3)
  - Decisiones Arquitectónicas (ADR si aplica)
  - Patrones de Diseño Utilizados
- **Responsabilidad del Módulo** — Descripción general, responsabilidades principales
- **Dependencias** — Externas (librerías) e internas (módulos)
- **Clases Principales** — Nombre, descripción y firma
- **Flujo de Datos** — Cómo fluyen datos internamente
- **API Reference**:
  - Overview de métodos públicos
  - Detalle de cada método (firma, parámetros, retorno, excepciones)
  - Contratos de entrada y salida
  - Manejo de errores y edge cases
- **Consideraciones de Seguridad** (si aplica) — Validación, sanitización, protecciones
- **Rendimiento y Optimización** (si aplica) — Complejidad O(n), caché, límites
- **Referencias** — Enlaces a doc funcional, ejemplos y tests

**Diagramas recomendados**:
- C4 Diagram (contexto, contenedores, componentes)
- Class Diagram (clases y relaciones)
- State Diagram (máquina de estados, si aplica)
- Sequence Diagram (flujo de llamadas)
- Entity Relationship Diagram (si hay persistencia)
- Architecture Diagrams (si hay web API, microservicios, etc.)
- Docker Deployment Diagram (si hay `Dockerfile` o `docker-compose.yml`: contenedores, puertos, volúmenes, redes)
- Event Modeling Diagram (si hay que describir sistemas mediante un ejemplo de cómo ha cambiado la información dentro de ellos a lo largo del tiempo)
- TreeView Diagram (si hay estructuras de datos jerárquicas)

---

## 4. Configuración Recomendada mkdocs.yml

La siguiente configuración es la **referencia estándar** para todos los proyectos.
Adapta los valores de `site_*`, `extra.version` y `nav` a cada proyecto; el resto es la base común.

### 4.1 Configuración Completa (Referencia)

```yaml
# ── Metadatos del sitio ──────────────────────────────────────────────────────
site_name: [Nombre del Proyecto]
site_description: [Descripción breve del proyecto]
site_author: [Autor / Equipo]
site_url: https://[usuario].github.io/[repo]

# ── Tema ─────────────────────────────────────────────────────────────────────
theme:
  name: material
  language: es
  features:
    # Navegación
    - navigation.tabs           # Pestañas principales en la barra superior
    - navigation.sections       # Agrupa entradas en secciones colapsables
    - navigation.top            # Botón "volver arriba"
    - toc.follow                # TOC sigue el scroll
    # Búsqueda
    - search.suggest
    - search.highlight
    # Código
    - content.code.copy         # Botón copiar en bloques de código
    - content.code.annotate     # Anotaciones en código
    - content.tabs.link         # Tabs de código sincronizadas

# ── Plugins ──────────────────────────────────────────────────────────────────
plugins:
  - search:
      lang: es

  # Opcional: muestra fecha de última modificación
  - git-revision-date-localized:  # pip install mkdocs-git-revision-date-localized
      type: date

  # Obligatorio si el proyecto es Python (docstrings → HTML)
  - mkdocstrings:               # pip install mkdocstrings[python]
      handlers:
        python:
          paths: [src]
          options:
            show_source: true
            show_root_heading: true

# ── Extensiones Markdown ─────────────────────────────────────────────────────
markdown_extensions:
  - admonition                  # Bloques de nota, warning, tip, etc.
  - tables
  - toc:
      permalink: true           # Anclas en encabezados

  # Resaltado de código
  - pymdownx.highlight:
      use_pygments: true
      anchor_linenums: true
  - pymdownx.inlinehilite

  # Bloques de código con Mermaid
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format

  - pymdownx.snippets           # Incluir fragmentos de otros archivos
  - pymdownx.emoji:             # Emojis :material-check:
      emoji_index: !!python/name:pymdownx.emoji.twemoji
      emoji_generator: !!python/name:pymdownx.emoji.to_svg

# ── Extras ───────────────────────────────────────────────────────────────────
extra:
  version:
    provider: mike              # pip install mike (versionado multi-versión)
  # Publicar versión: mike deploy [X.Y.Z] latest --update-aliases
  social:                       # Opcional
    - icon: fontawesome/brands/github
      link: https://github.com/[usuario]/[repo]

# ── Navegación (Obligatoria) ─────────────────────────────────────────────────
nav:
  - Inicio: index.md

  - Guías:
      - Inicio Rápido: [guia-rapida].md
      - Próximos Pasos: NEXT_STEPS.md
      - Arquitectura Visual: ARCHITECTURE_VISUAL.md

  - Funcional:
      - Contratos Base: functional/base.md
      - [Módulo 1]: functional/[modulo1].md
      - [Módulo 2]: functional/[modulo2].md

  - Ejemplos:
      - Inicio: examples/README.md
      - API y CLI:
          - [Ejemplo 1]: examples/[ejemplo1].md
      - Herramientas de IA:
          - [Guía IA]: examples/[guia-ia].md

  - API & Referencias:
      - Técnica:
          - Contratos Base: api/base.md
          - [Módulo 1]: api/[modulo1].md
      - Compatibilidad: COMPATIBILITY.md
      - Changelog: CHANGELOG.md
      - Troubleshooting: TROUBLESHOOTING.md
```

---

### 4.2 Navegación de util_bbdd (Implementación Actual)

Mapeo concreto del proyecto sobre la estructura anterior.
La fuente canónica de la navegación es siempre `mkdocs.yml`; este bloque refleja
los grupos principales como referencia rápida:

```yaml
nav:
  - Inicio: index.md
  - Instalación: INSTALLATION.md

  - Documentación Funcional:
      - Managers:
          - Gestión de Conexiones (Sync): functional/managers-sync.md
          - Ciclo de vida de sesión sincrónica: functional/managers-sync-session-lifecycle.md
          - Gestión de Conexiones (Async): functional/managers-async.md
      - Metadatos e Introspección:
          - Extracción de Metadatos: functional/metadata-extraction.md
          - Selección de Driver: functional/drivers-selection.md
      - Operaciones de Datos:
          - Operaciones Bulk (CRUD): functional/bulk-operations.md
          - Auditoría de Operaciones Bulk: functional/bulk-audit.md
      - Queries y Validación:
          - Registro de Queries: functional/query-registry.md
          - Ejecución de Consultas: functional/query-execution.md
          - Patrón de Validadores: functional/validators-pattern.md
      - Comparación de Esquemas:
          - Comparador de Esquemas: functional/schema-comparison.md
      - Migración de Esquemas:
          - Migración Oracle (origen): functional/migrate-oracle-mariadb.md
          - Migración MariaDB (origen): functional/migrate-mariadb-source.md
          - Migración SQL Server (origen): functional/migrate-sqlserver-source.md
          - Migración PostgreSQL (origen): functional/migrate-postgresql-source.md
      - Análisis de Relaciones:
          - Visualización de Grafos: functional/graph-analysis.md
      - Documentación de BD:
          - Generación de Documentación: functional/database-documentation.md

  - Referencia Técnica:
      - Managers: api/managers-sync.md  # y otros bajo api/managers-*.md
      - Metadatos: api/metadata-manager.md
      - Conexiones: api/connection-factory.md
      - Bulk: api/bulk-crud.md
      - Queries: api/query-system.md
      - Migración: api/migrate-oracle-mariadb.md  # y otros bajo api/migrate-*.md
      - Análisis: api/analysis.md
      - Documentación BD: api/database-documentation.md
      - Excepciones: api/exceptions.md

  - Ejemplos:
      - Conectar e Introspeccionar: examples/example-connect-introspect.md
      - Bulk Insert desde CSV: examples/bulk_insert_csv.md
      - Comparación de Esquemas: examples/schema_comparison.md
      - Migración Oracle (origen): examples/migrate-oracle-mariadb.md
      - Migración MariaDB (origen): examples/migrate-mariadb-source.md
      # ... resto de ejemplos en mkdocs.yml

  - Guías:
      - Programación Asíncrona: ASYNC_GUIDE.md
      - Drivers PostgreSQL: POSTGRESQL_DRIVER_GUIDE.md
      - Excepciones: EXCEPTIONS.md
      - Troubleshooting: TROUBLESHOOTING.md
      - Herramientas IA: examples/doc_generation_vscode_guide.md
      # ... resto en mkdocs.yml
```

---

### 4.3 Secciones Opcionales (Agregar según necesidad)

| Sección | Ubicación | Cuándo agregar |
|---------|-----------|----------------|
| **Seguridad** | `docs/security/` | Proyectos con auth, datos sensibles o auditoría |
| **Tutoriales** | `docs/tutorials/` | Curvas de aprendizaje complejas |
| **FAQ** | `docs/faq.md` | Preguntas frecuentes por módulo |
| **Glosario** | `docs/glossary.md` | Dominio específico con muchos términos |
| **Web Interface** | `docs/web-interface.md` | Si el proyecto tiene UI web |
| **Arquitectura Web API** | `docs/architecture/web-api.md` | Si existe `src/**/web/` con FastAPI/Flask/etc. |
| **Microservicios** | `docs/architecture/microservices.md` | Si el proyecto expone o consume múltiples servicios |
| **Docker / Contenedores** | `docs/architecture/docker.md` | Si existe `Dockerfile` o `docker-compose.yml` en el repo |
| **Contributing** | `docs/contributing.md` | Proyectos open source |

---

## 5. Roles de Agentes y Flujo de Trabajo

### Flujo Recomendado para Documentación

| Fase | Agente | Tarea | Entrada | Salida |
|------|--------|-------|---------|--------|
| **1. Planificación** | `Plan Architect` | Validar estructura actual vs propuesta | `mkdocs.yml` + código fuente | `PLAN` + `AUDIT_PLAN` |
| **2. Validación IA** | `config-reviewer` | Revisar coherencia en `CLAUDE.md`, `copilot-instructions.md` | Archivos IA | Findings + recomendaciones |
| **3. Exploración** | `Explore` | Mapear módulos existentes vs faltantes | `src/`, `docs/` | Matriz de cobertura |
| **4. Generación** | `documentation-generator` | Crear/actualizar docs funcional + técnica | Código fuente + prompts | Archivos en `docs/` + `mkdocs.yml` |
| **5. Auditoría** | `documentation-reviewer` | Validar completitud, ejemplos, coherencia | Docs generadas | Findings + mejoras |
| **6. Integración** | `Code Auditor` | Validar `mkdocs build` y no rompe refs | Output de build | Reporte |
| **7. Cierre** | `Version Closer` | Sincronizar `CHANGELOG.md` + `COMPATIBILITY.md` | Cambios completados | Release notes |

### Cuándo Usar Cada Agente

| Agente | Cuándo | Comando | Scope |
|--------|--------|---------|-------|
| `documentation-generator` | Generar docs por primera vez o actualizar módulo completo | `/new-feature "generar doc [módulo]"` | `src/` → `docs/` |
| `documentation-reviewer` | Auditar docs existentes (calidad, ejemplos, claridad) | `/audit-code` | `docs/functional/`, `docs/api/` |
| `config-reviewer` | Sincronizar instrucciones IA entre archivos de configuración | `/config-review` | `CLAUDE.md`, `copilot-instructions.md` |
| `Plan Architect` | Cambio estructural en `mkdocs.yml` o nuevo módulo importante | `/new-feature` o `/refactor` | `mkdocs.yml` |

---

## 6. Restricciones y Decisiones

### Restricciones Generales

- ✅ **MkDocs v1.5+** — No usar versiones antiguas, usar Material theme
- ✅ **Diagramas Mermaid** — Agnóstico a Graphviz, integrado en mkdocs
- ✅ **Lenguaje agnóstico** — Ejemplos Python en carpetas separadas si hay múltiples lenguajes
- ✅ **NO inventar código** — Todos los ejemplos deben validarse contra `src/`
- ✅ **Encoding UTF-8** — Todos los archivos markdown
- ❌ **NO guardar en OneDrive o Google Drive** — Usar referencias internas al repositorio

### Decisiones Críticas

1. **Separación Funcional ↔ Técnica**: Cada módulo tiene 2 documentos separados, no mezcladas
   - Funcional: `docs/functional/[módulo].md` (usuario final)
   - Técnica: `docs/api/[módulo].md` (desarrollador)

2. **Ubicaciones Fijas** (No cambiar sin consenso):
   - Funcional: `docs/functional/[módulo].md`
   - Técnica: `docs/api/[módulo].md`
   - Ejemplos: `docs/examples/[caso].md` (estructura plana; sin subcarpetas por tipo)
   - Guías: `docs/[nombre].md` en raíz

3. **Actualización de mkdocs.yml**: Automatizada con `mkdocstrings` + agente `documentation-generator`

4. **Build CI/CD**: `mkdocs build` validado en cada PR, detecta links rotos

5. **Versionamiento**: Sincronizar CHANGELOG.md + COMPATIBILITY.md según `.github/instructions/sync.instructions.md`

---

## 7. Cómo Proceder

Los pasos corresponden 1:1 con las fases de §5.

### Paso 1: Planificar (20 min)
```text
@Plan Architect
Validar estructura docs/ vs mkdocs.yml real. Entregar PLAN + AUDIT_PLAN.
```

### Paso 2: Validar Configuración IA (30 min)
```text
@config-reviewer
Revisar coherencia propuesta vs código real en src/.
Validar que estructura propuesta es implementable.
```

### Paso 3: Explorar Módulos (15 min)
```text
@Explore
Mapear módulos en src/ vs docs/. Identificar faltantes. Solo lectura.
```

### Paso 4: Generar/Actualizar Documentación (1-2 h)
```text
@documentation-generator
Generar docs para módulo específico O proyecto completo.
Actualiza mkdocs.yml automáticamente.
```

### Paso 5: Auditar Documentación (30 min)
```text
@documentation-reviewer
Validar ejemplos contra código real.
Verificar coherencia, completitud, claridad.
Reportar mejoras.
```

### Paso 6: Integración y Build (15 min)
```text
@Code Auditor
Ejecutar mkdocs build. Verificar links. Reportar errores de build.
```

### Paso 7: Sincronizar Versión (20 min)
```text
@Version Closer
Actualizar CHANGELOG.md, COMPATIBILITY.md.
Generar release notes.
```

### Criterio de Completitud

La estandarización se considera **completa** cuando:

- [ ] `mkdocs build` finaliza sin errores ni warnings de links rotos
- [ ] Todos los módulos en `src/` tienen doc funcional (`docs/functional/`) y técnica (`docs/api/`)
- [ ] Todos los archivos referenciados en `docs/examples/` existen en disco
- [ ] `CHANGELOG.md` y `COMPATIBILITY.md` reflejan la versión actual de `pyproject.toml`
- [ ] Las instrucciones IA (`CLAUDE.md`, `copilot-instructions.md`) son coherentes con el código real

---

## 📎 Referencias Internas

- [`.github/SHARED_INSTRUCTIONS.md`](.github/SHARED_INSTRUCTIONS.md) — Fuente canónica de arquitectura
- [`CLAUDE.md`](CLAUDE.md) — Instrucciones para Claude Code
- [`.github/copilot-instructions.md`](.github/copilot-instructions.md) — Instrucciones para Copilot Chat
- [`.github/instructions/docs.instructions.md`](.github/instructions/docs.instructions.md) — Guía de estilo para documentación
- [`pyproject.toml`](pyproject.toml) — Versión actual del proyecto
- [`.ai/product.md`](.ai/product.md) — Contexto de producto
- [`mkdocs.yml`](mkdocs.yml) — Configuración actual de MkDocs
- [`.github/instructions/sync.instructions.md`](.github/instructions/sync.instructions.md) — Sincronización de versiones
