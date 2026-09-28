# Prompt: maturity_assessment (Python library)

Evaluación de madurez del repositorio. Solo lectura. Agentes: Explore → Maturity Assessment.

## Inputs recomendados
- **Objetivo**: por qué se evalúa (publicación estable, readiness…)
- **Áreas de foco**: módulos clave o repositorio completo

Son recomendados, no bloqueantes: si faltan, decláralos como supuesto.

## Devuelve en este orden

### PLAN
- objetivo de la evaluación
- áreas analizadas
- fuentes de contexto consultadas

### AUDIT_PLAN
- dimensiones de riesgo priorizadas
- hipótesis de bloqueantes

### AUDIT_CODE
- hallazgos por dimensión con evidencia concreta (`archivo:línea`)
- clasificación: **bloqueante** / **mejora recomendada** / **informativo**
- **Veredicto:** `PRODUCTION_READY | NEAR_READY | BLOCKED`
  - `PRODUCTION_READY`: sin bloqueantes conocidos
  - `NEAR_READY`: bloqueantes menores o mejoras acotadas
  - `BLOCKED`: bloqueantes que impiden publicación o uso fiable

### VERSION
- commit message si hay cambios derivados del assessment
- checklist de acciones previas a publicación

## Evaluar
- estructura del proyecto y coherencia con la jerarquía de capas (`.github/instructions/architecture.instructions.md` § REGLA #6)
- consistencia de APIs públicas (managers sync/async, contratos, tipos)
- tipado (mypy con la configuración de `pyproject.toml`) y docstrings en código público
- seguridad y gestión de recursos (credenciales, SQL dinámico, fugas async)
- tests (cobertura, determinismo, ausencia de dependencias externas)
- documentación generada y ejemplos
- readiness para publicación y mantenimiento a largo plazo
