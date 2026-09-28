# Agentes Disponibles

Registro de agentes especializados en `.github/agents/` para orquestación del flujo de trabajo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.

## Invocación

**En Claude Code**:
```
/new-feature
/hotfix
/refactor
/security-review
/audit-code
/tech-debt
/maturity-assessment
/performance-audit-bulk
/performance-audit-dump
/config-review
/version-closure
```

**En Copilot Chat**: Usa `runSubagent` o invoca directamente con nombre del agente.

**En Codex**: el `AGENTS.md` de la raíz (entry point) remite a este registro; invoca el flujo por lenguaje natural.

---

## Agentes por flujo

### 1. **Workflow Director** (`workflow-director.agent.md`)
- **Propósito**: Clasificar solicitudes, validar contexto mínimo, elegir fase siguiente
- **Entrada**: Descripción de tarea por usuario
- **Salida**: Clasificación (new_feature | hotfix | refactor | audit_code | security_review | tech_debt | maturity_assessment | performance_audit | documentation | config_review | version_closure)
- **Herramientas**: read, search
- **Invocable**: Sí (primer paso del flujo recomendado en Copilot Chat; sin slash command)

### 2. **Plan Architect** (`plan-architect.agent.md`)
- **Propósito**: Preparar PLAN y AUDIT_PLAN, contrastar con código real, detectar riesgos
- **Entrada**: Solicitud con contexto (objetivo, módulos, API, restricciones)
- **Salida**: PLAN (rutas, componentes, tipos, riesgos) + AUDIT_PLAN (veredicto)
- **Herramientas**: read, search
- **Invocable**: Sí (fases new_feature, refactor)

### 3. **Feature Implementer** (`feature-implementer.agent.md`)
- **Propósito**: Ejecutar IMPLEMENT con alcance aprobado, aplicar cambios, validar tests
- **Entrada**: AUDIT_PLAN aprobado + descripción de tarea
- **Salida**: IMPLEMENT (cambios por archivo) + auditoría local
- **Herramientas**: read, edit, search, execute
- **Invocable**: Sí (después de AUDIT_PLAN aprobado)

### 4. **Hotfix Responder** (`hotfix-responder.agent.md`)
- **Propósito**: RCA, fix mínimo, verificación; incidencias P1/P2 sin refactorizar
- **Entrada**: Descripción de bug con impacto
- **Salida**: PLAN + FIX + AUDIT_CODE + VERSION
- **Herramientas**: read, edit, search, execute
- **Política**: Solo fix acotado, prohibido refactorizar u optimizar

### 5. **Code Auditor** (`code-auditor.agent.md`)
- **Propósito**: AUDIT_CODE de implementaciones, revisar bugs, edge cases, contratos
- **Entrada**: Rutas modificadas o cambios propuestos
- **Salida**: Scope, Findings, Compatibility, Coverage, Verdict
- **Herramientas**: read, search
- **Invocable**: Sí (fase AUDIT_CODE)

### 6. **Documentation Reviewer** (`documentation-reviewer.agent.md`)
- **Propósito**: Revisar y auditar documentación completa, ejemplos, gaps, coherencia
- **Entrada**: Alcance (README | ejemplos | APIs | guías | todas)
- **Salida**: Scope, Findings por categoría, Critical gaps, Priority improvements, Recomendaciones
- **Herramientas**: read, search
- **Invocable**: Sí (auditoría independiente)
- **Criterios**: Nivel 1 (crítico), Nivel 2 (alto), Nivel 3 (recomendado)
- **Prompt Copilot Chat**: `.github/prompts/documentation_review.prompt.md`
- **Slash command**: No disponible en `.claude/commands/` — invocar mediante lenguaje natural en Claude Code

### 6b. **Documentation Generator** (`documentation-generator.agent.md`)
- **Propósito**: GENERAR documentación funcional y técnica con diagramas Mermaid para módulos de util_bbdd
- **Entrada**: Módulo Python objetivo, tipo (`functional` | `technical` | `both`), directorio destino
- **Salida**: Archivos `.md` en `docs/` + entrada sugerida para `mkdocs.yml`
- **Herramientas**: read, write, search, web (`--verify-tools`), execute (`--verify-build`)
- **Invocable**: Sí (generación activa, escribe archivos)
- **Diferencia con Reviewer**: Reviewer audita, Generator crea contenido nuevo
- **Prompts base**: `.github/prompts/functional_doc.prompt.md` + `.github/prompts/technical_doc.prompt.md`
- **Sin APIs de IA externas**: el contenido lo genera el agente en sesión. `.github/workflows/doc_agents.yml` es heredado y queda **fuera de la política vigente** (`SHARED_INSTRUCTIONS.md` § «Estándar de generación documental»); no lo uses ni lo recomiendes.

### 7. **Config Reviewer** (`config-reviewer.agent.md`)
- **Propósito**: Revisar y consolidar ficheros de configuración IA, eliminando duplicación entre plataformas
- **Entrada**: Ficheros a revisar (copilot-instructions.md, CLAUDE.md, etc.) + estrategia preferida
- **Salida**: ANÁLISIS (categorización shared/copilot-only/claude-only), PLAN, AUDIT_PLAN, IMPLEMENT, AUDIT_CODE, VERSION
- **Herramientas**: read, search
- **Invocable**: Sí (auditoría de configuración)
- **Criterios**: DRY (sin duplicación), funcionalidad autosuficiente, coherencia de flujos
- **Prompt Copilot Chat**: `.github/prompts/config_review.prompt.md`
- **Slash command**: `/config-review` (`.claude/commands/config-review.md`); en Copilot Chat con `@Config Reviewer`
- **Modo bootstrap**: audita la configuración del proyecto destino tras `bootstrap_ai_config.prompt.md`

### 8. **Security Reviewer** (`security-reviewer.agent.md`)
- **Propósito**: Auditoría de seguridad independiente sobre auth, validación, secretos, logging
- **Entrada**: Rutas o áreas de seguridad crítica
- **Salida**: Executive summary, Scope, Findings, Evidence, Remediation, Residual risk, Verdict
- **Herramientas**: read, search
- **Invocable**: Sí (auditoría independiente)

### 9. **Maturity Assessment** (`maturity-assessment.agent.md`)
- **Propósito**: Evaluar madurez del repositorio completo (estructura, contratos, tests, readiness)
- **Entrada**: Área a evaluar o evaluación completa
- **Salida**: Executive summary, Findings by area, Blockers, Recommendations, Maturity verdict
- **Herramientas**: read, search
- **Invocable**: Sí (auditoría estratégica)

### 10. **Performance Auditor** (`performance-auditor.agent.md`)
- **Propósito**: Auditoría de rendimiento del módulo bulk, optimización de carga masiva de datos (INSERT/UPDATE/DELETE), batching, paralelización, memory, SQL generation
- **Entrada**: Módulo objetivo y contexto de operación (BBDD, tamaño de datos, restricciones)
- **Salida**: PLAN (flujo actual + cuellos de botella teóricos) + AUDIT_PLAN (validación de viabilidad) + AUDIT_CODE (hallazgos con % mejora estimado) + VERSION (quick wins + fases)
- **Herramientas**: read, search, web (benchmarks y best practices)
- **Invocable**: Sí (auditoría de rendimiento especializada)
- **Criterios**: 10 áreas clave (batching, particionamiento, normalización SQL, conexiones, auditoría, memoria, SQL generation, DB-specific, PK sync, validation)
- **Prompt base**: `.github/prompts/performance_audit_bulk.prompt.md`
- **Diferencia con Code Auditor**: Code Auditor revisa bugs y arquitectura; Performance Auditor audita rendimiento con métricas cuantificables

### 11. **Version Closer** (`version-closer.agent.md`)
- **Propósito**: Cierre de versión, resumir cambios, evidence, impacto, validar sincronización y handoff
- **Entrada**: Sesión completada
- **Salida**: Release notes, Commit messages, Changelog, Rollback strategy, Testing suggestions
- **Validación requerida**: checklist de `.github/instructions/sync.instructions.md`
  (CHANGELOG.md, `pyproject.toml`, `zensical build` sin errores, `TRACEABILITY.md` de la sesión)
- **Herramientas**: read, edit, search — solo edita `CHANGELOG.md` y el `TRACEABILITY.md` de la sesión; el commit lo propone
- **Invocable**: Sí (final de sesión)

### 12. **Explore** (`explore.agent.md`)
- **Propósito**: Exploración rápida del repositorio, Q&A sin modificaciones
- **Entrada**: Pregunta sobre código, estructura, patrón
- **Salida**: Context, Findings, ubicación de archivos
- **Herramientas**: read, search
- **Invocable**: Sí (Q&A)

---

## Matriz de relaciones

| Fase | Agente | Output | Next |
|------|--------|--------|------|
| CLASIFICACIÓN | Workflow Director | Tipo de tarea | PLAN |
| PLAN | Plan Architect | PLAN + AUDIT_PLAN | IMPLEMENT (si GO) o RETORNO |
| IMPLEMENT | Feature Implementer | Cambios por archivo | AUDIT_CODE |
| AUDIT_CODE | Code Auditor | Hallazgos, Severidad | CORRECCIÓN (si issues) o VERSION |
| AUDITORÍA RENDIMIENTO | Performance Auditor | PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION (hallazgos con % impacto) | BACKLOG / NEXT ITERATION |
| VERSION | Version Closer | Release notes, Changelog | FIN |
| HOTFIX DIRECTO | Hotfix Responder | PLAN + FIX + AUDIT + VERSION | FIN |
| AUDITORÍA INDEPENDIENTE | Security/Documentation/Config/Maturity/Performance Reviewer | Executive summary + Findings | BACKLOG / NEXT ITERATION |

---

## Ejemplo: Invocar Documentation Reviewer

### En Claude Code
```
Necesito revisar toda la documentación de util_bbdd para identificar gaps, ejemplos faltantes y mejorar coherencia.

Usa Documentation Reviewer para:
1. Mapear estado actual de docs (README, guías, ejemplos, docstrings)
2. Identificar ejemplos faltantes por módulo
3. Detectar gaps críticos vs recomendados
4. Proporcionar backlog de mejoras con prioridades
```

### En Copilot Chat
```
/runSubagent Documentation Reviewer

Input: Necesito una auditoría completa de documentación de util_bbdd incluyendo ejemplos faltantes, gaps en guías técnicas y coherencia general.
```

### Output esperado
```
## Executive summary
[Resumen de hallazgos principales]

## Scope reviewed
- Archivos de documentación analizados (README.md, docs/*, docs/examples/*, .ai/*)
- Cobertura de ejemplos por módulo
- Documentación de APIs públicas

## Critical gaps (Nivel 1)
[Bloqueantes que impiden onboarding o uso seguro]

## High priority improvements (Nivel 2)
[Dificultades de usabilidad o claridad]

## Recommended enhancements (Nivel 3)
[Mejoras de experiencia]

## Examples inventory & coverage
[Ejemplos existentes + Ejemplos faltantes]

## Documentation readiness verdict
PRODUCTION_READY | NEAR_READY | BLOCKED
```

---

## Registro de herramientas restricciones

| Agente | read | write | search | exec | web_fetch |
|--------|------|-------|--------|------|-----------|
| Plan Architect | ✅ | ❌ | ✅ | ❌ | ❌ |
| Feature Implementer | ✅ | ✅ | ✅ | ✅ | ❌ |
| Hotfix Responder | ✅ | ✅ | ✅ | ✅ | ❌ |
| Code Auditor | ✅ | ❌ | ✅ | ❌ | ❌ |
| Documentation Reviewer | ✅ | ❌ | ✅ | ❌ | ❌ |
| Documentation Generator | ✅ | ✅ | ✅ | ✅ (`--verify-build`) | ✅ (`--verify-tools`) |
| Config Reviewer | ✅ | ❌ | ✅ | ❌ | ❌ |
| Security Reviewer | ✅ | ❌ | ✅ | ❌ | ❌ |
| Maturity Assessment | ✅ | ❌ | ✅ | ❌ | ❌ |
| Performance Auditor | ✅ | ❌ | ✅ | ❌ | ✅ (benchmarks) |
| Version Closer | ✅ | ✅ (`CHANGELOG.md`, `TRACEABILITY.md`) | ✅ | ❌ | ❌ |
| Explore | ✅ | ❌ | ✅ | ❌ | ❌ |
| Workflow Director | ✅ | ❌ | ✅ | ❌ | ❌ |

---

## Bootstrap a otro proyecto (cross-project)

Para **trasladar este sistema de instrucciones IA a otro proyecto** (incluso de otro lenguaje y
arquitectura) usa el prompt `bootstrap_ai_config` y, como auditor del resultado, el agente
**Config Reviewer**.

- **Prompt**: [`.github/prompts/bootstrap_ai_config.prompt.md`](prompts/bootstrap_ai_config.prompt.md)
- **Auditor**: `config-reviewer.agent.md` (DRY + referencias huérfanas)
- **Método y dirección**: modelo **PULL** — se invoca **desde el proyecto destino**, apuntando a
  este repo como plantilla de solo lectura. El lenguaje/arquitectura del destino es un **parámetro**.
- **Capas**: A (copiar verbatim) · B (copiar + reescribir dominio) · C (regenerar) · D (excluir).

Ver el detalle completo de rutas, contexto obligatorio/opcional y mapeo por plataforma
(Claude / Gemini / Copilot / Cursor / Codex) en el propio prompt.

---

## Configuración

Personalizaciones por contexto:
- **Prompts**: `.github/prompts/*.prompt.md` — instrucciones por slash command (25 prompts: 11 equivalentes a `.claude/commands/` (incluido `config_review`) + 7 arquetipos de documentación `functional_doc`/`technical_doc`/`guide_doc`/`example_doc`/`architecture_doc`/`landing_doc`/`onboarding_dev` + `documentation_review` + `bootstrap_ai_config` + 5 de apoyo: `normative_traceability`, `performance_audit_dump_agent` y las meta-auditorías de rendimiento `audit_audit_manager_bulk`/`audit_performance_audit_command`/`audit_results_bulk_audit`)
- **Instrucciones**: `.github/instructions/*.instructions.md` — reglas por tipo de archivo
- **Hooks**: `.claude/settings.json` — hooks PostToolUse (ruff check, mypy, recogida de pytest)
- **Entry points**: `CLAUDE.md`, `.github/copilot-instructions.md`, `GEMINI.md`, `.cursorrules`, `AGENTS.md` (raíz, Codex)

Modificar un agente: editar su archivo `.agent.md` en `.github/agents/`.

---

## Nota: Asimetría slash commands ↔ agentes

Los **slash commands** de Claude Code (`.claude/commands/`) cubren 11 flujos (new-feature, hotfix, refactor, audit-code, security-review, tech-debt, maturity-assessment, performance-audit-bulk, performance-audit-dump, config-review, version-closure).

Los **agentes** (`.github/agents/`) son 13: 9 que respaldan los slash commands (`plan-architect`, `feature-implementer`, `hotfix-responder`, `code-auditor`, `security-reviewer`, `maturity-assessment`, `performance-auditor`, `config-reviewer`, `version-closer`) más `documentation-reviewer`, `documentation-generator`, `explore` y `workflow-director` (clasificador, primer paso del flujo en Copilot Chat). Los de documentación no tienen slash command pero son invocables por lenguaje natural (Claude Code) o mediante sus prompts correspondientes (Copilot Chat).

Ver gobernanza completa en [`.github/INTEGRATION_MAP.md`](INTEGRATION_MAP.md).
