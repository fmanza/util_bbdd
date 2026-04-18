# Prompt: config_review — Revisión y redefinición de ficheros de configuración IA

## Objetivo

Revisar los ficheros de instrucciones actuales del proyecto y generar una propuesta de
configuración nueva, mejor estructurada y sin duplicación, que funcione correctamente
tanto para **GitHub Copilot Chat** como para **Claude Code**.

## Devuelve en este orden

1. ANÁLISIS
2. PLAN
3. AUDIT_PLAN
4. IMPLEMENT
5. AUDIT_CODE
6. VERSION

## Contexto a completar

- Ficheros de referencia actuales:
- Estrategia elegida (Opción A / Opción B):
- Contenido a unificar o separar:
- Restricciones de compatibilidad (romper contratos públicos: sí/no):

## Instrucciones previas obligatorias

Lee los siguientes ficheros **antes** de emitir cualquier propuesta:

- `.github/copilot-instructions.md` — instrucciones actuales para Copilot Chat
- `CLAUDE.md` — instrucciones actuales para Claude Code

## Análisis previo que debes hacer

Antes de proponer, clasifica cada sección de ambos ficheros en una de estas categorías:

| Categoría | Descripción |
|---|---|
| `shared` | Regla válida para ambas plataformas sin cambios |
| `copilot-only` | Específico de Copilot Chat (agentes VS Code, `#file:`, prompts `.prompt.md`) |
| `claude-only` | Específico de Claude Code (slash commands, hooks, settings.json, ejecución offline) |
| `duplicado` | Presente en ambos ficheros con variaciones menores — candidato a unificar |

## Estrategias disponibles

### Opción A — Fichero compartido + especializaciones

```
SHARED_INSTRUCTIONS.md              ← reglas comunes, referenciado desde los demás
.github/copilot-instructions.md     ← solo overrides y especificidades Copilot Chat
CLAUDE.md                           ← solo overrides y especificidades Claude Code
```

Elige esta opción si el contenido compartido supera el 60 % del total.

### Opción B — Ficheros completamente separados (sin dependencia cruzada)

```
.github/copilot-instructions.md     ← autosuficiente para Copilot Chat
CLAUDE.md                           ← autosuficiente para Claude Code
```

Elige esta opción si cada plataforma tiene ciclo de vida o equipo de mantenimiento propio.

## Criterios de calidad

- Sin duplicación de reglas entre ficheros (DRY)
- Cada fichero es funcional sin necesidad de leer el otro
- El flujo `PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION` está presente en ambos contextos
- Las secciones específicas de cada plataforma están claramente delimitadas
- Formato: markdown estructurado con secciones etiquetadas

## Formato de salida esperado

### ANÁLISIS
- Tabla categorizada (shared / copilot-only / claude-only / duplicado)
- Porcentaje estimado de contenido compartido

### PLAN
- Estrategia elegida y justificación
- Ficheros resultantes (rutas y responsabilidad de cada uno)
- Riesgos de divergencia futura

### AUDIT_PLAN
- Riesgos funcionales
- Riesgos de mantenimiento
- Simplificaciones posibles
- Veredicto: `GO | GO_CONDICIONAL | NO_GO`

### IMPLEMENT
- Contenido completo de cada fichero propuesto

### AUDIT_CODE
- Cobertura de reglas clave (SOLID, OOP, multibase, políticas por tarea)
- Secciones ausentes o incompletas
- Veredicto: `APROBADO | APROBADO CON CONDICIONES | RECHAZADO`

### VERSION
- Commit message (Conventional Commits)
- Changelog
- Diff conceptual: qué desaparece, qué se mueve, qué es nuevo
- Rollback: pasos para volver al estado anterior
