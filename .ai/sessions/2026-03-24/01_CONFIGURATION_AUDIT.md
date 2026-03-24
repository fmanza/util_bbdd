# CONFIGURATION AUDIT

## Objetivo
Contrastar la configuración real del repositorio frente a la guía 01_VSCODE_SETUP.md y al resto del paquete metodológico.

## Veredicto
GO

## Checklist de cumplimiento

### 1. Instrucciones persistentes de repositorio
- Estado: OK
- Evidencia: .github/copilot-instructions.md existe y define rol, reglas de ejecución, políticas por tipo de tarea y formato esperado.

### 2. Prompt files reutilizables
- Estado: OK
- Evidencia: .github/prompts/ contiene new_feature, hotfix, security_review, refactor, tech_debt y maturity_assessment; además existen audit_code y version_closure como extensiones útiles del flujo.

### 3. Contexto estable del proyecto
- Estado: OK_CON_DESVIACION
- Evidencia: existen .ai/product.md, .ai/architecture.md, .ai/standards.md, .ai/runtime.md y .ai/glossary.md.
- Desviación: el paquete metodológico recomienda .ai/context/, pero el repositorio usa .ai en raíz.
- Impacto: bajo; la información existe y es reutilizable, pero la estructura no es homogénea con la metodología base.

### 4. Contexto de sesión y trazabilidad
- Estado: PARCIAL
- Evidencia: existe .ai/sessions/2026-03-22.
- Desviación: la sesión histórica no sigue el naming estándar 00_PLAN, 02_AUDIT_PLAN, 04_IMPLEMENT, 05_AUDIT_CODE, 07_VERSION_MANAGEMENT.
- Impacto: medio; la trazabilidad histórica existe, pero no está normalizada.

### 5. Tareas de VS Code
- Estado: OK
- Evidencia: .vscode/tasks.json define lint, format, test, type-check y build.
- Impacto: bajo; el flujo ya dispone de comandos normalizados invocables desde VS Code.

### 6. Ajustes de VS Code en repositorio
- Estado: OK
- Evidencia: .vscode/settings.json define pytest, formateo y activación de entorno; util_bbdd.code-workspace añade exclusiones y cwd de terminal.
- Impacto: bajo; la configuración de editor queda reproducible a nivel de repositorio/workspace.

### 7. EditorConfig
- Estado: OK
- Evidencia: .editorconfig define reglas base de charset, fin de línea, indentación, newline final y tratamiento específico de Markdown.
- Impacto: bajo; ahora existe una base transversal complementaria al toolchain Python.

### 8. Toolchain Python del repositorio
- Estado: OK
- Evidencia: pyproject.toml declara pytest, pytest-cov, pytest-asyncio, ruff, mypy, black e isort, además de configuración de pytest y ruff.

## Conclusión operativa
La configuración metodológica del repositorio queda operativa y suficientemente normalizada para trabajo diario con IA en VS Code. La principal desviación residual es estructural: el contexto estable sigue en .ai raíz en lugar de .ai/context/, y la sesión histórica previa no estaba aún normalizada.

## Acciones mínimas recomendadas
- Mantener .ai/*.md como contexto estable actual y registrar esta desviación como decisión temporal.
- Usar desde hoy la nomenclatura metodológica en nuevas sesiones.
- Evaluar en una sesión futura si conviene migrar .ai/*.md a .ai/context/ sin romper hábitos ni enlaces existentes.
- Revisar más adelante si el task build debe apoyarse en dependencia explícita de build en el entorno dev.
