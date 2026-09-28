# Instrucciones para Claude Code — util_bbdd

Este fichero proporciona especialización a Claude Code cuando trabaja con util_bbdd:
slash commands, hooks de desarrollo y configuración integrada.

---

## ⚠️ Contexto previo obligatorio

- **`.github/SHARED_INSTRUCTIONS.md`** — Fuente canónica: arquitectura de util_bbdd, SOLID, calidad,
  comandos, documentación, flujo de trabajo, Conventional Commits. **Esta es la base** y se importa
  automáticamente:

@.github/SHARED_INSTRUCTIONS.md

- **Este fichero** — Especialización para Claude Code únicamente.

---

## Slash commands de Claude Code

Cada command es un envoltorio fino: fija los inputs y remite a su agente y a su prompt de
`.github/prompts/`, que es el **contrato de salida** (fases, secciones y veredicto). Si la tabla y un
prompt discrepan, manda el prompt.

| Comando | Propósito | Prompt (contrato) | Salida | Veredicto |
|---|---|---|---|---|
| [`/new-feature`](./.claude/commands/new-feature.md) | Nueva funcionalidad | `new_feature` | PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION | `GO \| GO_CONDICIONAL \| NO_GO` |
| [`/hotfix`](./.claude/commands/hotfix.md) | Bug P1/P2, fix mínimo | `hotfix` | PLAN → AUDIT_PLAN → IMPLEMENT (RCA + fix) → AUDIT_CODE → VERSION | — |
| [`/refactor`](./.claude/commands/refactor.md) | Refactor sin cambios funcionales | `refactor` | PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION | `GO \| GO_CONDICIONAL \| NO_GO` |
| [`/audit-code`](./.claude/commands/audit-code.md) | Auditoría técnica (solo lectura) | `audit_code` | PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION | `APROBADO \| APROBADO CON CONDICIONES \| RECHAZADO` |
| [`/security-review`](./.claude/commands/security-review.md) | Auditoría de seguridad (solo lectura) | `security_review` | PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION | críticos bloquean el merge |
| [`/tech-debt`](./.claude/commands/tech-debt.md) | Deuda técnica priorizada | `tech_debt` | PLAN → AUDIT_PLAN → AUDIT_CODE (→ VERSION si se autoriza IMPLEMENT) | `LIMPIO \| DEUDA_MENOR \| DEUDA_SIGNIFICATIVA \| CRÍTICO` |
| [`/maturity-assessment`](./.claude/commands/maturity-assessment.md) | Madurez del repo (solo lectura) | `maturity_assessment` | PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION | `PRODUCTION_READY \| NEAR_READY \| BLOCKED` |
| [`/performance-audit-bulk`](./.claude/commands/performance-audit-bulk.md) | Rendimiento de `bulk/` (INSERT/UPDATE/DELETE) | `performance_audit_bulk` | PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION (impacto %) | `CRÍTICO \| SIGNIFICATIVO \| MODERADO \| LIMPIO` |
| [`/performance-audit-dump`](./.claude/commands/performance-audit-dump.md) | Rendimiento de `dump/` (volcado) | `performance_audit_dump` + `performance_audit_dump_agent` | 5 fases → informe + roadmap (+ validación) | — |
| [`/config-review`](./.claude/commands/config-review.md) | Configuración IA (DRY, huérfanos, bootstrap) | `config_review` | ANÁLISIS → PLAN → AUDIT_PLAN (→ IMPLEMENT → AUDIT_CODE → VERSION tras aprobación) | `GO \| GO_CONDICIONAL \| NO_GO` |
| [`/version-closure`](./.claude/commands/version-closure.md) | Cierre de versión o sesión | `version_closure` | Commit → Changelog → API → Migraciones → Compatibilidad → Rollback → Checklist → Directrices | — |

Invocación: escribe el command y, debajo, los inputs de su prompt. Ejemplo:

```text
/performance-audit-bulk

Objetivo: paralelización + batching
Baseline: no (ejecutar benchmark primero)
Dialects: PostgreSQL + MySQL + SQL Server
Volumen: 100K registros
Timeline: ASAP
Validación: sí
```

---

## Trasladar esta configuración IA a otro proyecto (bootstrap)

Usa [`.github/prompts/bootstrap_ai_config.prompt.md`](./.github/prompts/bootstrap_ai_config.prompt.md)
(modelo **PULL**: se invoca desde el proyecto destino; capas A/B/C/D, contexto mínimo y mapeo por
plataforma están en el propio prompt). La auditoría posterior la hace `/config-review` en modo `bootstrap`.

```text
# Abre el PROYECTO DESTINO en Claude Code y escribe:

Lee y aplica .github/prompts/bootstrap_ai_config.prompt.md
Origen (solo lectura): c:\Desarrollo\python\libs\util_bbdd
Destino: <raíz de este proyecto>
Lenguaje/arquitectura destino: <p.ej. TypeScript + NestJS hexagonal>
Plataformas IA activas: Claude Code, Gemini, Copilot, Cursor, Codex
Fase: PLAN y AUDIT_PLAN únicamente.
```

---

## Configuración: Hooks y PostToolUse

Lee [`.claude/README.md`](./.claude/README.md) para detalles completos sobre hooks:

```
.claude/
  settings.json.example   ← Plantilla VERSIONADA de hooks PostToolUse: ruff, mypy, pytest (recogida)
  settings.json           ← Copia local de la plantilla (git-ignored)
  settings.local.json     ← Personalización local adicional (git-ignored)
  commands/               ← Slash commands personalizados
  EDGE_CASES.md           ← Casos límite conocidos en el proyecto
  TESTING_GUIDE.md        ← Guía de testing con PostToolUse
```

**Hooks de la plantilla** (tras cada `Edit`/`Write`; informativos, no bloquean):

1. `ruff check src tests` — linting
2. `mypy src` — type-checking rápido (el completo está en «Comandos de desarrollo»)
3. `pytest --collect-only -q` — recogida de tests (`testpaths` de `pytest.ini`), sin ejecución

Los hooks **no** aplican formato ni ejecutan la suite: antes de cerrar IMPLEMENT ejecuta tú
`ruff format`, el `mypy` completo y `pytest` con los comandos de `.github/SHARED_INSTRUCTIONS.md`
§ «Comandos de desarrollo», e itera si fallan.

**Instalación en un clon nuevo** (`settings.json` no se versiona):

```bash
cp .claude/settings.json.example .claude/settings.json
```

Si cambias los hooks, edita la plantilla `settings.json.example` y vuelve a copiarla. Los hooks de
`settings.local.json` se **suman** a los de `settings.json`: no copies la plantilla en ambos
(los hooks correrían dos veces).

---

## Integración con Copilot Chat

| Cambio en Claude Code | Auditoría en Copilot Chat | Propósito |
|---|---|---|
| `/new-feature` + IMPLEMENT (cambios acotados) | Code Auditor (agente) | Verificación independiente |
| `/new-feature` + documentación en `docs/` | Documentation Reviewer (agente) | Validar ejemplos y coherencia |
| Cambios en `.github/SHARED_INSTRUCTIONS.md` | Config Reviewer (agente; `/config-review` en Claude Code) | Validar DRY y consistencia entre plataformas |

Claude Code escribe cambios y ejecuta tests localmente; Copilot Chat revisa sin ejecutar. Si hay
discrepancias, `SHARED_INSTRUCTIONS.md` es la fuente de verdad.

| Aspecto | Claude Code | Copilot Chat |
|---|---|---|
| **Invocación** | Slash commands (`/new-feature`, etc.) | Agentes con nombres + descripción |
| **Ejecución de tests** | Hooks PostToolUse + ejecución explícita | Manual (run_task, run_in_terminal) |
| **Contexto inicial** | `CLAUDE.md` + SHARED importado | `copilot-instructions.md` |
| **Mejor para** | Cambios estructurados, flujos completos | Consultas rápidas, auditorías independientes |
| **Documentación** | `.claude/` (settings.json, TESTING_GUIDE.md) | `.github/copilot-instructions.md` |

---

## Documentación con Claude Code

Punto único de entrada: agente **Documentation Generator** ([`.github/agents/documentation-generator.agent.md`](./.github/agents/documentation-generator.agent.md)),
invocado por lenguaje natural (no tiene slash command). Arquetipos, secciones fijas y flujo por fases:
[`.github/DOCUMENTATION_STANDARD.md`](./.github/DOCUMENTATION_STANDARD.md) §3 y §5. Reglas comunes
(Zensical, Mermaid, no inventar, sin APIs de IA externas, validación de Markdown):
`SHARED_INSTRUCTIONS.md` § «Documentación obligatoria».

```markdown
Usa Documentation Generator sobre [ruta_del_módulo]: documentación funcional y técnica.
Aplica .github/prompts/functional_doc.prompt.md y .github/prompts/technical_doc.prompt.md.
Guarda en docs/functional/[nombre].md y docs/api/[nombre].md y actualiza mkdocs.yml.
Opcional: --verify-build (zensical build --strict + inspección de site/), --verify-tools.
```

Para auditar sin editar: agente **Documentation Reviewer** con `.github/prompts/documentation_review.prompt.md`.

---

## Checklist de sincronización

Sigue `SHARED_INSTRUCTIONS.md` § «Gobernanza de plataformas IA». Específico de este fichero:

- [ ] Si cambias slash commands, actualiza la tabla de comandos de este fichero y `.github/AGENTS.md`

---

*Actualizado: 2026-09-25*
