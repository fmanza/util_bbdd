# Instrucciones para Codex — util_bbdd

Entry point de Codex (OpenAI). Solo añade especialización; las reglas comunes viven en el canónico.

## ⚠️ Contexto previo obligatorio

Lee **primero**, en este orden:

1. **`.github/SHARED_INSTRUCTIONS.md`** — Fuente canónica: arquitectura de util_bbdd, SOLID, calidad,
   comandos de desarrollo, documentación, flujo de trabajo, Conventional Commits.
2. **`.github/AGENTS.md`** — Registro de agentes (roles), prompts y flujos.
3. **Este fichero** — Especialización para Codex únicamente.

## Flujo de trabajo

Para cambios no triviales: `PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION`.
Codex no tiene slash commands ni agentes con nombre: aplica el prompt del flujo por lenguaje natural
(`Lee y aplica .github/prompts/new_feature.prompt.md …`); los prompts están en `.github/prompts/`.

## Reglas específicas para Codex

- Verifica en `src/util_bbdd/` que módulos, clases y rutas existen antes de proponerlos.
- Si una instrucción contradice `pyproject.toml` o el código real, prioriza el código y explicita el supuesto.
- Antes de dar por terminado IMPLEMENT, ejecuta los comandos de `SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo».
- Documentación: `.github/DOCUMENTATION_STANDARD.md` (arquetipos y flujo por fases).
- Guía de uso de Codex en este repo: `docs/guides/codex_guide.md`.

---

*Actualizado: 2026-09-25*
