# Directorio `.claude/`

Configuración y comandos especializados para **Claude Code**. Las reglas comunes viven en
[`.github/SHARED_INSTRUCTIONS.md`](../.github/SHARED_INSTRUCTIONS.md); la especialización de Claude,
en [`CLAUDE.md`](../CLAUDE.md).

---

## Archivos

### `settings.json.example` → `settings.json`

`settings.json.example` es la plantilla **versionada** de hooks; `settings.json` está en `.gitignore`,
así que en cada clon hay que copiarla:

```bash
cp .claude/settings.json.example .claude/settings.json
```

Si cambias los hooks, edita la plantilla y vuelve a copiarla. Hooks `PostToolUse` (tras cada
`Edit`/`Write`), informativos (su salida se pasa por `head`/`tail`, así que no bloquean):

- `python -m ruff check src tests --quiet` — linting
- `python -m mypy src --no-error-summary` — type-checking rápido
- `python -m pytest --collect-only -q` — recogida de tests (`testpaths` de `pytest.ini`), sin ejecución

No sustituyen a la validación de IMPLEMENT: ejecuta los comandos de
`SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo» antes de cerrar.

### `settings.local.json` (no versionado)

Personalización local adicional, ignorada por git. Claude Code **suma** sus hooks a los de
`settings.json`: no copies aquí la plantilla (los hooks correrían dos veces) ni esperes que un hook
local sustituya a uno de `settings.json`. Úsalo para permisos o hooks **adicionales**.

Para desactivar temporalmente todos los hooks en tu máquina: `"disableAllHooks": true` en
`settings.local.json`.

### `commands/`

Slash commands de Claude Code. La tabla canónica (comando, propósito, entrada, salida) está en
[`CLAUDE.md`](../CLAUDE.md) § «Slash commands de Claude Code»; el registro multiplataforma, en
[`.github/AGENTS.md`](../.github/AGENTS.md). Cada command es un envoltorio fino: inputs + agente +
prompt de `.github/prompts/` (el contrato de salida vive en el prompt).

Al añadir o cambiar un command: actualiza la tabla de `CLAUDE.md`, `.github/AGENTS.md` y el prompt gemelo.

### `performance-audit-guide.md`

Guía de la auditoría de rendimiento de `dump` (`/performance-audit-dump`): cuellos CB1–CB8,
banco `scripts/bench_dump.py` e interpretación de resultados.

### `COMMAND_TEMPLATE.md`, `EDGE_CASES.md`, `TESTING_GUIDE.md`

Plantilla para commands nuevos, casos límite conocidos y guía de tests.

---

## FAQ

### ¿Los hooks necesitan el entorno virtual activo?

Sí. Invocan `python` por nombre (resuelto vía `PATH`): abre Claude Code desde una terminal con el venv
del proyecto activado (`.\venv\Scripts\Activate.ps1` en Windows, `source venv/bin/activate` en
Linux/Mac). Instala las herramientas con `pip install -e ".[dev]"` (mismas versiones que CI).

### ¿Dónde reporto problemas con hooks?

Crea un issue con el comando que ejecutaste, la línea de error del hook, el sistema operativo y la
versión de Python.

---

## Referencias

- [`CLAUDE.md`](../CLAUDE.md) — especialización para Claude Code
- [`docs/guides/claude_code_guide.md`](../docs/guides/claude_code_guide.md) y
  [`docs/guides/github_copilot_guide.md`](../docs/guides/github_copilot_guide.md) — uso de cada plataforma
- [`.github/AGENTS.md`](../.github/AGENTS.md) — registro de agentes, prompts y slash commands
- Gobernanza entre plataformas: `SHARED_INSTRUCTIONS.md` § «Gobernanza de plataformas IA»
