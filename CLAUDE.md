# Instrucciones para Claude Code — util_bbdd

Este fichero proporciona especialización a Claude Code cuando trabaja con util_bbdd,
incluyendo slash commands, hooks de desarrollo y configuración integrada.

---

## ⚠️ Contexto previo obligatorio

Lee **primero**:
- **`.github/SHARED_INSTRUCTIONS.md`** — Fuente canónica: arquitectura TIMELOG, SOLID, calidad,
  comandos, documentación, flujo de trabajo, Conventional Commits. **Esta es la base.**
- **Este fichero** — Especialización para Claude Code únicamente.

---

## Slash commands de Claude Code

Usa estos comandos para activar flujos estructurados con automatización integrada:

| Comando | Propósito | Entrada | Salida |
|---|---|---|---|
| `/new-feature` | Nueva funcionalidad | Descripción + módulos | PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION |
| `/hotfix` | Bug P1/P2 mínimo | Descripción + impacto | RCA → FIX → AUDIT_CODE → VERSION |
| `/refactor` | Refactor sin cambios funcionales | Área + objetivo | PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE |
| `/audit-code` | Auditoría técnica independiente | Rutas o cambios | Scope → Findings → Verdict |
| `/security-review` | Auditoría de seguridad | Áreas críticas | Findings by severity → Remediation |
| `/tech-debt` | Deuda técnica priorizada | Área o módulo | Findings por severidad → Plan de remediación |
| `/maturity-assessment` | Evaluación de madurez del repo | Área o evaluación completa | Executive summary → Findings → Maturity verdict |
| `/version-closure` | Cierre de versión | Sesión completada | Release notes → Changelog → Rollback → Handoff |

**Ejemplo de uso**:

```
/new-feature

Objetivo: Añadir soporte para exportación a Parquet en timelog/

Alcance: timelog/export_parquet.py (nuevo), tests/unit/timelog/test_export_parquet.py (nuevo)

Restricciones:
  - Mantener compatibilidad con exports existentes (Excel, CSV, JSON)
  - Usar pandas.DataFrame.to_parquet()
  - Documentación en docstrings + ejemplo en README
```

---

## Trasladar esta configuración IA a otro proyecto (bootstrap)

Para replicar este sistema de instrucciones IA (Claude / Gemini / Copilot / Cursor / Codex) en **otro
proyecto**, incluso de **otro lenguaje y arquitectura**, usa el prompt
[`.github/prompts/bootstrap_ai_config.prompt.md`](./.github/prompts/bootstrap_ai_config.prompt.md).
La auditoría posterior la hace el agente **Config Reviewer**.

### Método y dirección de la llamada

**Modelo PULL — se invoca desde el proyecto DESTINO**, apuntando a este repo como plantilla de
solo lectura. Motivo: la adaptación necesita el **código real del destino en contexto**; lanzarlo
desde el origen arrastraría supuestos de Python/util_bbdd. El lenguaje y la arquitectura del destino
son **parámetros de entrada**, no constantes.

```text
# Abre el PROYECTO DESTINO en Claude Code y escribe:

Lee y aplica .github/prompts/bootstrap_ai_config.prompt.md
Origen (solo lectura): c:\Desarrollo\python\libs\util_bbdd
Destino: <raíz de este proyecto>
Lenguaje/arquitectura destino: <p.ej. TypeScript + NestJS hexagonal>
Plataformas IA activas: Claude Code, Gemini, Copilot, Cursor, Codex
Fase: PLAN y AUDIT_PLAN únicamente.
```

### Capas y dirección de ficheros

| Capa | Acción | Ejemplos |
|---|---|---|
| **A — Metodología** | Copiar verbatim (revisar comandos embebidos) | `.github/agents/`, `.github/prompts/`, `.claude/commands/`, `.ai/sessions/TEMPLATE/` |
| **B — Especialización** | Copiar + reescribir dominio | `SHARED_INSTRUCTIONS.md`, `CLAUDE.md`, `GEMINI.md`, `copilot-instructions.md`, `.cursorrules` |
| **C — Contexto** | Regenerar analizando el destino | `.ai/{product,architecture,runtime,glossary,standards}.md` |
| **D — No copiar** | Excluir | `.ai/sessions/<fechas>/`, `CHANGELOG.md`, caches, `settings.local.json` |

**Contexto obligatorio mínimo en el destino**: `SHARED_INSTRUCTIONS.md` reescrito, un entry point por
plataforma activa, `.ai/architecture.md` + `.ai/product.md`, núcleo de método (`new_feature`,
`hotfix`, `refactor`, `audit_code`, `version_closure` + agentes `plan-architect`, `code-auditor`,
`version-closer`) y `.ai/sessions/TEMPLATE/`. El resto es opcional e incremental.

---

## Configuración: Hooks y PostToolUse

Lee [`.claude/README.md`](./.claude/README.md) para detalles completos sobre hooks:

```
.claude/
  settings.json           ← Configuración: ruff, mypy, pytest hooks
  settings.json.example   ← Plantilla de ejemplo
  settings.local.json     ← Personalización local (no versionado, git-ignored)
  commands/               ← Slash commands personalizados
  EDGE_CASES.md           ← Casos límite conocidos en el proyecto
  TESTING_GUIDE.md        ← Guía de testing con PostToolUse
```

**Orden de ejecución automático típico**:

1. **Cambios de código** → `ruff format src tests` (aplicar formato)
2. **Validación estilo** → `ruff check src tests` (linting)
3. **Validación tipos** → `mypy src` (type-checking)
4. **Ejecución tests** → `pytest` (tests relevantes o suite completa)
5. **Retroalimentación** → Si fallan tests, Claude Code itera correcciones

**Configuración manual** (si es necesario):
```bash
# Instalar hooks locales en .claude/settings.local.json
# (no afecta otros clones del repositorio)
cp .claude/settings.json.example .claude/settings.local.json
# Edita .claude/settings.local.json con configuración personal
```

---

## Flujo estructurado de Claude Code

Cada slash command activa un flujo completo con fases definidas:

### `/new-feature`
```
Fase 1: PLAN → Analizar objetivo, alcance, riesgos, candidatos para cambio
Fase 2: AUDIT_PLAN → Verificar plan, detectar expansion, validar viabilidad
Fase 3: IMPLEMENT → Aplicar cambios, actualizar tests, ejecutar suite
Fase 4: AUDIT_CODE → Revisión independiente de calidad
Fase 5: VERSION → Changelog, commit message, rollback documentation
```

### `/hotfix`
```
Fase 1: RCA (Root Cause Analysis) → Identificar causa raíz del bug
Fase 2: FIX → Aplicar fix mínimo acotado (NO refactorizar)
Fase 3: AUDIT_CODE → Verificar fix, edge cases, pruebas
Fase 4: VERSION → Changelog, commit, rollback steps
Restricción: No refactorizar ni optimizar; solo fix
```

### `/audit-code`
```
Fase 1: Scope → Identificar archivos y responsabilidades
Fase 2: Findings → Hallazgos verificables (bugs, edge cases, contratos rotos)
Fase 3: Verdict → APROBADO | APROBADO CON CONDICIONES | RECHAZADO
Nota: Modo lectura; no edita código. Entrega hallazgos y recomendaciones.
```

### `/tech-debt`
```
Fase 1: Scope → Identificar módulo o área con deuda acumulada
Fase 2: Findings → Clasificar deuda por severidad (alta / media / baja)
Fase 3: Plan → Ordenar por impacto/esfuerzo, proponer remediaciones acotadas
Nota: No aplica cambios; entrega plan de trabajo priorizado.
```

### `/maturity-assessment`
```
Fase 1: Scope → Inventariar estructura, contratos, tests y docs del repo
Fase 2: Findings → Evaluar madurez por área (arquitectura, tipado, cobertura, seguridad)
Fase 3: Verdict → Maturity level + blockers para publicación
Nota: Solo lectura; no edita código.
```

### `/version-closure`
```
Fase 1: Resumen → Consolidar todos los cambios de la sesión
Fase 2: Validación → Verificar CHANGELOG.md, COMPATIBILITY.md y zensical build (o mkdocs build)
Fase 3: Handoff → Release notes, commit message, rollback strategy;
         poblar ## Directrices para Futuras IAs en .ai/sessions/*/TRACEABILITY.md
Nota: Ver .github/instructions/sync.instructions.md para checklist obligatorio.
```

---

## Integración con Copilot Chat

Esta especialización es **compatible con agentes Copilot Chat**:

| Cambio en Claude Code | Auditoría en Copilot Chat | Propósito |
|---|---|---|
| `/new-feature` + IMPLEMENT (cambios acotados) | Code Auditor (agente) | Verificación independiente |
| `/new-feature` + documentación en `docs/` | Documentation Reviewer (agente) | Validar ejemplos y coherencia |
| Cambios en `.github/SHARED_INSTRUCTIONS.md` | Config Reviewer (agente) | Validar DRY y consistencia entre plataformas |

**Flujo bidireccional recomendado**:

1. **Claude Code**: `/new-feature` → completa PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
2. **Copilot Chat**: Code Auditor → verifica cambios de Claude Code independientemente
3. **Copilot Chat**: Version Closer → cierre final y changelog consolidado

**Comunicación entre plataformas**:
- Claude Code escribe cambios y ejecuta tests localmente
- Copilot Chat revisa y confirma que cambios son conformes (sin ejecutar)
- Si hay discrepancias, ambas plataformas usan SHARED_INSTRUCTIONS.md como fuente de verdad

---

## Comparativa: Claude Code vs. Copilot Chat

| Aspecto | Claude Code | Copilot Chat |
|---|---|---|
| **Invocación** | Slash commands (`/new-feature`, etc.) | Agentes con nombres + descripción |
| **Ejecución de tests** | Automática via PostToolUse (hooks) | Manual (run_task, run_in_terminal) |
| **Contexto inicial** | Archivo abierto + prompt slash command | Contexto seleccionado + agente name |
| **Mejor para** | Cambios estructurados, flujos completos | Consultas rápidas, auditorías independientes |
| **Ciclo de feedback** | Iterativo local (hosteado localmente) | Iterativo conversacional (en chat) |
| **Documentación** | `.claude/` (settings.json, TESTING_GUIDE.md) | `.github/copilot-instructions.md` |

---

## 📐 Arquetipos Formales de Documentación

Toda documentación en util_bbdd sigue **7 arquetipos formales** definidos en [`.github/DOCUMENTATION_STANDARD.md`](./.github/DOCUMENTATION_STANDARD.md#3-propuesta-de-cambios):

| Arquetipo | Propósito | Ubicación | Prompt | Secciones |
|---|---|---|---|---|
| **1. Funcional** | ¿Qué hace y por qué? | `docs/functional/` | `functional_doc.prompt.md` | 1. Descripción · 2. Reglas · 3. Casos de Uso · 4. Criterios* · 5. Glosario |
| **2. Técnica/API** | ¿Cómo funciona internamente? | `docs/api/` | `technical_doc.prompt.md` | 1. Arquitectura · 2. Contratos · 3. Componentes · 4. Dependencias · 5. Ejemplos Relacionados ↔ |
| **3. Guía de Usuario** | ¿Cómo se usa/instala? | `docs/` raíz | `guide_doc.prompt.md` | 1. Objetivo · 2. Requisitos · 3. Pasos · 4. Verificación · 5. Variantes |
| **4. Ejemplos de Código** | ¿Cómo se implementa? | `docs/examples/` | `example_doc.prompt.md` | 1. Contexto · 2. Código (`--8<--`) · 3. Explicación · 4. Ejecución · 5. Referencias ↔ |
| **5. Decisión Arquitectónica** | ¿Por qué se decidió así? | `docs/adr/` | `architecture_doc.prompt.md` | Contexto → Decisión → Consecuencias → Alternativas → Estado |
| **6. Navegación Principal** *(variante)* | Intro + instalación + visión | `docs/index.md`, `INSTALLATION.md` | `landing_doc.prompt.md` | Variante A/B/C según tipo |
| **7. Onboarding Desarrolladores** | ¿Cómo me incorporo al proyecto? | `docs/ONBOARDING_DEV.md` | `onboarding_dev.prompt.md` | 1–4 Entorno · 5–6 Infra/App · 7 Mapa · 8 Convenciones · 9 Git · 10 Verificación · 11 Recursos |

**Características clave**:
- ✅ Secciones fijas: estructura inmutable (nunca omitir, escribir "No aplica" si vacío)
- ✅ Enlaces bidireccionales: Arquetipo 2 (§5) ↔ Arquetipo 4 (§5) obligatorios
- ✅ Multi-lenguaje: Arquetipos 2 y 7 soportan cualquier stack (Python, Java, TypeScript, Go…)
- ✅ Navegación: 7 secciones top-level exactas en `mkdocs.yml`

**Notas especiales**:
- Criterios de Aceptación (Arq.1 §4): Pendiente QA — placeholder hasta validación
- Documentación informativo-libre: Roadmaps/planes de release usan `<!-- arquetipo: informativo-libre -->` y quedan exentos

## Documentación con Claude Code

Usa el **Documentation Generator** (agente) como **único punto de entrada** para crear o actualizar
documentación, tanto de un módulo concreto como del proyecto completo.
No uses un único prompt masivo: trabaja siempre por fases separadas.

Sigue el **flujo estándar de 7 fases** definido en [`.github/DOCUMENTATION_STANDARD.md` §5](.github/DOCUMENTATION_STANDARD.md#5-roles-de-agentes-y-flujo-de-trabajo)
y la estructura de `DOCUMENTATION_STANDARD.md` §3 (funcional) y §3.2 (técnica).

### Flujo por fases

```
Fase 1 — Inventariar: leer src/, README, docs/, docs/examples/, mkdocs.yml
Fase 2 — Mapeo funcional (Senior Product Owner): objetivo de negocio, precondiciones, flujo, reglas
Fase 3 — Documentación técnica: responsabilidad, Mermaid, API pública, contratos, errores
Fase 4 — Ejemplos verificables: código real, resultado determinista, sin credenciales reales
Fase 5 — Sincronizar mkdocs.yml: añadir/mover/retirar entradas de navegación
Fase 6 — Revisión final: validar Markdown, enlaces relativos y sintaxis Mermaid
Fase 7 — Verificación de build (opt-in --verify-build): build del sitio + inspección del HTML generado
         Modo A (build): zensical build --strict / mkdocs build --strict → leer site/ con Read
         Modo B (serve):  zensical serve / mkdocs serve en background → WebFetch localhost:8000
```

### Solicitud para un módulo

```markdown
Lee [ruta_del_módulo] y genera documentación funcional y técnica.
Aplica .github/prompts/functional_doc.prompt.md y .github/prompts/technical_doc.prompt.md.
Guarda en docs/functional/[nombre].md y docs/api/[nombre].md.
Zensical renderiza automáticamente sin requiere actualización manual.
No inventes módulos ni capacidades; marca como pendiente lo no verificable.
```

### Solicitud para proyecto completo

```markdown
Revisa el proyecto completo y actualiza la documentación pública.
Fases: (1) inventariar módulos reales, (2) mapeo funcional (Senior PO),
(3) documentación técnica con Mermaid, (4) ejemplos verificables,
(5) Zenical renderiza automáticamente.
No inventes módulos ni capacidades; marca como pendiente lo no verificable.
No uses APIs de IA externas para generar contenido.
Opcional: añade `--verify-tools` para verificar plugins y versiones contra las webs oficiales.
```

### Contrato documental obligatorio

1. Revisar documentación existente antes de crear páginas nuevas; actualizar si el tema ya está cubierto.
2. Separar siempre los apartados **funcional**, **técnico** y **ejemplos** con secciones diferenciadas.
3. Usar Zensical como generador estático por defecto (o MkDocs Material, recíprocamente compatibles sobre el mismo `mkdocs.yml`); Mermaid.js para diagramas verificables.
4. Actualizar `mkdocs.yml` cuando se creen, muevan o eliminen páginas en `docs/`.
5. No inventar capacidades, módulos, APIs, salidas, errores ni dependencias.
6. Excluir **generación** de contenido documental delegando a LLMs o APIs de IA externas. Se permite consultar webs de referencia oficial (MkDocs, Zensical, PyPI) para verificar configuración, plugins y versiones (opción `--verify-tools`).

### Auditoría de documentación (solo lectura)

```markdown
Revisa docs/, docs/examples/, README y mkdocs.yml para detectar gaps.
Usa .github/prompts/documentation_review.prompt.md como criterio.
Entrega hallazgos con severidad (Nivel 1/2/3) sin editar archivos.
```
Criterio de completitud: `zensical build` sin errores + todos los módulos de `src/` documentados.

### Validación de Markdown — Checklist obligatorio

Ver `.github/SHARED_INSTRUCTIONS.md` § "Validación de Markdown en documentación" para directrices completas.

**Puntos críticos**:
- ✅ Listas: usar `- item` o `1. item`, NUNCA dos espacios al final de línea
  - ❌ `✅ Item 1  ` → Renderiza con `<br />` (horizontal)
  - ✅ `- ✅ Item 1` → Renderiza como `<ul><li>` (vertical)
- ✅ Enlaces a archivos estáticos: usar rutas relativas, NO placeholders
  - ❌ `[archivo.zip](#)`
  - ✅ `[archivo.zip](../util_bbdd.zip)` (desde `site/downloads/index.html` → apunta a `site/util_bbdd.zip`)
- ✅ Validar: `python -m mkdocs build --strict` sin errores
- ✅ Inspeccionar HTML: Revisar que `<ul><li>` se usan para listas, NUNCA `<p><br /></p>`

---

## 🗺️ Diagrama de Capas e Imports

La figura «Capas e imports reales» de `docs/architecture.md` se **genera desde el código**; no se edita a mano. Regla común y comandos: `.github/SHARED_INSTRUCTIONS.md` § «Diagrama de capas e imports».

```bash
python scripts/gen_arquitectura_capas.py          # mide imports con ast, verifica el dibujo y reescribe SVG + CSS
python scripts/gen_arquitectura_capas.py --edges  # tabla de imports medida (diagnóstico, no escribe nada)
```

**Cuándo ejecutarlo**: si tu cambio añade, mueve o elimina un paquete de primer nivel de `src/util_bbdd/` o un import entre ellos (típico en `/new-feature` y `/refactor`). Si falla, no fuerces la salida: sigue la regla común.

- Guía completa: [`docs/guides/architecture_diagram_guide.md`](./docs/guides/architecture_diagram_guide.md).

---

## 📦 Descarga de Documentación Offline

Util_bbdd proporciona **documentación en ZIP offline** con búsqueda integrada, SHA256 checksums y auto-publicación en GitHub Releases.

### Funcionalidades

✅ **Página de descargas**: https://fmanza.github.io/util_bbdd/downloads/  
✅ **ZIP comprimido**: ~2.5 MB (150+ archivos HTML)  
✅ **SHA256 Checksum**: Validación de integridad del archivo  
✅ **Auto-publicar**: GitHub Release automático en cada push a `main`/`develop`  
✅ **Búsqueda offline**: `search_index.json` incluido en ZIP  

### Comandos relacionados

```bash
# Generar ZIP localmente
python scripts/build_docs_zip.py

# Generar ZIP después de build (recomendado)
zensical build && python scripts/build_docs_zip.py

# Ver y validar checksums
cat dist/util_bbdd-docs-*.zip.sha256
sha256sum -c dist/*.sha256
```

### VS Code Tasks

```
Ctrl+Shift+P → "Run Task"
- docs: build + zip    # Genera ZIP con SHA256 automáticamente
```

### En GitHub Actions

El workflow `.github/workflows/docs-zip-release.yml` se ejecuta automáticamente:
1. En cada `push` a `main`/`develop` (si hay cambios en `docs/`)
2. Manualmente desde Actions UI

**Resultado**: Release con tag `docs-vX.X.X` + ZIP + checksums adjuntos

### Para otros proyectos (Bootstrap)

El sistema de descarga ZIP es **reutilizable** via bootstrap. Ver:
- `.github/prompts/bootstrap_ai_config.prompt.md` — Sección "📦 Descarga de Documentación Offline"
- Incluye matriz de equivalencias para Python, Node.js, Go, Java

---

## Checklist de sincronización

Cuando actualices **`.github/SHARED_INSTRUCTIONS.md`**, verifica:

- [ ] Ambos ficheros (CLAUDE.md y `.github/copilot-instructions.md`) contienen referencias sincronizadas
- [ ] No hay duplicación de reglas entre `SHARED_INSTRUCTIONS.md` y especializaciones
- [ ] Rutas de archivos son relativas (`./.github/`, `./.claude/`, no `file://...`)
- [ ] Tabla de gobernanza en SHARED_INSTRUCTIONS.md refleja responsabilidad de cada fichero
- [ ] Timestamps de actualización están sincronizados en ambos ficheros
- [ ] Si cambias slash commands, actualiza tabla de comandos en este fichero

---

## Comandos útiles referenciados

Consulta SHARED_INSTRUCTIONS.md para detalles completos:

```bash
python -m ruff check src tests      # Linting
python -m ruff format src tests     # Formato
python -m mypy src tests/unit/test_protocol_conformance.py   # Type-checking (2º arg: Protocols de la Regla #6)
python -m pytest                    # Tests
python -m build                     # Empaquetamiento
zensical serve                      # Documentación local (por defecto, lee mkdocs.yml)
mkdocs serve                        # Documentación local (recíproco, mismo mkdocs.yml)
python scripts/build_docs_zip.py    # Genera dist/util_bbdd-docs-{version}.zip para distribución offline
python scripts/gen_arquitectura_capas.py  # Regenera el diagrama de capas e imports (falla si no coincide con el código)
```

---

*Actualizado: 2026-09-22*
