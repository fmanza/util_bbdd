# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.github/SHARED_INSTRUCTIONS.md` — fuente canónica (rol, arquitectura, calidad, gobernanza)
- `.github/copilot-instructions.md` — entry point Copilot
- `CLAUDE.md` — entry point Claude Code
- `GEMINI.md` — entry point Gemini
- `.cursorrules` — entry point Cursor
- `.github/AGENTS.md` — registro de agentes y prompts
- `.github/instructions/sync.instructions.md` — checklist de sincronización VERSION
- `.github/agents/plan-architect.agent.md` — formato de PLAN/AUDIT_PLAN
- `.github/prompts/config_review.prompt.md`, `.claude/commands/new-feature.md` — convención de formato de prompts/commands
- Inventario de activos IA: `.github/agents/` (12), `.github/prompts/` (16), `.github/instructions/` (8), `.claude/commands/` (8), `.ai/` (contexto + sesiones)

## Estado actual observado
- Working tree limpio al inicio (rama develop).
- No se ejecutaron tests/lint/mypy: el cambio es solo de configuración IA y documentación (sin código fuente).

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno al inicio
- Último commit previo: 920bbeb (docs: documentar Zensical)

## Clasificación metodológica
- Tipo principal: new_feature (activo IA reutilizable nuevo + documentación)
- Estado real de alcance: acotado
- Consecuencia: ejecutar PLAN → AUDIT_PLAN → IMPLEMENT → VERSION sin tocar `src/`

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes (si aplica): ninguna (las 4 condiciones del AUDIT_PLAN fueron respondidas por el usuario)
