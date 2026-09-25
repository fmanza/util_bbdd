# config_review

Revisión de la configuración IA del repositorio (o de un proyecto destino tras un bootstrap).
Solo lectura: propone y emite veredicto; no edita archivos.

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/agents/config-reviewer.agent.md` — rol, inventario, categorías, comprobaciones obligatorias y modo bootstrap
2. `.github/prompts/config_review.prompt.md` — fases y formato de salida

## Inputs requeridos (OBLIGATORIO completar TODOS)

- [ ] **Modo**: `repo` (configuración de util_bbdd) | `bootstrap` (configuración del proyecto destino abierto)
- [ ] **Foco**: `duplicación` | `referencias huérfanas` | `paridad comandos/prompts/agentes` | `documentación` | `todo`
- [ ] **Ficheros**: rutas concretas o `todos` (inventario completo del agente)
- [ ] **Fases**: `análisis` (ANÁLISIS + PLAN + AUDIT_PLAN) | `completo` (incluye IMPLEMENT, AUDIT_CODE y VERSION tras aprobación)

**⚠️ VALIDACIÓN**: Si falta alguno, asume `repo` · `todo` · `todos` · `análisis` y decláralo como supuesto explícito.

## Reglas de ejecución

- No edites archivos ni ejecutes comandos durante ANÁLISIS, PLAN y AUDIT_PLAN.
- Detente tras AUDIT_PLAN y espera aprobación explícita antes de IMPLEMENT.
- IMPLEMENT lo aplica **Feature Implementer** (o `/refactor` si el cambio es estructural); este comando solo entrega el contenido propuesto.
- Cita `fichero:línea` en cada hallazgo.

## Ejemplo de entrada

```
/config-review

Modo: repo
Foco: duplicación + referencias huérfanas
Ficheros: CLAUDE.md, .github/copilot-instructions.md, .github/SHARED_INSTRUCTIONS.md
Fases: análisis
```

## Ejemplo de entrada (bootstrap, desde el proyecto destino)

```
/config-review

Modo: bootstrap
Origen (solo lectura): c:\Desarrollo\python\libs\util_bbdd
Foco: todo
Ficheros: todos
Fases: análisis
```

En el proyecto destino este comando solo existe si el bootstrap copió `.claude/commands/` (capa A).
