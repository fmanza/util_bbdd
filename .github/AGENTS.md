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
/version-closure
```

**En Copilot Chat**: Usa `runSubagent` o invoca directamente con nombre del agente.

---

## Agentes por flujo

### 1. **Workflow Director** (`workflow-director.agent.md`)
- **Propósito**: Clasificar solicitudes, validar contexto mínimo, elegir fase siguiente
- **Entrada**: Descripción de tarea por usuario
- **Salida**: Clasificación (new_feature | hotfix | refactor | security_review | tech_debt | maturity_assessment | version_closure)
- **Herramientas**: read, search
- **Invocable**: No (interno)

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
- **Herramientas**: read, write, exec (run_task, run_in_terminal)
- **Invocable**: Sí (después de AUDIT_PLAN aprobado)

### 4. **Hotfix Responder** (`hotfix-responder.agent.md`)
- **Propósito**: RCA, fix mínimo, verificación; incidencias P1/P2 sin refactorizar
- **Entrada**: Descripción de bug con impacto
- **Salida**: PLAN + FIX + AUDIT_CODE + VERSION
- **Herramientas**: read, write, exec
- **Política**: Solo fix acotado, prohibido refactorizar u optimizar

### 5. **Code Auditor** (`code-auditor.agent.md`)
- **Propósito**: AUDIT_CODE de implementaciones, revisar bugs, edge cases, contratos
- **Entrada**: Rutas modificadas o cambios propuestos
- **Salida**: Scope, Findings, Compatibility, Coverage, Verdict
- **Herramientas**: read, search
- **Invocable**: Sí (fase AUDIT_CODE)

### 6. **Documentation Reviewer** (`documentation-reviewer.agent.md`) ⭐ **NUEVO**
- **Propósito**: Revisar y auditar documentación completa, ejemplos, gaps, coherencia
- **Entrada**: Alcance (README | ejemplos | APIs | guías | todas)
- **Salida**: Scope, Findings por categoría, Critical gaps, Priority improvements, Recomendaciones
- **Herramientas**: read, search
- **Invocable**: Sí (auditoría independiente)
- **Criterios**: Nivel 1 (crítico), Nivel 2 (alto), Nivel 3 (recomendado)
- **Prompt Copilot Chat**: `.github/prompts/documentation_review.prompt.md`
- **Slash command**: No disponible en `.claude/commands/` — invocar mediante lenguaje natural en Claude Code

### 7. **Security Reviewer** (`security-reviewer.agent.md`)
- **Propósito**: Auditoría de seguridad independiente sobre auth, validación, secretos, logging
- **Entrada**: Rutas o áreas de seguridad crítica
- **Salida**: Executive summary, Scope, Findings, Evidence, Remediation, Residual risk, Verdict
- **Herramientas**: read, search
- **Invocable**: Sí (auditoría independiente)

### 8. **Maturity Assessment** (`maturity-assessment.agent.md`)
- **Propósito**: Evaluar madurez del repositorio completo (estructura, contratos, tests, readiness)
- **Entrada**: Área a evaluar o evaluación completa
- **Salida**: Executive summary, Findings by area, Blockers, Recommendations, Maturity verdict
- **Herramientas**: read, search
- **Invocable**: Sí (auditoría estratégica)

### 9. **Version Closer** (`version-closer.agent.md`)
- **Propósito**: Cierre de versión, resumir cambios, evidence, impacto, handoff
- **Entrada**: Sesión completada
- **Salida**: Release notes, Commit messages, Changelog, Rollback strategy, Testing suggestions
- **Herramientas**: read, search
- **Invocable**: Sí (final de sesión)

### 10. **Explore** (`explore.agent.md`)
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
| VERSION | Version Closer | Release notes, Changelog | FIN |
| HOTFIX DIRECTO | Hotfix Responder | PLAN + FIX + AUDIT + VERSION | FIN |
| AUDITORÍA INDEPENDIENTE | Security/Documentation/Maturity Reviewer | Executive summary + Findings | BACKLOG / NEXT ITERATION |

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
- Archivos de documentación analizados (README.md, docs/v0.6.7/*, docs/examples/*)
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
| Feature Implementer | ✅ | ✅ | ❌ | ✅ | ❌ |
| Hotfix Responder | ✅ | ✅ | ❌ | ✅ | ❌ |
| Code Auditor | ✅ | ❌ | ✅ | ❌ | ❌ |
| Documentation Reviewer | ✅ | ❌ | ✅ | ❌ | ❌ |
| Security Reviewer | ✅ | ❌ | ✅ | ❌ | ❌ |
| Maturity Assessment | ✅ | ❌ | ✅ | ❌ | ❌ |
| Version Closer | ✅ | ❌ | ✅ | ❌ | ❌ |
| Explore | ✅ | ❌ | ✅ | ❌ | ❌ |
| Workflow Director | ✅ | ❌ | ✅ | ❌ | ❌ |

---

## Configuración

Personalizaciones por contexto:
- **Prompts**: `.github/prompts/*.prompt.md` — instrucciones por slash command (9 prompts; 8 equivalentes a `.claude/commands/` + `documentation_review`)
- **Instrucciones**: `.github/instructions/*.instructions.md` — reglas por tipo de archivo
- **Hooks**: `.claude/settings.json` — comandos pre/post tool (lint, format, type-check)

Modificar un agente: editar su archivo `.agent.md` en `.github/agents/`.

---

## Nota: Asimetría slash commands ↔ agentes

Los **slash commands** de Claude Code (`.claude/commands/`) cubren 8 flujos (new-feature, hotfix, refactor, audit-code, security-review, tech-debt, maturity-assessment, version-closure).

Los **agentes** (`.github/agents/`) son 10: incluyen los 8 anteriores más `documentation-reviewer` y `explore`, que no tienen slash command pero son invocables por lenguaje natural (Claude Code) o mediante `.github/prompts/documentation_review.prompt.md` (Copilot Chat).

Ver gobernanza completa en [`.github/INTEGRATION_MAP.md`](INTEGRATION_MAP.md).
