# AUDIT_PLAN

## Plan under review
Plan de preparación metodológica y descomposición de la iniciativa v0.6.1 derivado de docs\v0.6.1\crear_prompt.md.

## Code reality check
- Las rutas candidatas del prompt existen en el repositorio.
- El repositorio sí contiene analysis, doc, metadata/cache y tests.
- La configuración metodológica de repositorio existe, pero no cubre por sí sola la normalización completa del paquete externo.
- Hay cambios locales no integrados en graphviz_ext.py, por lo que cualquier implementación inmediata aumentaría el riesgo de mezcla de trabajo.

## Mismatches detectados

### 1. La petición no está acotada a una sola intención
El documento de entrada mezcla:
- nueva funcionalidad
- refactorización arquitectónica
- optimización de rendimiento
- migración/documentación
- cierre de versión y PR

Esto contradice el principio metodológico de una intención por fase y la policy new_feature sin refactor.

### 2. La etiqueta new_feature no basta para autorizar implementación inmediata
La propia petición asume cambios de responsabilidad única, arquitectura SOLID, reorganización de módulos y eliminación de compatibilidad hacia atrás.

Esto requiere decisión explícita de arquitectura antes de IMPLEMENT.

### 3. Falta evidencia externa todavía no recopilada
El benchmark mínimo contra SchemaSpy ya se ha realizado, pero no justifica por sí mismo un refactor amplio.

La evidencia obtenida sí permite tomar decisiones de UX y semántica visibles, especialmente en tabs, variantes de diagrama y mensajes explicativos.

### 4. El cierre de versión está prematuramente mezclado con la definición del cambio
Actualizar README, CHANGELOG, arquitectura, runtime y PR pertenece a fases posteriores, no al arranque del trabajo.

## Missing evidence
- Inventario exacto de contratos públicos afectados en analysis y doc.
- Criterio aprobado sobre vistas y sobre compatibilidad rota en v0.6.1.

## Evidence collected after audit start
- SchemaSpy confirma como baseline útil:
	- tabs por grado/variante
	- separación entre relaciones reales e implied
	- mapas o SVG con enlaces clicables
	- mensajes informativos explícitos cuando cambia el tipo de relación
- El código real del repositorio confirma que ya existen:
	- GraphDocument y HiddenLevelsSummary en analysis/base.py
	- resumen de hidden levels y textos de pie en analysis/graphviz_ext.py
	- pestañas HTML por dirección/nivel en doc/html_generator.py y detail.html.j2
- El workspace actual confirma:
	- tests OK
	- lint OK
	- mypy global no limpio por deuda histórica

## Risks

### Riesgos funcionales
- romper generación documental sin especificación cerrada de compatibilidad
- introducir una semántica ambigua para niveles, vistas y cardinalidad

### Riesgos técnicos
- mezclar feature y refactor en el mismo lote
- pisar cambios locales existentes en analysis
- ampliar alcance hasta documentación y versionado sin diseño validado
- intentar usar la limpieza global de mypy como condición de salida de la feature

### Riesgos de seguridad
- no se observan hallazgos críticos en esta fase documental
- riesgo bajo de introducir HTML/SVG no escapado en fases futuras si se amplían etiquetas visuales sin validación

## Conditions
- Separar la siguiente sesión en discovery/diseño antes de implementación.
- Mantener fuera de alcance cualquier cambio de código hasta resolver la decisión feature vs refactor prerequisito.
- Mantener la trazabilidad en .ai/sessions/2026-03-24 como fuente de arranque de v0.6.1.
- Tratar el baseline de mypy como deuda preexistente y no como regresión de la iniciativa.
- Acotar la primera implementación a UX HTML, semántica visible y contratos de payload del diagrama.

## Verdict
GO_CONDICIONAL

## Authorized scope
- Sí autorizado: preparación metodológica, auditoría de configuración, saneado de la petición, benchmark mínimo y diseño detallado acotado.
- No autorizado todavía: implementación funcional, refactor estructural, migración documental final y cierre de versión.
