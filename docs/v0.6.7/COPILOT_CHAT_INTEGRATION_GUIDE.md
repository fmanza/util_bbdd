# Guía de Adaptación: De Claude Code a Copilot Chat en VS Code

**Propósito**: Integración coherente de las instrucciones mejoradas en Copilot Chat (GitHub Copilot Chat en VS Code)
**Versión**: v0.6.7-dev
**Audiencia**: DevX, Leads técnicos, usuarios de Copilot Chat

---

## Contexto

El plan de mejoras en `docs/v0.6.7/CLAUDE_INSTRUCTIONS_IMPROVEMENT_PLAN.md` fue diseñado con **Claude Code** como foco principal (slash commands, hooks, settings.json). Sin embargo, la mayoría de desarrolladores usa **Copilot Chat en VS Code**.

Esta guía ayuda a:
1. Mapear slash commands de Claude Code a flujos equivalentes en Copilot Chat
2. Adaptar la configuración de Copilot Chat para soportar PLAN/AUDIT_PLAN/IMPLEMENT
3. Definir prompts y agents para Copilot equivalentes a `.claude/commands/`
4. Integrar con agentes de Copilot (Plan Architect, Feature Implementer, etc.)

---

## Diferencias Clave: Claude Code vs Copilot Chat

| Aspecto | Claude Code | Copilot Chat | Impacto |
|--------|----------|--|---|
| **Activación** | Slash commands (`/new-feature`) | Prompts o `@` mentions | Diferentes UX, mismo flujo |
| **Configuración** | `.claude/settings.json` | `.github/copilot-instructions.md` | Viven en lugares diferentes |
| **Comandos** | `.claude/commands/*.md` | `.github/prompts/*.prompt.md` | Contenido similar, sintaxis diferente |
| **Agentes** | Internal a Claude | Seleccionables (`@#symbol:agentName`) | Copilot permite elegir agente explícitamente |
| **Hooks** | PostToolUse en settings | Reglas en copilot-instructions.md | Menos automatización en Copilot |
| **Context** | CLAUDE.md carga siempre | copilot-instructions.md + `.github/instructions/` | Múltiples puntos de entrada |

---

## Mapeo: Slash Commands Claude → Copilot Chat

### `/new-feature` en Claude Code

**Claude Code**:
```
/new-feature
Objetivo: ...
```

**Equivalente Copilot Chat** (opción 1 — directo):
```
Voy a implementar una nueva funcionalidad.
Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.
Contexto:
- Objetivo: ...
- Módulo(s): ...
- API esperada: ...
```

**Equivalente Copilot Chat** (opción 2 — con prompt/agent):
```
@prompt /new-feature
Objetivo: ...
```
(Si `.github/prompts/new-feature.prompt.md` existe)

**Equivalente Copilot Chat** (opción 3 — con agent recomendado):
```
@#symbol:Feature Implementer

Necesito nueva funcionalidad: ...
Módulo(s): ...
```

### Matriz Completa

| Claude Code | Copilot Chat (directo) | Copilot Chat (con prompt) | Copilot Chat (con agent) |
|---|---|---|---|
| `/new-feature` | "Voy a implementar nueva funcionalidad..." | `@prompt /new-feature` | `@#symbol:Feature Implementer` (si soporta) |
| `/hotfix` | "Hay un bug crítico..." | `@prompt /hotfix` | `@#symbol:Hotfix Responder` |
| `/refactor` | "Voy a refactorizar sin cambios funcionales..." | `@prompt /refactor` | `@#symbol:Plan Architect` + confirmar scope |
| `/audit-code` | "Revisa este código por bugs, edge cases..." | `@prompt /audit-code` | `@#symbol:Code Auditor` |
| `/security-review` | "Auditoría de seguridad en este módulo..." | `@prompt /security-review` | `@#symbol:Security Reviewer` |
| `/tech-debt` | "Inventario de deuda técnica en..." | `@prompt /tech-debt` | `@#symbol:Plan Architect` (strategy context) |
| `/maturity-assessment` | "Evalúa madurez y readiness del repo..." | `@prompt /maturity-assessment` | `@#symbol:Maturity Assessment` |
| `/version-closure` | "Cierra la versión v0.6.7..." | `@prompt /version-closure` | `@#symbol:Version Closer` |

---

## Opción 1: Migración "Directa" (sin cambios en `.github/`)

**Ventaja**: Rápida, requiere cambios mínimos
**Desventaja**: Usuario debe recordar el flujo manualmente
**Esfuerzo**: < 1 hora (solo documentación)

### Implementación

1. Crear documento `docs/v0.6.7/COPILOT_CHAT_WORKFLOWS.md`:
   ```markdown
   # Flujos PLAN/AUDIT_PLAN para Copilot Chat

   ## /new-feature equivalente
   ```
   Escribe esto en Copilot Chat:
   ```
   Voy a implementar una nueva funcionalidad en util_bbdd.

   Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.

   Contexto:
   - Objetivo: [ej. exportación Markdown con Mermaid]
   - Módulo(s) o clase(s): [ej. src/util_bbdd/doc/render_markdown.py]
   - API pública esperada: [ej. parámetro opcional enable_mermaid]
   - Contrato de entrada: [ej. modelo de metadatos ya introspectado]
   - Contrato de salida: [ej. Markdown portable determinista]
   - Reglas de negocio: [ej. no inventar metadatos, Mermaid solo con datos reales]
   - Restricciones: [ej. sin dependencias nuevas]
   - Motores afectados: [ej. Markdown]
   - Archivos relevantes: [ej. sí]

   Primero: emite PLAN con rutas afectadas, componentes y riesgos.
   ```

2. Incluir matriz de entrada/salida esperada

3. Enlazar desde CLAUDE.md o nueva sección "Copilot Chat"

**Pros**: Cero cambios a `.github/`; usuario toma control de estructura
**Contras**: Requiere que usuario sepa el flujo; puede ser olvidadizo

---

## Opción 2: Prompts en `.github/prompts/` (Recomendado)

**Ventaja**: Flujo activado por @prompt mention es más natural para Copilot Chat
**Desventaja**: Requiere crear archivos paralelos a los de Claude Code
**Esfuerzo**: 2-3 horas

### Estructura Propuesta

Crear `.github/prompts/` espejo de `.claude/commands/`:

```
.github/prompts/
  new-feature.prompt.md       ← equivalente a .claude/commands/new-feature.md
  hotfix.prompt.md            ← equivalente a .claude/commands/hotfix.md
  refactor.prompt.md
  audit-code.prompt.md
  security-review.prompt.md
  tech-debt.prompt.md
  maturity-assessment.prompt.md
  version-closure.prompt.md
```

### Contenido de `.github/prompts/new-feature.prompt.md`

```markdown
---
name: new_feature
description: Implementar nueva funcionalidad con flujo PLAN→AUDIT_PLAN→IMPLEMENT
---

# Nueva Funcionalidad

Política: **prohibido refactorizar**.

Voy a guiarte por el flujo estructurado para agregar nueva funcionalidad.

## Paso 1: Inputs requeridos

Proporciona los siguientes datos (si alguno falta, pregunta para aclarar):

- **Objetivo**: Descripción breve de qué se va a implementar
- **Módulo(s) o clase(s)**: Ruta y componentes afectados (ej. `src/util_bbdd/doc/render_markdown.py`)
- **API pública esperada**: Parámetros nuevos, métodos nuevos, cambios de firma
- **Contrato de entrada**: Qué espera recibir (tipos, estructura)
- **Contrato de salida**: Qué produce y garantiza
- **Reglas de negocio**: Restricciones funcionales (ej. "no inventar metadatos", "determinismo")
- **Restricciones**: Límites técnicos (ej. "sin dependencias nuevas", "sync/async compatible")
- **Motores o formatos afectados**: BD motors o formatos de salida relevantes
- **¿Hay archivos relevantes existentes?**: (sí/no) Referencias a archivos relacionados

## Paso 2: Emito PLAN

Devuelvo:
- **objetivo** resumido en 1 línea
- **rutas afectadas** (ej. `src/...`, `tests/...`)
- **componentes implicados** (clases, funciones)
- **tipos necesarios** (dataclasses, Protocols, tipos nuevos)
- **riesgos** (funcionales, técnicos, seguridad)

## Paso 3: AUDIT_PLAN

Analizo:
- Riesgos funcionales (comportamiento incorrecto, incompletitud)
- Riesgos técnicos (SOLID, performance, tipado)
- Riesgos de seguridad (inputs no validados, SQL injection, credencials)
- Simplificaciones posibles (scope reduction de alcance)
- **Veredicto**: GO / NO_GO / GO_CONDICIONAL (con condiciones si aplica)

## Paso 4: IMPLEMENT

Por capas (Level 1 → 2 → 3):
- Cambios por archivo
- Código
- Explicación breve

## Paso 5: AUDIT_CODE

Revisión técnica:
- Bugs potenciales
- Edge cases
- Performance
- Seguridad
- Tipado
- Deuda técnica

## Paso 6: VERSION

Cierre:
- Commit message (formato: `feat: <descripción>`)
- Changelog
- Impacto en API pública
- Rollback
- Pruebas sugeridas

---

## Para empezar

Proporciona los inputs de la sección "Paso 1: Inputs requeridos".
```

### Integración con Copilot Chat

En `Settings > Copilot > Chat` (si soporta prompts):

```json
{
  "prompts": {
    "new-feature": {
      "file": ".github/prompts/new-feature.prompt.md",
      "description": "Nueva funcionalidad con PLAN→AUDIT_PLAN→IMPLEMENT"
    }
    // ... más prompts
  }
}
```

o vía `copilot-instructions.md`:

```markdown
# Prompts disponibles

Usa `@prompt /new-feature` para implementar nueva funcionalidad.
Usa `@prompt /hotfix` para correcciones.
Usa `@prompt /audit-code` para auditorías.

## Archivo de definición
- Los prompts están en `.github/prompts/*.prompt.md`
```

**Pros**: Clara integración Copilot Chat; reutiliza estructura
**Contras**: Duplicación con `.claude/commands/` (mantener sincronizados)

---

## Opción 3: Agentes de Copilot + Prompts Juntos (Óptimo)

**Ventaja**: Máxima integración (agent + prompt + instruction); experiencia unificada
**Desventaja**: Requiere trabajo previo de arquitectura de agentes
**Esfuerzo**: 4-5 horas (incluye refinamiento de agentes)

### Arquitectura Propuesta

```
.github/copilot-instructions.md
  └── Referencia a agentes: Plan Architect, Feature Implementer, Code Auditor, etc.

.github/prompts/
  └── new-feature.prompt.md: "Usa @#symbol:Plan Architect para PLAN/AUDIT_PLAN"
  └── hotfix.prompt.md: "Usa @#symbol:Hotfix Responder para fix minimalista"
  └── audit-code.prompt.md: "Usa @#symbol:Code Auditor para auditoría"

.claude/commands/
  └── new-feature.md: Slash command equivalente
  └── hotfix.md: Equivalente
  └── (etc.)
```

### Flujo de Usuario (Copilot Chat)

```
Usuario escribe en Copilot Chat:
  "Necesito nueva funcionalidad: exportación Markdown con Mermaid"

Copilot sugerencia:
  "@#symbol:Plan Architect para analizar, luego @#symbol:Feature Implementer"

Usuario pincha sugerencia → Plan Architect se activa:
  Emite PLAN automáticamente

Usuario confirma PLAN → Copilot sugiere Feature Implementer
  Emite AUDIT_PLAN → PLAN → IMPLEMENT

(Flujo similar al de Claude Code, pero a través de agents)
```

### Sincronización Entre Plataformas

Crear tabla de referencia en `.github/INTEGRATION_MAP.md`:

| Flujo | Claude Code | Copilot Chat |
|---|---|---|
| PLAN → AUDIT_PLAN | `/new-feature` | `@#symbol:Plan Architect` + `@prompt /new-feature` |
| IMPLEMENT | `/new-feature` step 4 | `@#symbol:Feature Implementer` |
| AUDIT_CODE | `/audit-code` | `@#symbol:Code Auditor` |
| Hotfix | `/hotfix` | `@#symbol:Hotfix Responder` + `@prompt /hotfix` |

---

## Recomendación Final: Ruta Híbrida

1. **Fase 1 (Inmediato)**: Opción 1 (Directa)
   - Crear `docs/v0.6.7/COPILOT_CHAT_WORKFLOWS.md`
   - Documentar entrada/salida esperada
   - **Esfuerzo**: 1h
   - **Beneficio**: Usuarios Copilot Chat saben qué escribir ahora

2. **Fase 2 (Próximas 2 semanas)**: Opción 2 (Prompts)
   - Crear `.github/prompts/*.prompt.md` paralelo a `.claude/commands/`
   - Integrar con `@prompt` mentions
   - **Esfuerzo**: 2-3h
   - **Beneficio**: UX más natural en Copilot Chat

3. **Fase 3 (Futuro)**: Opción 3 (Agentes)
   - Refinar agentes en `.github/copilot-instructions.md`
   - Crear automated workflow (plan → audit → implement)
   - **Esfuerzo**: 4-5h
   - **Beneficio**: Experiencia totalmente unificada

---

## Quick Start para Hoy

Si el usuario quiere usar Copilot Chat **ahora** con el flujo PLAN/AUDIT_PLAN:

### Paso 1: Copilot Settings

En VS Code, abre Copilot Chat y escribe (botón "Settings" en VS Code):

```
Activa las reglas de .github/copilot-instructions.md
```

### Paso 2: Flujo Manual (Opción 1)

Escribe en Copilot Chat:

```
Activa el flujo PLAN → AUDIT_PLAN para nueva funcionalidad siguiendo CLAUDE.md.

Nueva feature: [tu descripción]

Contexto:
- Objetivo: ...
- Módulo(s): ...
- API esperada: ...
```

### Paso 3: Leer Estas Guías

- Para Claude Code: Lee [CLAUDE.md](CLAUDE.md)
- Para Copilot Chat: Lee [docs/v0.6.7/COPILOT_CHAT_WORKFLOWS.md](docs/v0.6.7/COPILOT_CHAT_WORKFLOWS.md) (una vez creado)

---

## Pendientes de Configuración

### En `copilot-instructions.md`

Añadir sección:

```markdown
## Flujos estructurados (PLAN→AUDIT_PLAN→IMPLEMENT)

### Para Copilot Chat

Usa el patrón propuesto en [docs/v0.6.7/COPILOT_CHAT_WORKFLOWS.md](docs/v0.6.7/COPILOT_CHAT_WORKFLOWS.md).

Ejemplo para nueva funcionalidad:
```
[quoteblock con ejemplo de entrada]
```

### Para Claude Code

Usa slash commands en `.claude/commands/`:
- `/new-feature` para nueva funcionalidad
- `/hotfix` para bugs
- `/refactor` para refactors
- (etc.)

Más detalles en [CLAUDE.md](CLAUDE.md).
```

---

## Conclusión

**Recomendación para .github/copilot-instructions.md v0.6.7**:

1. **Ya hoy**: Referenciar [CLAUDE_COPILOT_MAPPING.md](../v0.6.7/CLAUDE_COPILOT_MAPPING.md) en sección "Flujos equivalentes"
2. **Semana 1**: Crear [COPILOT_CHAT_WORKFLOWS.md](../v0.6.7/COPILOT_CHAT_WORKFLOWS.md) con instrucciones directas
3. **Semana 2**: Considerar crear `.github/prompts/` paralelo a `.claude/commands/`
4. **Post-v0.6.7**: Evaluar agentes de Copilot para automatización completa

**Métrica de éxito**: 80% de usuarios Copilot Chat usan PLAN/AUDIT_PLAN en sus PRs
