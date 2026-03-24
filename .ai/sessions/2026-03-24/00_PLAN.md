# PLAN

## Request summary
Preparar la iniciativa v0.6.1 a partir de docs\v0.6.1\crear_prompt.md aplicando la metodología leída hoy, sin entrar aún en implementación funcional del cambio.

## Goal
Convertir una petición amplia y mezclada en un plan ejecutable, auditable y compatible con el repositorio real.

## Scope in
- Saneado de la petición.
- Auditoría de configuración metodológica del repositorio.
- Identificación de rutas afectadas probables.
- Descomposición del alcance funcional y técnico.
- Benchmark mínimo contra SchemaSpy y contra el código real de analysis/doc.
- Definición de riesgos, dependencias y estrategia de pruebas.
- Preparación de artefactos de sesión para continuidad.

## Scope out
- Implementación de código en src/util_bbdd.
- Actualización de README.md, CHANGELOG.md, pyproject.toml o documentación viva.
- Creación de PR y etiquetado en GitHub.

## Current-state observations
- El objetivo funcional apunta a una mejora importante del subsistema de diagramas relacionales y de la salida HTML.
- La solicitud mezcla new_feature con refactor arquitectónico, optimización, documentación, migración y cierre de versión.
- El repositorio ya dispone de contexto suficiente para planificar, pero no de autorización limpia para implementar bajo el policy new_feature.
- Existen cambios locales previos en analysis que obligan a mantener separación estricta de esta sesión.
- El workspace pasa tests y lint, pero mypy global ya parte roto fuera del alcance de la iniciativa.
- La salida HTML actual ya soporta SVG, pestañas por nivel/dirección y enlaces clicables en nodos.
- El concepto de niveles ocultos ya existe y está implementado en analysis/base.py y analysis/graphviz_ext.py.

## Proposed design

### 1. Dividir la iniciativa en tracks controlados
- Track A: discovery y benchmark visual/funcional contra SchemaSpy.
- Track B: diseño funcional de v0.6.1 para graphviz, cardinalidad, tablas y HTML.
- Track C: decisión de arquitectura sobre refactor permitido o flujo separado.
- Track D: implementación acotada una vez exista veredicto GO.
- Track E: documentación, migración y cierre de versión.

### 2. Mantener la clasificación principal como new_feature, con condición explícita
La feature no puede arrancar en IMPLEMENT mientras el alcance siga incluyendo refactor estructural no acotado. Primero debe decidirse si ese refactor es:
- prerequisito de arquitectura autorizado dentro de alcance, o
- flujo separado de refactor previo.

### 3. Rutas afectadas probables
- src/util_bbdd/analysis/base.py
- src/util_bbdd/analysis/graphviz_ext.py
- src/util_bbdd/doc/
- tests/ relacionados con analysis y doc
- docs funcionales y de migración de v0.6.1

## Files impacted
- .ai/sessions/2026-03-24/00_REQUEST.md
- .ai/sessions/2026-03-24/00_CONTEXT_SNAPSHOT.md
- .ai/sessions/2026-03-24/01_CONFIGURATION_AUDIT.md
- .ai/sessions/2026-03-24/00_PLAN.md
- .ai/sessions/2026-03-24/02_AUDIT_PLAN.md
- .ai/sessions/2026-03-24/TRACEABILITY.md

## Test plan
- En esta sesión no aplica ejecución de tests funcionales porque no hay cambios de código productivo.
- Para la fase futura de implementación: tests unitarios de análisis multinivel, render, cardinalidad, HTML y compatibilidad con generación documental.
- Para la fase futura de gobierno: validar comandos estándar de lint, format y test una vez exista tasks.json o convención equivalente.

## Risks
- Riesgo alto de sobrealcance si se intenta ejecutar la iniciativa completa como una sola feature.
- Riesgo alto de violar la policy new_feature si se refactoriza sin autorización explícita de arquitectura.
- Riesgo medio de interferencia con cambios locales existentes en analysis.
- Riesgo medio de falta de trazabilidad si no se separan investigación, diseño, implementación y cierre de versión.
- Riesgo medio de dependencia externa si SchemaSpy se toma como referencia sin acotar qué se adopta y qué no.
- Riesgo medio de intentar usar mypy global como criterio de aceptación cuando el baseline ya está degradado.

## Open questions
- ¿Las vistas deben renderizarse siempre, nunca o mediante política configurable?
- ¿El cambio arquitectónico necesario se autoriza dentro del flujo de feature o se forzará una sesión de refactor separada?
- ¿Qué nivel de breaking change se acepta en la API pública de analysis y doc para v0.6.1?

## Recommendation
Mantener esta sesión como fase de preparación y discovery, y pasar a diseño detallado de v0.6.1 con alcance acotado sobre HTML, semántica visual y contratos de payload antes de implementar.
