# hotfix

Corrección acotada de un bug P1/P2. Política: **solo fix mínimo; prohibido refactorizar y optimizar**.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/hotfix.prompt.md` — inputs requeridos, contrato de salida y reglas
2. `.github/agents/hotfix-responder.agent.md` (RCA + fix), `code-auditor.agent.md` (AUDIT_CODE) y
   `version-closer.agent.md` (VERSION)

## Reglas de ejecución

- **⚠️ VALIDACIÓN**: si no puedes emitir un PLAN con diagnóstico de causa raíz claro, DETENTE.
- Commit con tipo `hotfix:` (ver `SHARED_INSTRUCTIONS.md` § «Formato de commits»).

## Ejemplo de entrada

```text
/hotfix

Bug: el renderer HTML pierde los iconos al exportar fuera del workspace
Rutas: src/util_bbdd/doc/infrastructure/renderers/html_generator.py, src/util_bbdd/doc/data/html_assets/
Síntomas: al abrir el HTML desde otra ruta, los iconos desaparecen
Supuesto: los assets deben embeberse (base64), no referenciarse por ruta
```
