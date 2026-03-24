# CONTEXT SNAPSHOT

## Metodología leída
- README.md
- 01_VSCODE_SETUP.md
- 02_CONTEXTO_Y_PROMPTING.md
- 03_BIBLIOTECA_DE_PROMPTS.md
- 04_FASES_Y_ARTEFACTOS.md
- 05_GATES_TRAZABILIDAD_Y_GOBIERNO.md
- 06_EJEMPLOS_PRACTICOS.md
- 07_REFERENCIAS.md

## Contexto del repositorio revisado
- .github/copilot-instructions.md
- .github/prompts/new_feature.prompt.md
- .ai/architecture.md
- .ai/product.md
- .ai/standards.md
- .ai/runtime.md
- .ai/glossary.md
- pyproject.toml
- util_bbdd.code-workspace
- docs\v0.6.1\crear_prompt.md
- .ai/sessions/2026-03-22/* como referencia histórica

## Estado actual observado
- Existe customización de repositorio en .github/copilot-instructions.md.
- Existen prompt files metodológicos en .github/prompts/ para new_feature, hotfix, security_review, refactor, tech_debt y maturity_assessment.
- Existe contexto estable del proyecto en .ai/*.md.
- Existe carpeta de sesiones .ai/sessions/, pero la sesión histórica previa no sigue aún la nomenclatura por fases del paquete metodológico externo.
- No existe .ai/context/ como layout recomendado por la metodología; el repositorio usa .ai en raíz como contexto estable efectivo.
- Existe .vscode/settings.json con configuración Python y de guardado.
- Existe .vscode/tasks.json con tareas estándar de lint, format, test, type-check y build.
- Existe .editorconfig con reglas base de fin de línea, indentación y newline final.
- util_bbdd.code-workspace ya incorpora exclusiones de artefactos y activación del entorno para terminal.
- pyproject.toml sí declara pytest, ruff, mypy, black e isort.

## Estado Git relevante
- Rama activa: develop.
- Hay cambios locales no relacionados con esta sesión en src\util_bbdd\analysis\graphviz_ext.py.
- docs\v0.6.1\crear_prompt.md está presente en el working tree y ha sido usado como input funcional de esta sesión.

## Clasificación metodológica
- Tipo principal: new_feature.
- Estado real de alcance: mezclado con refactor arquitectónico, cambios de documentación, investigación externa y cierre de versión.
- Consecuencia: la solicitud necesita descomposición por fases antes de autorizar implementación.

## Gate G0 · Context Ready
Veredicto: GO

Motivo:
- Hay objetivo funcional suficiente.
- Hay archivos candidatos identificados.
- Hay restricciones explícitas.
- Existe evidencia suficiente para planificar y auditar el plan.

## Datos faltantes aún abiertos
- Criterio exacto para representar u omitir vistas en diagramas.
- Definición cerrada de “Salida oculta” en la documentación funcional.
- Nivel de investigación externa permitido sobre SchemaSpy antes de pasar a diseño detallado.
- Decisión formal sobre si la refactorización arquitectónica se ejecutará como flujo separado o como prerequisito autorizado de la feature.
