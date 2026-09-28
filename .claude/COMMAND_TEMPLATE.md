# COMMAND_TEMPLATE.md

Plantilla para crear o auditar un slash command de Claude Code en `.claude/commands/`.

## Principio: envoltorio fino sobre un prompt gemelo

Un command **no define el contrato de salida**: lo define su prompt gemelo en
`.github/prompts/<flujo>.prompt.md`, que también usan Copilot, Gemini y Codex. El command solo fija la
invocación en Claude Code y remite al agente y al prompt. Así hay una sola fuente por flujo y los
commands no divergen de los prompts.

| Vive en el command (`.claude/commands/<x>.md`) | Vive en el prompt (`.github/prompts/<x>.prompt.md`) |
|---|---|
| Título y propósito (1-2 líneas) | Inputs requeridos |
| «Contexto obligatorio»: prompt, agentes y guías a leer, en orden | Fases y secciones de salida, en orden |
| «Reglas de ejecución» propias de Claude Code (validación, parada tras AUDIT_PLAN, entregables) | Veredicto y sus valores |
| Ejemplo de entrada tal como se escribe tras `/x` | Reglas del flujo (política de cambios, evidencias, tipo de commit) |

## Estructura del command

````markdown
# /<nombre-del-command>

<Propósito en 1-2 líneas. Política clave si la hay, p.ej. «prohibido refactorizar».>

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/<flujo>.prompt.md` — inputs, contrato de salida y reglas
2. `.github/agents/<agente>.agent.md` — rol y restricciones

## Reglas de ejecución

- **⚠️ VALIDACIÓN**: <qué hacer si falta un input: DETENTE o supuesto explícito>.
- <Parada tras AUDIT_PLAN, entregables, commit… solo si aplica>.

## Ejemplo de entrada

```text
/<nombre-del-command>

<Campo>: <valor real del repositorio>
```
````

## Checklist de command bien formado

- [ ] Existe el prompt gemelo `.github/prompts/<flujo>.prompt.md` con inputs, salida y veredicto
- [ ] El command no repite las secciones de salida del prompt
- [ ] Rutas, clases y scripts del ejemplo existen en el repositorio (o se marcan `(nuevo)`)
- [ ] Sin slash commands inexistentes
- [ ] Bloques de código cerrados (fence exterior de 4 backticks si anida otro bloque)
- [ ] Registrado en la tabla de `CLAUDE.md` § «Slash commands de Claude Code» y en `.github/AGENTS.md`

## Crear un command nuevo

1. Escribe o actualiza el prompt gemelo (contrato completo).
2. Crea el command con la estructura de arriba.
3. Regístralo en `CLAUDE.md` y `.github/AGENTS.md`; si usa un agente nuevo, créalo en `.github/agents/`.
4. Revisa con `/config-review` (foco: paridad comandos/prompts/agentes).

---

*Actualizado: 2026-09-28 — patrón de envoltorio fino (config-review); sustituye la plantilla de 10 secciones de v0.6.7.*
