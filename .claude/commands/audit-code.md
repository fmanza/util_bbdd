# audit_code

Auditoría técnica de código con veredicto final. Modo lectura: no edita código.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/audit_code.prompt.md` — inputs requeridos, contrato de salida y reglas
2. `.github/agents/code-auditor.agent.md` — rol y restricciones

## Reglas de ejecución

- **⚠️ VALIDACIÓN**: si no se especifican archivos, DETENTE.

## Ejemplo de entrada

```text
/audit-code

Archivos: src/util_bbdd/metadata/
Contexto: auditoría post-refactor para detectar regresiones
Foco: bugs, edge cases, tipado, tests
```
