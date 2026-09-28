# tech_debt

Inventario de deuda técnica. No mezclar con nuevas features en el mismo PLAN.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/tech_debt.prompt.md` — inputs, contrato de salida, criterios de prioridad y reglas
2. `.github/agents/plan-architect.agent.md` — análisis; si el scope autoriza IMPLEMENT,
   `feature-implementer.agent.md`, `code-auditor.agent.md` y `version-closer.agent.md`

## Reglas de ejecución

- Si falta algún input, decláralo como supuesto explícito antes de continuar.
- Sin IMPLEMENT autorizado en el scope, solo análisis: no edites archivos.

## Ejemplo de entrada

```text
/tech-debt

Módulo: src/util_bbdd/metadata/mariadb/
Síntomas: Any sueltos y duplicación sync/async
Versión y rama: v0.18.3, develop
Scope: solo análisis
Compatibilidad: no se autoriza romper contratos públicos
```
