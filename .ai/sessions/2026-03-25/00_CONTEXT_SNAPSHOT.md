# CONTEXT SNAPSHOT

## Metodología leída
- README.md
- 02_CONTEXTO_Y_PROMPTING.md
- 03_BIBLIOTECA_DE_PROMPTS.md
- 04_FASES_Y_ARTEFACTOS.md
- 05_GATES_TRAZABILIDAD_Y_GOBIERNO.md
- 06_EJEMPLOS_PRACTICOS.md
- 07_REFERENCIAS.md

## Contexto del repositorio revisado
- .github/copilot-instructions.md
- .github/prompts/
- .vscode/settings.json
- .vscode/tasks.json
- util_bbdd.code-workspace
- .editorconfig
- .ai/architecture.md
- .ai/product.md
- .ai/runtime.md
- .ai/standards.md
- .ai/glossary.md
- docs\v0.6.2\crear_prompt.md

## Estado actual observado
- El repositorio mantiene customización persistente en .github/copilot-instructions.md.
- Existen prompt files metodológicos en .github/prompts/ para new_feature, hotfix, security_review, refactor, tech_debt, maturity_assessment, audit_code y version_closure.
- El contexto estable del proyecto sigue en .ai/ raíz y no en .ai/context/ como recomienda la metodología externa.
- Existen .vscode/settings.json, .vscode/tasks.json, util_bbdd.code-workspace y .editorconfig alineados con el flujo recomendado.
- La carpeta .ai/sessions/ contiene sesiones históricas 2026-03-22 y 2026-03-24.
- No existe todavía carpeta de sesión para 2026-03-25.
- docs\v0.6.2\crear_prompt.md existe y es el input funcional de esta sesión.

## Estado Git relevante
- Rama activa: develop.
- El árbol contiene elementos no versionados ajenos a esta sesión:
  - docs/prompt/prompt-base.md
  - docs/v0.6.2/
  - docs/v0.6.3/
- Esta sesión debe convivir con esos cambios sin reordenarlos ni limpiarlos.

## Clasificación metodológica
- Tipo principal: new_feature.
- Estado real del alcance: mezcla new_feature con decisiones de visualización, potenciales breaking changes, documentación, migración y cierre de versión.
- Consecuencia: no conviene autorizar IMPLEMENT en la misma sesión sin acotar primero alcance y contratos.

## Gate G0 · Context Ready
Veredicto: GO

## Motivo
- Hay objetivo suficientemente claro.
- El documento de entrada existe.
- El repositorio expone contexto estable y configuración operativa verificable.
- Las restricciones y el formato esperado quedan suficientemente definidos para planificar.

## Datos faltantes aún abiertos
- Inventario exacto de contratos públicos afectados en analysis y doc para la línea v0.6.2.
- Criterio técnico final para recolocar cardinalidades sin degradar legibilidad ni romper la generación actual.
- Baseline visual exacto que se tomará como referencia para validar la reducción de tamaño de nodos y la recolocación de cardinalidades.
