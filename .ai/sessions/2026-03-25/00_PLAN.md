# PLAN

## Request summary
Aplicar la metodología externa al documento docs\v0.6.2\crear_prompt.md con fecha 2026-03-25, sin arrancar todavía la implementación de la nueva funcionalidad.

## Goal
Convertir una petición amplia y mezclada en un plan ejecutable, auditable y compatible con el estado actual del repositorio.

## Scope in
- Saneado metodológico de la solicitud v0.6.2.
- Auditoría de configuración del repositorio respecto al marco externo.
- Identificación preliminar de rutas afectadas.
- Detección de riesgos funcionales, técnicos y de versionado.
- Preparación de artefactos de sesión para continuidad.

## Scope out
- Implementación de código en src/util_bbdd.
- Ejecución de refactors o cambios arquitectónicos reales.
- Actualización de README.md, CHANGELOG.md, pyproject.toml o release notes.
- Creación de PR y cierre de versión.

## Current-state observations
- El usuario ha confirmado que la versión correcta de trabajo es v0.6.2, por lo que cualquier referencia residual a 0.6.1 en el prompt debe tratarse como arrastre documental.
- El objetivo funcional se concentra en render Graphviz/HTML: tamaño visual de tablas, cardinalidades y manejo de relaciones por nivel.
- La petición mezcla visualización, posibles breaking changes, arquitectura, caché, documentación, migración y versionado final.
- El repositorio ya dispone de base metodológica, tareas y contexto suficientes para planificar sin necesidad de tocar setup de editor.
- El árbol git contiene contenidos no versionados en docs/ que deben preservarse durante esta sesión.

## Proposed design

### 1. Tratar v0.6.2 como flujo `new_feature` estricto
- Mantener la clasificación principal como new_feature.
- Separar explícitamente cualquier necesidad de refactor a un flujo posterior si se confirma.

### 2. Descomponer la iniciativa antes de IMPLEMENT
- Slice A: reducción y estandarización de tamaño visual de nodos de tabla.
- Slice B: reposicionamiento y semántica visual de cardinalidades.
- Slice C: tratamiento de densidad por nivel mediante pestañas o alternativa equivalente.
- Slice D: documentación/migración/versionado solo después de validar slices funcionales.

### 3. Contrastar el prompt con el estado real del repositorio
- Verificar si las capacidades de tabs por nivel ya existen parcialmente.
- Verificar si el problema de cardinalidad es de renderer, de layout Graphviz o de plantilla HTML.
- Tratar la referencia residual a 0.6.1 como inconsistencia documental del prompt y no como objetivo real de versionado.

## Files impacted
- docs/v0.6.2/crear_prompt.md como entrada funcional.
- src/util_bbdd/analysis/base.py
- src/util_bbdd/analysis/graphviz_ext.py
- src/util_bbdd/doc/
- tests/ relacionados con analysis y doc
- .ai/sessions/2026-03-25/*

## Test plan
- En esta sesión no aplica ejecución de tests funcionales, porque no se ha autorizado IMPLEMENT.
- Para una siguiente sesión de implementación:
  - tests unitarios de layout de nodos
  - tests unitarios de cardinalidad renderizada
  - tests documentales HTML/Word para tabs por nivel y payload asociado

## Risks
- Riesgo alto de sobrealcance si se intenta ejecutar visualización, arquitectura, caché y versionado en una sola pasada.
- Riesgo alto de violar la policy new_feature si se introduce refactor estructural durante IMPLEMENT.
- Riesgo medio de confusión documental por referencias residuales del prompt no alineadas con la versión real v0.6.2.
- Riesgo medio de alterar la legibilidad del renderer si se recolocan cardinalidades sin criterio geométrico verificable.

## Open questions
- ¿La mejora de cardinalidad debe resolverse en el renderer Graphviz, en el modelo intermedio o en el consumo HTML?
- ¿La alternativa a pestañas por nivel debe ser visual, contractual o ambas?
- ¿Qué baseline visual se tomará para afirmar que el nodo al 75% sigue siendo legible en SVG, HTML y Word?

## Recommendation
Mantener esta sesión como fase de preparación metodológica y usar una siguiente sesión para discovery técnico acotado sobre layout de nodos, cardinalidad y paginación visual por niveles antes de cualquier implementación.
