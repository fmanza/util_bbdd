# DISCOVERY

## Objective
Contrastar docs\v0.6.1\crear_prompt.md contra el código real del repositorio y contra SchemaSpy para convertir la iniciativa en un diseño implementable sin mezclar todavía feature y refactor.

## Workspace validation
- tests: OK
  - comando ejecutado: pytest -q
  - resultado: 525 passed, 1 skipped
- lint: OK
  - comando ejecutado: ruff check .
  - resultado: All checks passed
- type-check global: NOK por deuda histórica previa
  - comando ejecutado: mypy src
  - resultado: 110 errores en 37 archivos
  - interpretación: no sirve como gate de aceptación de esta iniciativa porque el baseline ya está roto fuera del alcance de v0.6.1

## Internal benchmark

### analysis/base.py
- Ya existe un modelo intermedio suficientemente expresivo para diagramas multinivel.
- Entidades confirmadas:
  - GraphDocument
  - GraphNode
  - GraphEdge
  - GraphLevel
  - HiddenLevelsSummary
- El concepto de niveles ocultos ya está modelado y no es una idea nueva del prompt.

### analysis/graphviz_ext.py
- Ya existe render Graphviz evolucionado para:
  - profundidad configurable
  - dirección incoming/outgoing/both
  - modos de columnas
  - cardinalidad y nombres de constraints
  - generación por niveles
  - resumen de niveles ocultos
- El texto actual del pie usa semántica concreta:
  - Salida oculta = outgoing_hidden_levels
  - Entrada oculta = incoming_hidden_levels

### doc/html_generator.py
- La salida HTML ya soporta:
  - generación SVG al vuelo
  - pestañas por dirección y nivel
  - inyección de enlaces clicables en nodos SVG
  - resumen de niveles visibles/no visibles
- La feature v0.6.1 no parte desde cero; es una evolución visual y semántica sobre una base funcional ya existente.

### doc/templates/pages/detail.html.j2
- Ya existen:
  - grupos por dirección
  - tabs por nivel
  - render object de SVG
  - resumen de profundidad visible y niveles no visibles
- Falta todavía interacción rica de navegación visual dentro del SVG, por ejemplo zoom/pan controlado por la propia página.

## External benchmark: SchemaSpy

### Observed behavior
- SchemaSpy organiza diagramas en pestañas por grado de separación.
- Distingue relaciones reales e implied.
- Usa imágenes o SVG embebidos con mapas/enlaces clicables.
- Expone una nota explícita cuando solo existen relaciones implied.
- En el detalle de tabla, el benchmark principal es estructura de navegación y claridad de variantes, no interacción avanzada.

### Relevant contrast against util_bbdd
- util_bbdd ya supera a SchemaSpy en una dimensión: niveles separados por dirección y resumen explícito de niveles ocultos.
- SchemaSpy ofrece nomenclatura más directa para variantes del diagrama:
  - One
  - Two degrees
  - Compact
  - Large
  - Compact Implied
  - Large Implied
- SchemaSpy no aporta evidencia de zoom/pan nativo en página; el prompt v0.6.1 va más allá del benchmark en ese punto.
- SchemaSpy sí confirma como buena práctica:
  - tabs claras
  - mensajes informativos cuando el tipo de relación cambia
  - separación de variantes visuales por complejidad

## Functional conclusions

### 1. La iniciativa es evolutiva, no greenfield
La base de análisis y de render HTML ya existe. El trabajo correcto es endurecer contratos y mejorar UX/semántica, no rehacer la arquitectura completa sin evidencia adicional.

### 2. “Salida oculta” ya tiene significado verificable
No es un concepto abierto: representa niveles salientes que existen en el grafo pero quedan fuera de la profundidad visible configurada.

### 3. El gap principal está en UX y contratos de salida
Los cambios más justificables por evidencia son:
- etiquetado más claro de tabs y resúmenes
- leyenda más explícita para cardinalidad y significado de colores/símbolos
- soporte de zoom/pan en HTML para SVG ya generados
- política clara de columnas visibles
- aclarar cómo se representan tablas vs vistas

### 4. No hay base todavía para un refactor amplio
La deuda de mypy y la existencia de cambios locales previos hacen inconveniente mezclar ahora una reorganización estructural con la feature.

## Proposed implementation slice

### Slice 1: HTML UX
- Añadir controles de zoom, reset y pan para SVG en detail.html.j2 y assets asociados.
- Mantener compatibilidad con SVG actual generado por html_generator.py.

### Slice 2: Semántica visible
- Renombrar textos de resumen y tabs para hacer evidente:
  - dirección
  - nivel visible
  - niveles no visibles
- Incorporar leyenda de cardinalidad si el SVG o el pie actual no la hace suficiente.

### Slice 3: Contrato de diagram_summary
- Fijar el payload esperado por la plantilla HTML.
- Cubrir con tests la semántica de hidden_levels y total_levels.

### Slice 4: Vistas
- Decidir explícitamente si:
  - no participan en diagramas
  - participan siempre
  - participan por flag
- No implementar sin esta decisión porque afecta contratos públicos y documentación.

## Risks
- Mezclar la mejora visual con refactor del generador Graphviz.
- Intentar “arreglar” mypy global como parte de esta feature.
- Cambiar semántica textual de hidden levels sin test de regresión documental.

## Verdict
GO_CONDICIONAL para diseño detallado e implementación acotada.

## Conditions to move to IMPLEMENT
- cerrar política sobre vistas
- definir el contrato final de diagram_summary y diagram_tabs
- mantener fuera de alcance la limpieza global de mypy
- no tocar cambios locales ajenos ya presentes en analysis/graphviz_ext.py
