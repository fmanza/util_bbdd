# TRACEABILITY

## Session metadata
- id: 2026-09-28-config-review
- fecha: 2026-09-28
- rama: develop
- skill: config_review + version_closure
- fase: ANÁLISIS + PLAN + AUDIT_PLAN (GO_CONDICIONAL → GO) + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```text
/config-review
Modo: repo · Foco: todo · Ficheros: todo · Fases: análisis
```
Decisiones del propietario: D1 ampliar tipos de commit (`perf`, `release`, `hotfix`, `security`);
D2 Version Closer con `edit` para `CHANGELOG.md` y `TRACEABILITY.md`; D3 archivar informes sueltos y
prompts de meta-auditoría (respuesta «si»: se asumió archivar); D4 registrar el flujo de constraints con
slash command propio. Después: «IMPLEMENT» y `/version-closure` «antes decidir si .claude/settings.json se
tiene que versionar» → versionarlo con solo hooks.

## Context supplied
- `.github/agents/config-reviewer.agent.md`, `.github/prompts/config_review.prompt.md`
- Inventario completo de configuración IA (≈16 300 LOC; 11 331 en el inventario del agente)
- `pyproject.toml`, `pytest.ini`, `.gitignore`, `mkdocs.yml`, `src/util_bbdd/` (verificación de rutas y APIs)

## AI output summary
- ANÁLISIS: 6 hallazgos Alta, 9 Media, 6 Baja; duplicación ~7 % (bloques parafraseados), ~40 referencias huérfanas.
- `445b298` contratos: `/version-closure` y su prompt con Directrices + sync; Version Closer `edit`; `applyTo` de
  introspection → `metadata/` y render → `doc/` (render-markdown fusionado); `.ai/` sin versión fija; hooks.
- `53a9454` DRY: 7 commands finos sobre prompts unificados; tabla única en CLAUDE.md; tipos de commit en SHARED;
  pool por defecto en ambos managers; mypy sin `--strict` y docstrings Google en instructions.
- `43e0ca5` documentación: `DOCUMENTATION_STANDARD.md` §3 canónico de 8 arquetipos; `docs.instructions.md`
  745 → 504 líneas; reglas Markdown de SHARED movidas; sin términos de otros proyectos.
- `3a1ea31` inventario: `/performance-audit-constraints`; prompts de agente a `.github/prompts/`; commands de
  rendimiento finos; retirados 12 ficheros (copia local en `.ai/doc_old/config-2026-09/`, no versionada);
  bootstrap, COMMAND_TEMPLATE, TESTING_GUIDE (estructura real de `tests/`), fences anidados.
- `a8488d8` `.claude/settings.json` versionado (solo hooks); fuera `settings.json.example`.
- Validación: comprobación de rutas/paridad de la configuración viva sin huérfanos ni fences abiertos;
  `pytest` 5288 passed / 199 skipped; tests de docs 26 passed. Sin cambios en `src/` ni `docs/`.
- `zensical build --strict` en worktree limpio: 3 incidencias en `73f3418` (antes de la sesión) y las mismas 3 en
  `a8488d8` → la sesión no añade ninguna. `mkdocs build --strict` sin avisos. En el working tree principal
  Zensical informa 38 por estado local no versionado (no reproducible en worktree limpio).
- VERSION: entrada en `CHANGELOG.md` § `[Unreleased]` (sin bump: no cambia el paquete publicado).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Commits | `445b298`, `53a9454`, `43e0ca5`, `3a1ea31`, `a8488d8` (develop, sin push) | completado |
| Command nuevo | `.claude/commands/performance-audit-constraints.md` | completado |
| Archivo local | `.ai/doc_old/config-2026-09/` (+ `README.md`) | no versionado |
| CHANGELOG | `CHANGELOG.md` § `[Unreleased]` | completado |

## Directrices para Futuras IAs
- **[config IA]**: el contrato de salida de cada flujo vive SOLO en `.github/prompts/<flujo>.prompt.md`; `.claude/commands/<flujo>.md` es un envoltorio fino (contexto a leer, reglas de ejecución de Claude, ejemplo de entrada). Plantilla: `.claude/COMMAND_TEMPLATE.md`. Para cambiar fases o secciones, edita el prompt, no el command.
- **[config IA]**: los arquetipos de documentación se definen solo en `.github/DOCUMENTATION_STANDARD.md` §3; `.github/instructions/docs.instructions.md` solo lleva reglas de edición por ruta. No vuelvas a copiar estructuras de arquetipo en otro fichero.
- **[config IA]**: `.github/agents/` contiene solo `*.agent.md`; los flujos operativos de agente (`*_agent.prompt.md`) van en `.github/prompts/`, que es donde los buscan `docs/` y los commands.
- **[config IA]**: los `applyTo` de `.github/instructions/` deben apuntar a rutas reales (`src/util_bbdd/metadata/**`, `src/util_bbdd/doc/**`); un glob a una carpeta inexistente desactiva la regla en silencio.
- **[config IA]**: `.claude/settings.json` se versiona y contiene solo hooks; los permisos de sesión van a `settings.local.json` (git-ignored). Se había ignorado en `7e592e5` porque acumulaba allowlists de sesión.
- **[repo]**: `.ai/doc_old/` y `doc_old/` están en `.gitignore` y no tienen ficheros versionados: «archivar» ahí equivale a retirar del repositorio conservando copia local e historial de git.
- **[config IA]**: `.github/README.md` tiene prioridad sobre el `README.md` raíz en la portada de GitHub; no lo recrees sin querer ese efecto.
- **[config IA]**: `pytest.ini` fija `testpaths = tests`; pasar `src` a `pytest --collect-only` recoge 0 tests.
- **[herramientas]**: la verificación de huérfanos debe resolver rutas relativas al fichero y probar los prefijos `src/util_bbdd/`, `docs/` y `.github/`; los ejemplos «malo/incorrecto» y las secciones opcionales hipotéticas dan falsos positivos. Script usado: `verify.py` de la sesión (scratchpad, no versionado); candidato a `scripts/check_ai_config.py` (NUEVO, no existe).
- **[config IA]**: Version Closer solo puede editar `CHANGELOG.md` y el `TRACEABILITY.md` de la sesión, así que no puede registrar la sesión en `.ai/sessions/INDEX.md` ni en `SESSIONS_DIGEST.md`; decidir si se amplía su lista de ficheros.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Registrar esta sesión en `.ai/sessions/INDEX.md` y `SESSIONS_DIGEST.md` (fuera del permiso de Version Closer; fila propuesta en el cierre).
- `README.md` raíz: 13 enlaces rotos a documentación antigua (Documentation Reviewer).
- `SHARED_INSTRUCTIONS.md` § «Convención de nombres en `docs/`» exige minúsculas en todo `docs/`, pero existen `INSTALLATION.md`, `ROADMAP.md` y `CONSTRAINTS_*.md`.
- `docs/PERFORMANCE_AUDIT_CONSTRAINTS_GUIDE.md` y `docs/CONSTRAINTS_*` no están en el `nav` de `mkdocs.yml`.
- `zensical build --strict` falla (previo a la sesión): anclas `#reference`, `#agent`, `#guide` inexistentes en `docs/CONSTRAINTS_QUICK_REFERENCE.md:12-14`.
- `.ai/sessions/INDEX.md:227` (sesión `2026-09-27d-export-safety`) enlaza al `TRACEABILITY.md` de `2026-09-27c`.
- Push de `develop` pendiente de decisión del usuario.
