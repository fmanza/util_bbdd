# TRACEABILITY

## Session metadata
- id: 2026-06-05-bootstrap-ai-config
- fecha: 2026-06-05
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Recomendar el mejor método para copiar las instrucciones IA completas de este proyecto a otro
proyecto VS Code (posible otro lenguaje/arquitectura), con plataformas Gemini/Copilot/Claude
(+Cursor), proponiendo método y dirección de la llamada y rutas; contexto obligatorio vs. opcional.
Primero PLAN y AUDIT_PLAN; luego IMPLEMENT, commit y actualización documental.

## Context supplied
- `.github/SHARED_INSTRUCTIONS.md`, `.github/copilot-instructions.md`, `CLAUDE.md`, `GEMINI.md`, `.cursorrules`
- `.github/AGENTS.md`, `.github/instructions/sync.instructions.md`, `.github/agents/plan-architect.agent.md`
- `.github/prompts/config_review.prompt.md`, `.claude/commands/new-feature.md`
- Inventario completo de `.github/{agents,prompts,instructions}/`, `.claude/`, `.ai/`

## AI output summary
- Inventario y clasificación de activos IA en 4 capas: A (verbatim), B (copiar+reescribir), C (regenerar), D (excluir).
- Emitido PLAN + AUDIT_PLAN con veredicto GO_CONDICIONAL y 4 condiciones; usuario respondió las 4.
- Decisión de método: modelo **PULL** (invocar desde el destino con el origen como plantilla de solo lectura).
- Recomendación: **prompt nuevo** `bootstrap_ai_config` + reutilizar agente `config-reviewer` como auditor.
- IMPLEMENT: creado `.github/prompts/bootstrap_ai_config.prompt.md` (4 plataformas, capas, método, contexto obligatorio/opcional, adaptación de hooks).
- Documentación sincronizada: CLAUDE.md (sección + tabla), copilot-instructions.md (sección), AGENTS.md (sección + contador 16→17), GEMINI.md (puntero), .cursorrules (cabecera + puntero), SHARED_INSTRUCTIONS.md (2 filas de gobernanza). Timestamps → 2026-06-05.
- AUDIT_CODE: verificado DRY, rutas relativas, cobertura de las 4 plataformas, condición nº3 reflejada en el prompt.
- VERSION: commit `cd22520` en develop (7 ficheros, +335/−5). Excluido `.claude/settings.json` (allowlist de sesión, ajeno).
- Registro de sesión: commit `1bf511b` (REQUEST + CONTEXT_SNAPSHOT + TRACEABILITY).
- Revisión documental (agente `documentation-reviewer`) sobre los artefactos de la sesión: NEAR_READY; 1 hallazgo Nivel 1 + 2 Nivel 2 + 1 Nivel 3.
- Correcciones aplicadas: (N1) directiva falsa sobre `.ai/standards.md` corregida —el fichero SÍ existe y está versionado—; (N2) alcance de Codex declarado fuera de alcance en el prompt; (N2) título y gobernanza de `SHARED_INSTRUCTIONS.md` reconciliados con Gemini y Cursor + fila `GEMINI.md`; (N3) conteo de agentes 11→12 en `AGENTS.md`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Prompt bootstrap | `.github/prompts/bootstrap_ai_config.prompt.md` | creado |
| Doc Claude | `CLAUDE.md` | actualizado |
| Doc Gemini | `GEMINI.md` | actualizado |
| Doc Copilot | `.github/copilot-instructions.md` | actualizado |
| Doc Cursor | `.cursorrules` | actualizado |
| Registro agentes | `.github/AGENTS.md` | actualizado |
| Gobernanza | `.github/SHARED_INSTRUCTIONS.md` | actualizado |
| Sesión | `.ai/sessions/2026-06-05-bootstrap-ai-config/` | creada |

## Directrices para Futuras IAs
- **[bootstrap cross-project]**: `.github/prompts/bootstrap_ai_config.prompt.md` es el punto único para trasladar la config IA a otro proyecto; el auditor del resultado es el agente `config-reviewer`.
- **[método]**: el bootstrap usa modelo PULL — se invoca DESDE el proyecto destino con el origen como plantilla de solo lectura; lanzarlo desde el origen arrastra supuestos de Python/util_bbdd.
- **[clasificación]**: todo activo IA se clasifica en capas A (verbatim/revisar comandos) · B (copiar+reescribir dominio) · C (regenerar analizando el destino) · D (excluir: sesiones, changelog, caches, settings.local.json).
- **[capa A no es verbatim puro]**: agentes/prompts/commands llevan comandos embebidos del origen (`pytest`, `mkdocs build`, rutas `src/`) que deben sustituirse por equivalentes del destino.
- **[plataformas]**: el repo soporta 4 plataformas IA — Claude (`CLAUDE.md`), Gemini (`GEMINI.md`), Copilot (`.github/copilot-instructions.md`), Cursor (`.cursorrules`); todas referencian `SHARED_INSTRUCTIONS.md` como canónico.
- **[parámetros]**: lenguaje y arquitectura del destino son parámetros de entrada del prompt, no constantes; el prompt detiene la emisión de PLAN si falta cualquier campo de contexto.
- **[contexto .ai]**: `.ai/standards.md` existe y está versionado; es referenciado por `plan-architect`, los demás agentes y el prompt de bootstrap como fuente de convenciones de calidad. En el destino del bootstrap es un objetivo a regenerar (capa C).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit `cd22520` no empujado (push / PR a main pendiente de decisión del usuario).
- `.claude/settings.json` con allowlist de sesión sin commitear (descartar o commitear aparte).
