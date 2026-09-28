# security_review

Auditoría de seguridad independiente. Hallazgos verificables, ordenados por severidad.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/security_review.prompt.md` — inputs, contrato de salida y reglas
2. `.github/agents/security-reviewer.agent.md` — rol y restricciones

## Reglas de ejecución

- Modo lectura; las remediaciones se aplican después con `/hotfix` o `/new-feature` y commit `security:`.

## Ejemplo de entrada

```text
/security-review

Áreas: src/util_bbdd/doc/, src/util_bbdd/analysis/
Foco: fuga de secretos, SQL injection, exposición de datos sensibles
```
