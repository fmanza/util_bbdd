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

Usa estos comandos para activar flujos estructurados con automatización integrada:

| Comando | Propósito | Entrada | Salida |
|---|---|---|---|
| `/new-feature` | Nueva funcionalidad | Descripción + módulos | PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION |
| `/hotfix` | Bug P1/P2 mínimo | Descripción + impacto | RCA → FIX → AUDIT_CODE → VERSION |
| `/refactor` | Refactor sin cambios funcionales | Área + objetivo | PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE |
| `/audit-code` | Auditoría técnica independiente | Rutas o cambios | Scope → Findings → Verdict |
| `/security-review` | Auditoría de seguridad | Áreas críticas | Findings by severity → Remediation |
| `/tech-debt` | Deuda técnica priorizada | Área o módulo | Findings por severidad → Plan de remediación |
| `/maturity-assessment` | Evaluación de madurez del repo | Área o evaluación completa | Executive summary → Findings → Maturity verdict |
| `/performance-audit-bulk` | Auditoría de rendimiento (bulk: INSERT/UPDATE/DELETE) | Módulo + operaciones + escala + BBDD | PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION (con % impacto) |
| `/performance-audit-dump` | Auditoría de rendimiento (dump: volcado masivo) | Áreas + baseline + BBDD + volumen | 5 fases → informe + roadmap + validación ([guía](./.claude/performance-audit-guide.md)) |
| `/config-review` | Revisión de configuración IA (DRY, huérfanos, bootstrap) | Modo + foco + ficheros | ANÁLISIS → PLAN → AUDIT_PLAN (IMPLEMENT tras aprobación) |
| `/version-closure` | Cierre de versión | Sesión completada | Release notes → Changelog → Rollback → Handoff |

### `/performance-audit-bulk` — Auditoría de Rendimiento (Módulo Bulk)

Usa este comando para auditar el módulo `src/util_bbdd/bulk/` (carga masiva: INSERT/UPDATE/DELETE).

- **Agente especializado**: [@Performance Auditor](./.github/agents/performance-auditor.agent.md)
- **Guía completa**: [`.claude/commands/performance-audit-bulk.md`](./.claude/commands/performance-audit-bulk.md)
- **Prompt de referencia**: [`.github/prompts/performance_audit_bulk.prompt.md`](./.github/prompts/performance_audit_bulk.prompt.md)

**10 áreas auditadas**: Batching | Paralelización | Normalización SQL | Conexiones | Auditoría integrada | Memoria | SQL generation | DB-specific | PK sync | Validation

**Duración estimada**: 4–8 horas (puede dividirse en 2 sesiones de 2–4 hrs c/u)

**Inputs OBLIGATORIOS** (completa TODOS):
- Objetivo: `batching` | `paralelización` | `SQL` | `conexiones` | `auditoría` | `memoria` | `todas`
- Baseline: ¿tienes benchmark? (sí/no)
- Dialects: `PostgreSQL` | `MySQL` | `Oracle` | `SQL Server` | `SQLite` | `todas`
- Volumen: `1K` | `100K` | `1M` | `otro`
- Timeline: `ASAP` | `próxima semana` | `flexible`
- Validación post-audit: sí/no

**Ejemplo de invocación**:

```
/performance-audit-bulk

Objetivo: Auditar rendimiento del módulo bulk (carga masiva de datos)

Alcance: src/util_bbdd/bulk/ — todas las clases y funciones

Inputs requeridos:
  - Objetivo: paralelización + batching
  - Baseline: no (ejecutar benchmark primero)
  - Dialects: PostgreSQL + MySQL + SQL Server
  - Volumen: 100K registros típicos
  - Timeline: ASAP
  - Validación: sí

Puedes consultar internet para best practices y benchmarks.
```

**Outputs generados**:
- `audit_report_bulk_YYYYMMDD.md` — Hallazgos detallados por severidad
- `improvement_roadmap_bulk.md` — Roadmap P0/P1/P2 con timeline
- `validation_report_YYYYMMDD.md` — Benchmark before/after (opcional)

---

**Ejemplo de uso** (otros comandos):

```
/new-feature

Objetivo: Añadir exportación a Parquet en el volcado masivo (dump/)

Alcance: src/util_bbdd/dump/ (writer nuevo), tests/unit/dump/ (tests nuevos)

Restricciones:
  - Mantener compatibilidad con los formatos de salida existentes
  - Usar pandas.DataFrame.to_parquet()
  - Documentación en docstrings + ejemplo en docs/examples/
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

## Flujo estructurado de Claude Code

Cada slash command activa un flujo completo con fases definidas:

### `/new-feature`
```
Fase 1: PLAN → Analizar objetivo, alcance, riesgos, candidatos para cambio
Fase 2: AUDIT_PLAN → Verificar plan, detectar expansion, validar viabilidad
Fase 3: IMPLEMENT → Aplicar cambios, actualizar tests, ejecutar suite
Fase 4: AUDIT_CODE → Revisión independiente de calidad
Fase 5: VERSION → Changelog, commit message, rollback documentation
```

### `/hotfix`
```
Fase 1: RCA (Root Cause Analysis) → Identificar causa raíz del bug
Fase 2: FIX → Aplicar fix mínimo acotado (NO refactorizar)
Fase 3: AUDIT_CODE → Verificar fix, edge cases, pruebas
Fase 4: VERSION → Changelog, commit, rollback steps
Restricción: No refactorizar ni optimizar; solo fix
```

### `/audit-code`
```
Fase 1: Scope → Identificar archivos y responsabilidades
Fase 2: Findings → Hallazgos verificables (bugs, edge cases, contratos rotos)
Fase 3: Verdict → APROBADO | APROBADO CON CONDICIONES | RECHAZADO
Nota: Modo lectura; no edita código. Entrega hallazgos y recomendaciones.
```

### `/tech-debt`
```
Fase 1: Scope → Identificar módulo o área con deuda acumulada
Fase 2: Findings → Clasificar deuda por severidad (alta / media / baja)
Fase 3: Plan → Ordenar por impacto/esfuerzo, proponer remediaciones acotadas
Nota: No aplica cambios; entrega plan de trabajo priorizado.
```

### `/maturity-assessment`
```
Fase 1: Scope → Inventariar estructura, contratos, tests y docs del repo
Fase 2: Findings → Evaluar madurez por área (arquitectura, tipado, cobertura, seguridad)
Fase 3: Verdict → Maturity level + blockers para publicación
Nota: Solo lectura; no edita código.
```

### `/performance-audit-bulk`
```
Fase 1: PLAN → Mapea flujo actual de carga + cuellos de botella teóricos + estrategia de benchmark
Fase 2: AUDIT_PLAN → Valida viabilidad de mejoras, pruebas, orden de ejecución
Fase 3: AUDIT_CODE → Hallazgos por severidad con impacto% estimado, evidencia, remediación
Fase 4: VERSION → Quick wins + fases de implementación + métricas de éxito
Nota: Audita rendimiento de carga masiva (INSERT/UPDATE/DELETE) en módulo bulk.
Puedes consultar internet para benchmarks y best practices.
```

### `/config-review`
```
Fase 1: ANÁLISIS → Clasificar reglas (shared, <plataforma>-only, duplicado, divergente, huérfano)
Fase 2: PLAN → Mapa de migración origen → destino
Fase 3: AUDIT_PLAN → GO | GO_CONDICIONAL | NO_GO; se detiene hasta aprobación
Nota: Solo lectura; aplica Feature Implementer. Modo bootstrap para proyectos destino.
```

### `/version-closure`
```
Fase 1: Resumen → Consolidar todos los cambios de la sesión
Fase 2: Validación → Checklist de .github/instructions/sync.instructions.md (CHANGELOG, pyproject, zensical build)
Fase 3: Handoff → Release notes, commit message, rollback strategy;
         poblar ## Directrices para Futuras IAs en .ai/sessions/*/TRACEABILITY.md
```

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
