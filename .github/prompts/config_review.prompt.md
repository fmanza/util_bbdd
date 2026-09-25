# Prompt: config_review — Revisión y redefinición de ficheros de configuración IA

## Objetivo

Revisar los ficheros de instrucciones actuales del proyecto y generar una propuesta de
configuración nueva, mejor estructurada y sin duplicación, que funcione correctamente
en todas las plataformas activas (**Claude Code**, **GitHub Copilot Chat**, **Gemini**, **Codex**, **Cursor**).

Agente ejecutor: `.github/agents/config-reviewer.agent.md` (categorías, comprobaciones obligatorias,
métrica de duplicación y modo bootstrap). Este prompt define el formato de salida.

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
- Alcance documental: incluir agentes/prompts de documentación y `mkdocs.yml` cuando aplique:

## Instrucciones previas obligatorias

Lee los siguientes ficheros **antes** de emitir cualquier propuesta:

- `.github/SHARED_INSTRUCTIONS.md` — fuente canónica y § «Gobernanza de plataformas IA»
- `.github/AGENTS.md` — registro de agentes, prompts y slash commands
- `.github/copilot-instructions.md`, `CLAUDE.md`, `GEMINI.md`, `.cursorrules` — entry points por plataforma
- `.github/instructions/docs.instructions.md` — reglas canónicas de documentación
- `.github/agents/documentation-generator.agent.md` — generación/actualización documental
- `.github/agents/documentation-reviewer.agent.md` — revisión documental
- `.github/prompts/functional_doc.prompt.md` — prompt funcional
- `.github/prompts/technical_doc.prompt.md` — prompt técnico
- `.github/prompts/documentation_review.prompt.md` — prompt de revisión documental
- `mkdocs.yml` — navegación y configuración documental, si el cambio afecta docs

## Análisis previo que debes hacer

Antes de proponer, clasifica cada sección de los ficheros auditados con las categorías del agente
(`shared`, `<plataforma>-only`, `docs-shared`, `duplicado`, `divergente`, `huérfano`), definidas en
`.github/agents/config-reviewer.agent.md` § «Categorías de clasificación».

## Estrategias disponibles

### Opción A — Fichero compartido + especializaciones (**vigente**)

```
.github/SHARED_INSTRUCTIONS.md      ← reglas comunes, referenciado desde los demás
.github/copilot-instructions.md     ← solo especificidades Copilot Chat
CLAUDE.md                           ← solo especificidades Claude Code
GEMINI.md / .cursorrules            ← solo especificidades Gemini / Cursor
```

Elige esta opción si el contenido compartido supera el 60 % del total.

### Opción B — Ficheros completamente separados (sin dependencia cruzada)

```
.github/copilot-instructions.md     ← autosuficiente para Copilot Chat
CLAUDE.md                           ← autosuficiente para Claude Code
```

Elige esta opción si cada plataforma tiene ciclo de vida o equipo de mantenimiento propio.
Volver a esta opción desde la vigente exige justificarlo en el PLAN.

## Criterios de calidad

- Sin duplicación de reglas entre ficheros (DRY)
- Cada fichero es funcional sin necesidad de leer el otro
- El flujo `PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION` está presente en todos los entry points
- Cero referencias `huérfano` (rutas, comandos, módulos o términos de otros proyectos)
- Las secciones específicas de cada plataforma están claramente delimitadas
- Formato: markdown estructurado con secciones etiquetadas
- Los prompts de documentación separan funcional, técnico, ejemplos y revisión final
- La creación y actualización de documentación comparten un único flujo de entrada siempre que sea posible
- `mkdocs.yml` se incluye cuando se creen, muevan o retiren páginas
- No se incluyen instrucciones de generación mediante APIs externas mientras esté excluido

## Formato de salida esperado

### ANÁLISIS
- Tabla categorizada con `fichero:línea` y LOC por categoría
- `% duplicación` baseline (líneas `duplicado` / líneas auditadas; menor es mejor)
- Tabla de reglas documentales comunes y dónde deben vivir

### PLAN
- Estrategia elegida y justificación
- Ficheros resultantes (rutas y responsabilidad de cada uno)
- Riesgos de divergencia futura
- Punto único de entrada para crear o actualizar documentación del proyecto

### AUDIT_PLAN
- Riesgos funcionales
- Riesgos de mantenimiento
- Simplificaciones posibles
- Veredicto: `GO | GO_CONDICIONAL | NO_GO`

### IMPLEMENT
- Contenido completo de cada fichero propuesto

### AUDIT_CODE
- Cambios aplicados vs PLAN aprobado (nada fuera de alcance, nada omitido)
- Cobertura de reglas clave: las reglas canónicas (SOLID, OOP, multibase, políticas por tarea) siguen alcanzables desde cada entry point, sin copiarlas
- Secciones ausentes o incompletas
- Referencias: todas las rutas existen, sin ciclos de «lee primero», `% duplicación` final
- **Verificación documental:** Confirma separación funcional/técnica/ejemplos, actualización de `mkdocs.yml`, uso de Mermaid y regla de no inventar
- **Verificación de APIs externas:** Bloquea instrucciones o ejemplos de generación documental mediante API por estar fuera de alcance temporal
- Veredicto: `APROBADO | APROBADO CON CONDICIONES | RECHAZADO`

### VERSION
- Commit message (Conventional Commits)
- Changelog
- Diff conceptual: qué desaparece, qué se mueve, qué es nuevo
- Rollback: pasos para volver al estado anterior
