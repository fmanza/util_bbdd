# maturity_assessment

Evaluación de madurez del repositorio. Separar bloqueantes de mejoras recomendadas. Solo lectura.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/prompts/maturity_assessment.prompt.md` — inputs, dimensiones, contrato de salida y veredicto
2. `.github/agents/explore.agent.md` (inventario) y `maturity-assessment.agent.md` (evaluación)

## Reglas de ejecución

- Los inputs son recomendados: si faltan, emite supuestos explícitos.

## Ejemplo de entrada

```text
/maturity-assessment

Objetivo: readiness para publicar la versión estable
Áreas: bulk/, dump/, metadata/ (o repositorio completo)
```
