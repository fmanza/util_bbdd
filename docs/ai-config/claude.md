# Configuración de Claude Code — util_bbdd

## 1. Descripción General

Claude Code es el asistente IA principal de desarrollo en `util_bbdd`. Se configura mediante
`CLAUDE.md` (especialización) y `.github/SHARED_INSTRUCTIONS.md` (fuente canónica compartida),
con hooks `PostToolUse` informativos que ejecutan linting, tipado y la recogida de tests tras cada edición.

**Propósito**: Automatizar los flujos de nueva funcionalidad, hotfix, refactor, auditoría de código
y cierre de versión mediante slash commands que orquestan agentes especializados en `.github/agents/`.

**Plataformas activas en el proyecto**: Claude Code · GitHub Copilot Chat · Gemini Code Assist ·
Cursor · Codex (OpenAI). Todas comparten `.github/SHARED_INSTRUCTIONS.md` como fuente canónica.

## 2. Ficheros de Configuración

| Fichero | Propósito | Editar cuando… |
|---|---|---|
| `CLAUDE.md` | Especialización Claude Code: slash commands, flujos estructurados, integración Copilot | Cambien los comandos disponibles o el flujo de trabajo |
| `.github/SHARED_INSTRUCTIONS.md` | Fuente canónica: arquitectura, calidad, Conventional Commits, tooling | Cambien las reglas que aplican a todas las plataformas IA |
| `.claude/settings.json` | Solo los hooks compartidos (versionado): ruff → mypy → recogida de pytest tras Edit/Write | Se añadan o eliminen pasos de validación automática |
| `.claude/settings.local.json` | Permisos («no volver a preguntar») y ajustes personales (no versionado) | Configuración específica del entorno del desarrollador |
| `.claude/commands/` | Slash commands personalizados adicionales | Se añadan nuevos flujos estructurados |

## 3. Hooks y Automatización

### PostToolUse (activados tras cada `Edit` o `Write`)

Orden de ejecución configurado en `.claude/settings.json`:

| Paso | Comando | Propósito |
|---|---|---|
| 1 | `python -m ruff check src tests --quiet` | Linting — detecta problemas de estilo y errores estáticos |
| 2 | `python -m mypy src --no-error-summary` | Type-checking rápido (el completo, con `tests/unit/test_protocol_conformance.py`, está en los comandos de desarrollo) |
| 3 | `python -m pytest --collect-only -q` | Recogida de tests (`testpaths` de `pytest.ini`), sin ejecutarlos |

Los hooks son **informativos, no bloquean**: no aplican formato ni ejecutan la suite. Antes de cerrar una
implementación hay que ejecutar `ruff format`, el `mypy` completo y `pytest` (ver `.github/SHARED_INSTRUCTIONS.md`
§ «Comandos de desarrollo»).

### Build de la documentación

Ejecutar manualmente antes de publicar documentación (Zensical es el generador del CI; MkDocs, equivalente):

```bash
zensical build --strict   # o: python -m mkdocs build --strict
zensical serve            # preview local (o: python -m mkdocs serve)
```

## 4. Slash Commands Disponibles

Hay 15 comandos en `.claude/commands/`: `/new-feature`, `/hotfix`, `/refactor`, `/audit-code`, `/security-review`,
`/tech-debt`, `/maturity-assessment`, `/performance-audit-bulk`, `/performance-audit-dump`,
`/performance-audit-constraints`, `/metadata-centralization`, `/documentation-architecture-audit`, `/doc-generator`,
`/config-review` y
`/version-closure`. Cada uno es un envoltorio fino de su prompt en `.github/prompts/`, que es el contrato de salida
(fases, secciones y veredicto). La tabla con propósito, fases y veredicto de cada comando está en `CLAUDE.md` (fuente
única; no se copia aquí para que no diverja).

## 5. Restricciones y Principios Innegociables

| Restricción | Detalle |
|---|---|
| Sin API keys | Prohibido incrustar credenciales IA en código, prompts o workflows |
| Sin componentes programáticos IA | El código Python es tooling determinista; nunca invoca servicios IA |
| Ejecución en chat | La generación documental ocurre en el chat, no en componentes programáticos |
| Tooling determinista | `ruff`, `mypy`, `pytest` — sin red, sin credenciales, sin estado global mutable |
| Conventional Commits | Obligatorios; tipos (`feat`, `fix`, `hotfix`, `security`, `perf`, `refactor`, `test`, `docs`, `chore`, `release`) en `SHARED_INSTRUCTIONS.md` § «Formato de commits» |
