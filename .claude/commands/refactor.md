# refactor

Refactor sin cambios funcionales. API pública estable salvo justificación explícita.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/refactor.prompt.md` — inputs requeridos, contrato de salida y reglas
2. `.github/agents/plan-architect.agent.md` (PLAN + AUDIT_PLAN), `feature-implementer.agent.md` (IMPLEMENT),
   `code-auditor.agent.md` (AUDIT_CODE) y `version-closer.agent.md` (VERSION)

## Reglas de ejecución

- **⚠️ VALIDACIÓN**: si hay cambio de API pública sin justificación, DETENTE y aclara.
- Detente tras AUDIT_PLAN y espera aprobación explícita antes de IMPLEMENT.

## Ejemplo de entrada

```text
/refactor

Objetivo: separar la construcción del payload de leyenda del renderizado HTML
Módulos: src/util_bbdd/doc/infrastructure/renderers/html_generator.py
Restricción API: no cambia (mismo input/output)
Tests: sí — tests/unit/test_html_generator_diagrams.py
```
