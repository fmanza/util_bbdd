# Configuración de Claude Code — util_bbdd

## 1. Descripción General

Claude Code es el asistente IA principal de desarrollo en `util_bbdd`. Se configura mediante
`CLAUDE.md` (especialización) y `.github/SHARED_INSTRUCTIONS.md` (fuente canónica compartida),
con hooks `PostToolUse` que ejecutan automáticamente linting, tipado y tests tras cada edición.

**Propósito**: Automatizar los flujos de nueva funcionalidad, hotfix, refactor, auditoría de código
y cierre de versión mediante slash commands que orquestan agentes especializados en `.github/agents/`.

**Plataformas activas en el proyecto**: Claude Code · GitHub Copilot Chat · Gemini Code Assist ·
Cursor · Codex (OpenAI). Todas comparten `.github/SHARED_INSTRUCTIONS.md` como fuente canónica.

## 2. Ficheros de Configuración

| Fichero | Propósito | Editar cuando… |
|---|---|---|
| `CLAUDE.md` | Especialización Claude Code: slash commands, flujos estructurados, integración Copilot | Cambien los comandos disponibles o el flujo de trabajo |
| `.github/SHARED_INSTRUCTIONS.md` | Fuente canónica: arquitectura, calidad, Conventional Commits, tooling | Cambien las reglas que aplican a todas las plataformas IA |
| `.claude/settings.json` | Hooks PostToolUse: ruff → mypy → pytest tras Edit/Write | Se añadan o eliminen pasos de validación automática |
| `.claude/settings.local.json` | Personalización local (no versionado) | Configuración específica del entorno del desarrollador |
| `.claude/commands/` | Slash commands personalizados adicionales | Se añadan nuevos flujos estructurados |

## 3. Hooks y Automatización

### PostToolUse (activados tras cada `Edit` o `Write`)

Orden de ejecución configurado en `.claude/settings.json`:

| Paso | Comando | Propósito |
|---|---|---|
| 1 | `python -m ruff check src tests --quiet` | Linting — detecta problemas de estilo y errores estáticos |
| 2 | `python -m mypy src --no-error-summary` | Type-checking strict — verifica anotaciones de tipo |
| 3 | `python -m pytest --collect-only -q src` | Validación de sintaxis de tests — asegura que los tests son importables |

Si cualquier paso falla, Claude Code itera automáticamente correcciones antes de continuar.

### MkDocs build

Ejecutar manualmente antes de publicar documentación:

```bash
python -m mkdocs build --strict   # Build completo con warnings como errores
python -m mkdocs serve            # Preview local en http://127.0.0.1:8000
```

## 4. Slash Commands Disponibles

| Comando | Propósito | Fases |
|---|---|---|
| `/new-feature` | Nueva funcionalidad con flujo completo | PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION |
| `/hotfix` | Bug P1/P2 mínimo, sin refactorizar | RCA → FIX → AUDIT_CODE → VERSION |
| `/refactor` | Cambio estructural sin impacto funcional | PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE |
| `/audit-code` | Auditoría técnica independiente (solo lectura) | Scope → Findings → Verdict |
| `/security-review` | Auditoría de seguridad (solo lectura) | Findings by severity → Remediation |
| `/tech-debt` | Deuda técnica priorizada (solo lectura) | Scope → Findings → Plan |
| `/maturity-assessment` | Evaluación de madurez del repositorio (solo lectura) | Scope → Findings → Verdict |
| `/version-closure` | Cierre de versión: release notes, changelog, handoff | Resumen → Validación → Handoff |

Cada comando lee `CLAUDE.md` + `SHARED_INSTRUCTIONS.md` como contexto antes de actuar.

## 5. Restricciones y Principios Innegociables

| Restricción | Detalle |
|---|---|
| Sin API keys | Prohibido incrustar credenciales IA en código, prompts o workflows |
| Sin componentes programáticos IA | El código Python es tooling determinista; nunca invoca servicios IA |
| Ejecución en chat | La generación documental ocurre en el chat, no en componentes programáticos |
| Tooling determinista | `ruff`, `mypy`, `pytest` — sin red, sin credenciales, sin estado global mutable |
| Conventional Commits | `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` obligatorio en commits |
