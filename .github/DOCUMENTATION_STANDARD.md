# 📚 Estándar de Documentación

Estándar canónico de la documentación de **util_bbdd**: arquetipos, configuración de `mkdocs.yml`,
roles de los agentes de documentación y criterios de completitud. Reglas de edición por ruta
(Markdown, Mermaid, snippets, `nav`): `.github/instructions/docs.instructions.md`. Reglas comunes a
todas las plataformas IA: `.github/SHARED_INSTRUCTIONS.md` § «Documentación obligatoria».

---

## 1. Objetivo

Estandarizar la documentación para asegurar:
- **Claridad de usuario**: documentación funcional orientada a "qué puedo hacer"
- **Claridad de desarrollador**: documentación técnica orientada a "cómo funciona internamente"
- **Mantenibilidad**: estructura fija por arquetipo, fácil de auditar y actualizar
- **Automatización**: generación con el agente Documentation Generator y validación con `zensical build --strict` en CI
- **Versionamiento**: sincronización de `CHANGELOG.md` y `pyproject.toml` con cada release

---

## 3. Arquetipos

Este apartado es la **definición canónica** de los arquetipos. `.github/instructions/docs.instructions.md`
solo añade reglas de edición por ruta (Markdown, Mermaid, snippets, `nav`) y remite aquí.

**Regla de sección vacía** (todos los arquetipos): si una sección no tiene contenido, escribe
`*No aplica para este módulo.*` — nunca la omitas.

### 3.1 Arquetipo 1 — Documentación Funcional (`docs/functional/`)

**Propósito**: Responder "¿Qué hace y por qué?"

**Audiencia**: Product Owner, QA, jefes de proyecto y responsables de negocio.

**Ubicación**: `docs/functional/[módulo].md` · **Prompt**: `.github/prompts/functional_doc.prompt.md`

**Estructura obligatoria** (8 secciones numeradas, en este orden). La fuente es
`.github/prompts/functional_doc.prompt.md` (núcleo compartido por bootstrap); si difieren, manda el prompt:

```
# [Título del Módulo/Funcionalidad]

## 1. Objetivo y Descripción
2-3 párrafos sin jerga técnica: qué problema resuelve, qué valor aporta y por qué existe.

## 2. Precondiciones
Lo que debe existir o estar configurado antes de usar la funcionalidad (un ítem por precondición).

## 3. Flujo Principal
Diagrama Mermaid sequenceDiagram (máximo 12 nodos) + párrafo que describe el flujo paso a paso.

## 4. Postcondiciones y Efectos
Estado observable tras la operación: registros creados/modificados, artefacto producido,
transacciones confirmadas o revertidas, cachés afectadas.

## 5. Reglas de Negocio
Tabla: | Regla | Descripción | Impacto si se viola |

## 6. Límites, Flujos Alternativos y Casos Especiales
### Qué NO hace esta funcionalidad
### Flujos alternativos
### Casos especiales

## 7. Criterios de Aceptación
Tabla: | ID | Dado | Cuando | Entonces |  (derivados del código cuando sea posible)
### Pendiente de validación QA  (solo si algún criterio no puede derivarse del código)

## 8. Glosario de Dominio
Tabla: | Término | Definición |
```

> **Migración pendiente**: los 19 documentos de `docs/functional/` siguen la estructura anterior de 4
> secciones (Descripción General · Reglas de Negocio · Casos de Uso · Glosario). Se migran por área con
> Documentation Generator al regenerarlos; hasta entonces no se consideran incumplimiento en revisión.

**Reglas de lenguaje**:

- Terminología de negocio, no técnica; sin jerga técnica sin explicación.
- No menciones nombres de clases internas, variables ni rutas de implementación.
- Legible por un responsable de proyecto sin conocimientos del lenguaje de implementación.

**Diagramas recomendados**: `sequenceDiagram` (flujo principal), `flowchart TD` (decisiones).

---

### 3.2 Arquetipo 2 — Documentación Técnica (`docs/api/`)

**Propósito**: Responder "¿Cómo está construido?"

**Audiencia**: desarrolladores, ingenieros de datos, DBAs y equipo de mantenimiento.

**Ubicación**: `docs/api/[módulo].md` · **Prompt**: `.github/prompts/technical_doc.prompt.md`

Las páginas que solo contienen directivas autodoc de `mkdocstrings` están excluidas de este arquetipo.

**Estructura obligatoria** (secciones numeradas, en este orden):

```
# [Nombre del Componente/Módulo]

[Párrafo introductorio de una frase: responsabilidad exacta del módulo.]

## 1. Arquitectura y Diseño
Diagrama Mermaid (flowchart TD, classDiagram, sequenceDiagram o architecture-beta
según los criterios de docs.instructions.md § Mermaid). Máximo 12 nodos.

## 2. API Reference
### Autodoc
Directiva de generación automática (Python: ::: util_bbdd.modulo.Clase).
Solo exportados en __all__. Nunca implementación interna.
### Contratos
Tabla API pública: | Función/Clase | Firma simplificada | Descripción | Retorna |
Tabla entrada:     | Parámetro | Tipo | Descripción | Restricciones |
Contrato de salida: tipos, estructura y casos especiales.
Errores y casos especiales: excepciones propias del módulo.

## 3. Componentes y Clases
Responsabilidad de cada clase o función principal exportada.
Para módulos con una sola clase/función: "No aplica para este módulo."

## 4. Dependencias y Requisitos
Tabla: | Dependencia | Propósito | Requerida | Comportamiento sin ella |

## 5. Ejemplos Relacionados      ← OBLIGATORIO (enlace bidireccional con Arquetipo 4 §5)
Lista de enlaces a docs/examples/ con descripción de lo que ilustra cada uno.
Si no existe ningún ejemplo del módulo: "Pendiente — crear ejemplo en docs/examples/[nombre].md"
```

**Reglas de lenguaje**:

- Preciso, con los tipos de Python explícitos.
- Solo lo exportado públicamente; no documentes implementación interna.
- Sin comentarios triviales sobre el código.

---

### 3.3 Arquetipo 3 — Guías de Usuario o Configuración (`docs/guides/`)

**Propósito**: Responder "¿Cómo se usa/instala/opera?" (marco Diátaxis: how-to o tutorial).

**Audiencia**: usuarios finales, operadores y desarrolladores que necesitan una guía how-to.

**Ubicación**: `docs/guides/[nombre_guia].md` (siempre en `guides/`, minúsculas con guiones bajos) ·
**Prompt**: `.github/prompts/guide_doc.prompt.md`

**Estructura obligatoria** (secciones numeradas, en este orden):

```
# [Guía de X / Tutorial de Y]

## 1. Objetivo
Qué conseguirás al seguir esta guía (1 párrafo). Distingue how-to ("instalar X") vs tutorial ("entender X").

## 2. Requisitos Previos
Lista: herramientas, versiones, accesos o estado inicial requerido.

## 3. Pasos
Procedimiento secuencial numerado con bloques de código. Cada paso atómico y verificable.

## 4. Verificación
Comando + output esperado para confirmar éxito.

## 5. Variantes y Solución de Problemas
Tabla: | Escenario/Error | Causa probable | Solución |
Incluye alternativas al flujo principal y configuraciones opcionales.
Si no hay casos conocidos: "No aplica para este módulo."
```

**Reglas de lenguaje**:

- Orientado a la acción: verbos imperativos ("instala", "ejecuta", "verifica").
- `## 1. Objetivo` en 1 párrafo; nunca omitirlo.
- Siempre un comando de verificación real en `## 4.`.
- En `## 5.` solo errores o variantes conocidos y documentados.

---

### 3.4 Arquetipo 4 — Guías de Ejemplos de Código (`docs/examples/`)

**Propósito**: Responder "¿Cómo se implementa?"

**Audiencia**: desarrolladores que quieren implementar un patrón concreto.

**Ubicación**: `docs/examples/[nombre].md` (plano; el código en `docs/examples/[nombre].py` o
`docs/examples/database/[fragmento].py`) · **Prompt**: `.github/prompts/example_doc.prompt.md`

**Estructura obligatoria** (secciones numeradas, en este orden):

```
# Ejemplo: [Nombre del Patrón/Funcionalidad]

## 1. Contexto del Ejemplo
Qué problema concreto resuelve este código (1-2 párrafos).

## 2. Implementación de Referencia
Snippet con --8<-- "examples/[ruta].py" (ruta relativa a docs/).
Para fragmentos ilustrativos cortos: código inline.

## 3. Explicación del Código
Puntos críticos: concurrencia, rendimiento, contratos, decisiones no obvias.
Para ejemplos triviales: "No aplica para este módulo."

## 4. Ejecución y Pruebas
Comando exacto + output esperado si es determinista.
Validación sintáctica: python -m py_compile docs/examples/[nombre].py

## 5. Referencias Relacionadas      ← OBLIGATORIO (enlace bidireccional con Arquetipo 2 §5)
- Documentación funcional: [enlace a docs/functional/...]
- Referencia técnica: [enlace a docs/api/...]
- Ejemplos relacionados: [otros ejemplos del mismo área si existen]
```

**Reglas de lenguaje**:

- En `## 2.` usa `--8<--` para ficheros ejecutables de 30 líneas o más; código inline solo para ilustraciones.
- Si el fichero de código no existe, créalo antes de referenciarlo.
- `## 5.` siempre presente; enlaza al menos a la referencia técnica correspondiente.

---

### 3.5 Arquetipo 5 — Decisión Arquitectónica / ADR (`docs/adr/`)

**Propósito**: Responder "¿Por qué se decidió así?"

**Audiencia**: arquitectos de software, tech leads, responsables de plataforma.

**Ubicación**: `docs/adr/ADR-[NNN]-[nombre].md` (plantilla: `docs/adr/ADR-TEMPLATE.md`) ·
**Prompt**: `.github/prompts/architecture_doc.prompt.md`

**Estructura obligatoria** (secciones numeradas, en este orden):

```
# [ADR-NNN: Título de la Decisión]

## 1. Contexto y Problema
Qué situación motivó la decisión. Estado del sistema antes de la decisión.

## 2. Decisión
Qué se decidió hacer y por qué se eligió sobre las alternativas.

## 3. Consecuencias
Ventajas, compromisos (trade-offs) y deuda técnica aceptada.

## 4. Alternativas Consideradas
Tabla: | Alternativa | Pros | Contras | Motivo de rechazo |

## 5. Estado y Revisión
Estado: PROPUESTO | ACEPTADO | OBSOLETO | REEMPLAZADO POR [ADR-NNN]
Fecha de última revisión.
```

Documenta **una decisión concreta con trade-offs**, no la visión global del sistema (esa es la
Variante C del Arquetipo 6). Los documentos de planificación (roadmap, release plans) se marcan con
`<!-- arquetipo: informativo-libre -->` y quedan exentos.

---

### 3.6 Arquetipo 6 — Páginas de Navegación Principal (`docs/` raíz)

**Propósito**: Responder "¿Qué es, cómo lo instalo y cómo está organizado?" en las páginas de entrada.

**Audiencia**: cualquier visitante que llega a la documentación por primera vez.

**Ubicación**: `docs/index.md` (Inicio), `docs/INSTALLATION.md` (Instalación), `docs/architecture.md`
(Arquitectura) · **Prompt**: `.github/prompts/landing_doc.prompt.md` (variantes A/B/C)

Estas páginas entran directamente en `nav:` (nivel raíz), no bajo `functional/`, `api/`, `examples/` ni `adr/`.

**Estructura obligatoria** (según variante):

```
# Variante A — Inicio (docs/index.md)
## 1. Identidad y Propósito
## 2. Capacidades Principales
## 3. Quick Start
## 4. Mapa de la Documentación
## 5. Compatibilidad y Soporte

# Variante B — Instalación (docs/INSTALLATION.md)
## 1. Requisitos Previos
## 2. Instalación del Paquete
## 3. Drivers por Motor
## 4. Verificación
## 5. Solución de Problemas

# Variante C — Arquitectura del sistema (docs/architecture.md) — modelo arc42-lite + C4
## 1. Visión General y Objetivos de Calidad   (arc42 1+3; incluye diagrama C4 nivel 1)
## 2. Mapa de Módulos (Building Blocks)        (arc42 5; C4 nivel 3)
## 3. Flujo en Ejecución (Runtime)             (arc42 6)
## 4. Conceptos Transversales y Estándares No Funcionales  (arc42 8+10; checklist NFR)
## 5. Decisiones, Extensión y Límites          (arc42 9+11; enlace a docs/adr/)
```

El checklist no funcional de la Variante C §4 cubre, como mínimo: Seguridad, Observabilidad,
Rendimiento, Compatibilidad, Robustez/Errores y Tipado/Calidad, anclando cada ítem a un mecanismo
real del código. La figura «Capas e imports reales» de `docs/architecture.md` se genera con
`scripts/gen_arquitectura_capas.py` (no se edita a mano).

**Distinción con otros arquetipos**:

- El Arquetipo 5 documenta **un ADR concreto**; la Variante C es la **vista panorámica** del sistema y
  enlaza al log de ADR. Ambas conviven bajo la sección `Arquitectura` del nav.
- El Arquetipo 3 cubre guías genéricas (async, drivers, troubleshooting); la Variante B es específica de
  instalación del paquete y drivers.

`docs/legacy-versions.md` permanece exento de arquetipo.

---

### 3.7 Arquetipo 7 — Guía de Incorporación para Desarrolladores (`docs/guides/onboarding_dev.md`)

**Propósito**: Responder "¿Cómo me incorporo al proyecto y pongo en marcha mi entorno?"

**Audiencia**: desarrolladores que se incorporan al proyecto por primera vez.

**Ubicación**: `docs/guides/onboarding_dev.md` (todos los proyectos — mismo convenio que el resto de guías)

**Prompt**: `.github/prompts/onboarding_dev.prompt.md`

**Secciones obligatorias** (11, en este orden):

```
## 1. Prerequisitos del Entorno      — tabla: Herramienta | Versión mínima | Verificar con | Notas
## 2. Obtener el Código              — clone, rama de trabajo, submódulos/dependencias privadas
## 3. Configurar el Entorno          — venv/IDE, credenciales, registros privados, ficheros de config
## 4. Primera Compilación/Instalación — comando principal + tabla de errores frecuentes
## 5. Infraestructura Local           — BD, contenedores, servicios; "*No aplica*" si librería stateless
## 6. Ejecutar la Aplicación          — puertos, URLs, credenciales; "*No aplica*" si librería
## 7. Mapa del Código                 — árbol simplificado, responsabilidad por módulo/paquete, regla de capas
## 8. Convenciones y Herramientas     — lint, format, tipos, tests — verificar contra SHARED_INSTRUCTIONS.md
## 9. Flujo de Trabajo Git            — ramas, Conventional Commits, PR/MR
## 10. Verificación del Entorno       — tabla: Verificación | Comando | Output esperado
## 11. Recursos y Referencias         — .ai/*.md, docs/ relevantes, normativa, contacto
```

**Regla de sección vacía**: §5 y §6 **siempre** están presentes. Si el proyecto no requiere infraestructura o no tiene servidor, escribir `*No aplica para este proyecto.*` con explicación breve. Nunca omitir la sección.

**Distinción con Arquetipo 3** (Guías de Usuario):
- Arquetipo 3 documenta **cómo usar o configurar una funcionalidad** (guía how-to para usuarios finales).
- Arquetipo 7 documenta **cómo unirse al equipo de desarrollo** (entorno, código, convenciones, workflow).

**Cuándo actualizar**: en cada release mayor, tras cambios de stack o infraestructura, o cuando un nuevo desarrollador detecte que la guía está desactualizada.

---

### 3.8 Arquetipo 8 — Trazabilidad Normativa (`docs/normativa/`) — **Condicional**

**Propósito**: Responder "¿Qué obligaciones legales o reglamentarias están cubiertas por este sistema?"

**Condición de activación**: SOLO si el proyecto hace referencia explícita a leyes, decretos,
directivas, normas UNE o cualquier normativa de obligado cumplimiento. Verificar en `.ai/product.md`
o `README.md`. Si no hay normativa de referencia → **este arquetipo no aplica** y la carpeta
`docs/normativa/` no se crea.

> **Este proyecto (util_bbdd)**: librería Python de operaciones de base de datos sin normativa de
> referencia explícita. El arquetipo no aplica actualmente. Si en el futuro se incorpora
> normativa (ej. RGPD, LOPD-GDD para datos procesados, normas de accesibilidad), aplicar entonces.

**Audiencia**: auditores de cumplimiento, técnicos de normativa, responsables de proyecto.

**Ubicación**: `docs/normativa/<abbrev_norma>_traceability.md`  
**Naming**: nombre en minúsculas con guión bajo (ej. `ley39_rd174_traceability.md`, `rgpd_traceability.md`)

**Estructura obligatoria** (secciones en este orden):

```
# Trazabilidad Normativa — <Nombre de las normas>

(versión del sistema analizado + fecha de revisión)

## Propósito

## 1. <Norma A> — <Nombre corto>
  ### 1.1 <Grupo de artículos>
  Tabla: | Artículo | Obligación | Módulo/servicio | Doc de referencia | Cobertura |
  ### ...

## 2. <Norma B> — ...

## N. Resumen de gaps por severidad
  ### Nivel 1 — Crítico (riesgo de incumplimiento o auditoría bloqueada)
  Tabla: | ID | Gap | Norma | Módulo afectado | Acción recomendada |
  ### Nivel 2 — Importante (gap documental, dificulta mantenimiento)
  ### Nivel 3 — Mejora

## N+1. Normativa complementaria referenciada
Tabla: | Norma | Objeto | Cobertura en el sistema |

## N+2. Próximas acciones priorizadas
```

**Leyenda de cobertura**:

| Símbolo | Significado |
|---------|-------------|
| ✅ | Cubierto — implementado y documentado |
| ⚠️ | Parcial — implementado pero con gap documental o funcional conocido |
| ❌ | Gap — no implementado o sin documentación verificable |
| 🔍 | A verificar — evidencia insuficiente para determinar cobertura |

**Sección MkDocs** (solo si el arquetipo aplica):

```yaml
- Normativa:                                                     # Entre "Funcional" y "Arquitectura"
    - Trazabilidad <Nombre norma>: normativa/<codigo>_traceability.md
```

**Cuándo crear**: al comenzar el proyecto si la normativa es conocida desde el inicio, o en la
primera auditoría de cumplimiento formal.

**Cuándo actualizar**:
- Cuando cambia la normativa de referencia (modificación legal, nuevo artículo)
- Cuando se implementa un módulo que cubre un gap documentado
- En cada revisión de versión mayor que afecte lógica de negocio regulada

**Restricciones estrictas**:
- No inventar contenido normativo sin verificar contra el texto oficial
- Marcar como 🔍 cualquier artículo sin evidencia suficiente en código o documentación
- No documentar como ✅ ningún artículo sin módulo del sistema identificado
- No copiar texto legal verbatim; describir la obligación en términos del sistema

**Prompt de generación**: `.github/prompts/normative_traceability.prompt.md`

---

### 3.9 Estándar de la Sección Guías (`docs/guides/`)

Esta sección define el contrato mínimo y las reglas de nomenclatura para **todos los proyectos**.

#### Convenio de nombres

| Regla | Correcto | Incorrecto |
|---|---|---|
| Nombre en minúsculas | `connection_guide.md` | `CONNECTION_GUIDE.md` |
| Palabras con guión bajo | `async_guide.md` | `async-guide.md`, `asyncGuide.md` |
| Ubicación siempre en `guides/` | `docs/guides/troubleshooting.md` | `docs/TROUBLESHOOTING.md` |
| Sin subcarpetas dentro de `guides/` | `guides/deployment_guide.md` | `guides/ops/deployment.md` |

#### Conjunto mínimo obligatorio

| Fichero | Arquetipo | Contenido | Mandatorio |
|---|---|---|---|
| `guides/onboarding_dev.md` | 7 | Incorporación: entorno, código, convenciones, verificación | ✅ Siempre |
| `guides/troubleshooting.md` | 3 | Problemas frecuentes por categoría + solución verificable | ✅ Siempre |

#### Guías adicionales según tipo de proyecto

| Tipo de proyecto | Guías recomendadas |
|---|---|
| Librería Python (util_bbdd) | `connection_guide.md`, `async_guide.md`, `exceptions.md`, `migration_guide.md`, + guías de drivers y herramientas IA |
| Aplicación con servidor | `deployment_guide.md` |
| Cualquier proyecto con herramientas IA | Subsección "Herramientas IA" en Guías: claude_code_guide.md, codex_guide.md, etc. |

#### Estructura de la sección en `mkdocs.yml`

```yaml
- Guías:
    - Incorporación para Desarrolladores: guides/onboarding_dev.md   # Siempre primero
    - [Grupos operativos según el proyecto]:                           # Conexión, Despliegue, etc.
        - [Guía específica]: guides/[nombre_guia].md
    - Errores y Diagnóstico:
        - Troubleshooting: guides/troubleshooting.md                  # Siempre en esta subsección
    - Herramientas IA:                                                 # Si el proyecto usa herramientas IA
        - [Nombre herramienta]: guides/[tool]_guide.md
```

#### Cuándo actualizar

- Al incorporar el primer desarrollador externo → generar `onboarding_dev.md` si no existe.
- Tras cambios de stack, build tool o infraestructura → actualizar `onboarding_dev.md`.
- Cuando se reporta un error no documentado → añadir a `troubleshooting.md`.
- Cuando se añade una herramienta IA nueva → añadir su guía en Herramientas IA.

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
  - Inicio: index.md                       # Arquetipo 6, Variante A
  - Instalación: INSTALLATION.md           # Arquetipo 6, Variante B
  - Documentación Funcional:
      - [Área]:
          - [Módulo]: functional/[modulo].md
  - Referencia Técnica:
      - [Área]:
          - [Módulo]: api/[modulo].md
  - Guías:
      - Incorporación para Desarrolladores: guides/onboarding_dev.md
      - [Tema]:
          - [Guía]: guides/[nombre_guia].md
      - Errores y Diagnóstico:
          - Troubleshooting: guides/troubleshooting.md
  - Ejemplos:
      - [Área]:
          - [Ejemplo]: examples/[nombre].md
  - Arquitectura:
      - Arquitectura del sistema: architecture.md   # Arquetipo 6, Variante C
      - [ADR-NNN]: adr/[ADR-NNN-nombre].md         # Arquetipo 5
  - Historia y Planes:
      - Versiones Históricas: legacy-versions.md
      - Roadmap: ROADMAP.md
```

---

### 4.2 Navegación de util_bbdd

La navegación real está **solo** en `mkdocs.yml` (no se copia aquí para que no diverja). Secciones de
primer nivel y agrupación en subsecciones: `docs.instructions.md` § «Generador estático».

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
| **Normativa** | `docs/normativa/` | **Solo** si el proyecto referencia leyes, decretos o normativas de obligado cumplimiento (Arquetipo 8) |

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
| **6. Verificación de config** (opt-in `--verify-tools`) | `documentation-generator` | Fetch webs oficiales — validar plugins y versiones en `mkdocs.yml` | Config + webs MkDocs/Zensical/PyPI | Discrepancias por severidad |
| **6b. Verificación de build** (opt-in `--verify-build`) | `documentation-generator` | Build + inspección HTML generado — alias bug, snippets, Mermaid, nav | `site/` (Modo A) o `localhost:8000` (Modo B `--serve`) | Hallazgos por página + acciones recomendadas |
| **7. Cierre** | `Version Closer` | Escribe `CHANGELOG.md` y el `TRACEABILITY.md` de la sesión; verifica `pyproject.toml` | Cambios completados | Release notes |

### Cuándo Usar Cada Agente

| Agente | Cuándo | Comando | Scope |
|--------|--------|---------|-------|
| `documentation-generator` | Generar docs por primera vez o actualizar módulo completo | Sin slash command: lenguaje natural (Claude Code) · `@Documentation Generator` (Copilot) | `src/` → `docs/` |
| `documentation-reviewer` | Auditar docs existentes (calidad, ejemplos, claridad) | Sin slash command: lenguaje natural (Claude Code) · `@Documentation Reviewer` (Copilot) | `docs/` |
| `config-reviewer` | Sincronizar instrucciones IA entre archivos de configuración | `/config-review` (Claude Code) · `@Config Reviewer` (Copilot) | `SHARED_INSTRUCTIONS.md`, entry points, agentes, prompts |
| `Plan Architect` | Cambio estructural en `mkdocs.yml` o nuevo módulo importante | `/new-feature` o `/refactor` | `mkdocs.yml` |

---

## 6. Restricciones y Decisiones

### Restricciones Generales

- ✅ **Zensical** (por defecto, CI) o **MkDocs Material** — mismo `mkdocs.yml`; no se usa `zensical.toml`
- ✅ **Diagramas Mermaid** — Agnóstico a Graphviz, integrado en mkdocs
- ✅ **NO inventar código** — Todos los ejemplos deben validarse contra `src/`
- ✅ **Encoding UTF-8** — Todos los archivos markdown
- ❌ **Sin APIs de IA externas** para generar documentación (`SHARED_INSTRUCTIONS.md` § «Estándar de generación documental»)

### Decisiones Críticas

1. **Separación Funcional ↔ Técnica**: Cada módulo tiene 2 documentos separados, no mezcladas
   - Funcional: `docs/functional/[módulo].md` (usuario final)
   - Técnica: `docs/api/[módulo].md` (desarrollador)

2. **Ubicaciones Fijas** (No cambiar sin consenso):
   - Funcional: `docs/functional/[módulo].md`
   - Técnica: `docs/api/[módulo].md`
   - Ejemplos: `docs/examples/[caso].md` (ficheros **planos en disco**, sin subcarpetas por tipo).
     En `nav:` **se agrupan en subsecciones por área funcional**, igual que `Referencia Técnica`
     y `Documentación Funcional` (ver `docs.instructions.md` → "Agrupación en subsecciones por área").
   - Guías: `docs/guides/[nombre].md` (ficheros en carpeta `guides/`, **nombre siempre en minúsculas con guiones bajos**).
     En `nav:` **se agrupan en subsecciones temáticas** (Incorporación, Conexión y Drivers, Errores y Diagnóstico,
     Rendimiento, Migración de Versión, Herramientas IA…), no por módulo.

3. **Actualización de mkdocs.yml**: la hace el agente `documentation-generator` al crear, mover o retirar páginas (`mkdocstrings` solo genera el contenido de las páginas autodoc, no el `nav`)

4. **Build CI/CD**: `zensical build --strict` en CI (`.github/workflows/docs-zip-release.yml`); en local, `zensical build --strict` o `mkdocs build --strict`

5. **Versionamiento**: Sincronizar CHANGELOG.md + `pyproject.toml` según `.github/instructions/sync.instructions.md`

---

## 7. Criterio de Completitud

La estandarización se considera **completa** cuando:

- [ ] `zensical build --strict` (o `mkdocs build --strict`) finaliza sin errores ni warnings de links rotos
- [ ] Todos los módulos en `src/` tienen doc funcional (`docs/functional/`) y técnica (`docs/api/`)
- [ ] Todos los archivos referenciados en `docs/examples/` existen en disco
- [ ] `CHANGELOG.md` refleja la versión actual de `pyproject.toml`
- [ ] Las instrucciones IA (`CLAUDE.md`, `copilot-instructions.md`) son coherentes con el código real
- [ ] Todos los documentos en `nav:` (excepto `legacy-versions.md`) tienen exactamente las secciones numeradas de su arquetipo asignado (`index.md`, `INSTALLATION.md` y `architecture.md` se rigen por el Arquetipo 6)
- [ ] Las secciones vacías contienen `*No aplica para este módulo.*` en lugar de estar omitidas
- [ ] Los prompts `.github/prompts/guide_doc.prompt.md` y `example_doc.prompt.md` existen y son coherentes con Arquetipos 3 y 4

---

## 📎 Referencias Internas

- [`SHARED_INSTRUCTIONS.md`](SHARED_INSTRUCTIONS.md) — Fuente canónica común a todas las plataformas IA
- [`instructions/docs.instructions.md`](instructions/docs.instructions.md) — Reglas de edición por ruta en `docs/`
- [`instructions/sync.instructions.md`](instructions/sync.instructions.md) — Sincronización de versiones
- [`AGENTS.md`](AGENTS.md) — Registro de agentes y prompts de documentación
- [`../CLAUDE.md`](../CLAUDE.md) y [`copilot-instructions.md`](copilot-instructions.md) — Entry points por plataforma
- [`../mkdocs.yml`](../mkdocs.yml) — Navegación y configuración real
- [`../pyproject.toml`](../pyproject.toml) — Versión actual del proyecto
- [`../.ai/product.md`](../.ai/product.md) — Contexto de producto
