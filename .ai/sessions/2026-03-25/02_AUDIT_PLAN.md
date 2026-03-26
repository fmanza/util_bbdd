# AUDIT_PLAN

## Plan under review
Plan de preparación metodológica y descomposición de la iniciativa v0.6.2 derivado de docs\v0.6.2\crear_prompt.md.

## Code reality check
- Las rutas candidatas del prompt existen en el repositorio: analysis, doc y tests.
- El repositorio dispone ya de configuración metodológica persistente y trazabilidad por sesiones.
- Existen tareas estándar de lint, test, type-check y build ya preparadas en VS Code.
- El objetivo del prompt apunta a problemas de representación visual que requieren contraste con el código real antes de autorizar implementación.

## Mismatches

### 1. El prompt mezcla intención funcional y cierre de versión
La petición no se limita a una mejora visual. También incorpora breaking changes, migración documental, actualización de arquitectura y cierre de versión.

### 2. Hay una inconsistencia explícita de versionado
El documento está bajo docs\v0.6.2\crear_prompt.md, pero en requisitos arrastra una referencia a crear la versión 0.6.1. Tras aclaración del usuario, esa referencia debe interpretarse como inconsistencia documental y no como objetivo real.

### 3. El alcance técnico no está todavía contrastado con el renderer real
Antes de IMPLEMENT falta verificar dónde reside exactamente cada problema:
- tamaño de tabla
- posición de cardinalidades
- densidad por nivel

## Missing evidence
- Evidencia directa del estado actual de graphviz_ext.py y html_generator.py respecto a cardinalidades y tabs por nivel.
- Confirmación de contratos públicos impactados por la propuesta de breaking change.
- Criterio de aceptación para la nueva geometría visual de tablas y etiquetas.

## Risks

### Riesgos funcionales
- degradar la legibilidad de los diagramas al recolocar cardinalidades sin un diseño probado.
- alterar el comportamiento documental actual sin delimitar el contrato esperado de Word y HTML.

### Riesgos técnicos
- mezclar feature y refactor en el mismo lote.
- arrastrar decisiones de versión desde texto obsoleto del prompt y contaminar README, CHANGELOG o pyproject en una fase temprana.
- introducir cambios visuales grandes sin baseline de tests o capturas comparables.

### Riesgos de seguridad
- no se observan riesgos críticos en esta fase metodológica.
- riesgo bajo futuro de introducir HTML/SVG menos legible o con etiquetas superpuestas si no se valida la solución en varios casos.

## Conditions
- Mantener fijado que la versión correcta de la iniciativa es v0.6.2.
- Abrir una fase posterior de discovery técnico acotado al renderer y a los payloads HTML/Word.
- Mantener fuera de alcance en esta sesión cualquier implementación o refactorización real.
- Tratar el versionado y la documentación pública como fase posterior al bloque funcional.

## Verdict
GO_CONDICIONAL

## Authorized scope
- Sí autorizado: preparación metodológica, auditoría de configuración, saneado del prompt y planificación de continuidad.
- No autorizado todavía: implementación funcional, refactor estructural, migración documental final y cierre de versión.
