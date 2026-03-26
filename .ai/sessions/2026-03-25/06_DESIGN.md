# DESIGN

## Objective
Definir un diseño técnico implementable para v0.6.2 centrado en ajuste visual del renderer de diagramas relacionales, legibilidad de cardinalidades, navegación controlada del SVG desde la propia página HTML y validación del caso de alta densidad, sin mezclar la iniciativa con refactor amplio ni con cierre de versión.

## Design scope
- recalibrar el tamaño visual de las tablas del diagrama hacia un 75 por ciento aproximado del baseline actual
- mejorar la legibilidad de los marcadores de cardinalidad respecto a aristas y nodos relacionados
- reforzar el panning y zoom controlado desde la propia página HTML para diagramas densos
- verificar si la UX actual de tabs por nivel/dirección ya cubre el caso de densidad o si requiere ajuste incremental
- mantener compatibilidad operativa con Word y HTML mientras no exista justificación real para un breaking change adicional

## Out of scope
- reescritura de GraphvizRelationshipGraphExt
- rediseño de GraphDocument o de la semántica multinivel existente
- limpieza global de mypy
- actualización de README, CHANGELOG, pyproject.toml o release notes
- cierre de versión y PR
- creación de una alternativa completa a tabs por nivel sin evidencia de necesidad

## Files affected

### Productive code candidatos
- src/util_bbdd/analysis/graphviz_ext.py
- src/util_bbdd/doc/html_generator.py
- src/util_bbdd/doc/templates/pages/detail.html.j2
- src/util_bbdd/doc/templates/assets o equivalente actual de scripts del visor, si existe separación de assets
- opcional y solo si aporta valor real: src/util_bbdd/doc/print_config_manager.py

### Tests candidatos
- tests/unit/test_graphviz_ext_helpers.py
- tests/unit/test_html_generator_diagrams.py
- opcional: tests/unit/test_doc_generators_helpers.py si el cambio toca inyección de assets, configuración del viewer, salida Word o resumen semántico

## Current contracts verified

### analysis/base.py
- `_split_relations_for_visualization()` ya soporta división paginada del conjunto de relaciones
- el modelo multinivel ya cubre niveles, nodos, aristas y relaciones sin necesidad de ampliarlo para esta slice

### analysis/graphviz_ext.py
- el tamaño del nodo ya se controla mediante constantes y estilos de label HTML
- el renderer ya limita columnas, trunca textos y emite una fila de columnas ocultas
- la cardinalidad ya se expresa mediante `taillabel` y `headlabel`

### doc/html_generator.py
- ya existe payload con `diagram_tabs`, `diagram_summary` y metadatos por dirección/nivel
- ya existe leyenda HTML que documenta cardinalidad y semántica visual actual

### detail.html.j2
- ya existe viewer por panel SVG con tabs por dirección/nivel
- ya existe resumen de niveles visibles y no visibles
- ya existen controles de visor, pero la nueva necesidad exige formalizar el control de pan y zoom como capacidad propia y predecible de la página

## Proposed design decisions

### Decision 1: tratar v0.6.2 como ajuste visual incremental, no como reescritura
Razón:
- el discovery demuestra que la base funcional ya existe
- el gap real es de calibración geométrica y legibilidad
- una reescritura ampliaría alcance sin evidencia suficiente

### Decision 2: reducir el nodo desde el renderer Graphviz, no desde HTML
Acción de diseño:
- recalibrar primero `DEFAULT_TABLE_WIDTH`, `DEFAULT_NAME_COLUMN_WIDTH`, `DEFAULT_TYPE_COLUMN_WIDTH` y los límites de truncado en `graphviz_ext.py`
- mantener el contrato HTML intacto mientras el problema sea puramente de SVG generado

Razón:
- el tamaño del nodo nace en el label HTML de Graphviz, no en la plantilla Jinja
- tocar HTML no reduce el tamaño real del SVG embebido

### Decision 3: definir el 75 por ciento como reducción aproximada del baseline actual, no como constante matemática rígida
Traducción inicial propuesta para SVG no raster:
- `table_width`: 240 -> 180
- `name_column_width`: 160 -> 120
- `type_column_width`: 80 -> 60

Nota:
- estos valores son punto de partida de diseño, no decisión cerrada de implementación
- la validación debe apoyarse en tests de estilos y, si hace falta, en inspección visual manual

### Decision 4: no introducir una alternativa completa a tabs sin antes medir la suficiencia de la UX actual
Acción de diseño:
- conservar tabs por dirección y nivel como baseline funcional
- evaluar solo mejoras incrementales de copy o metadatos si el caso de densidad lo exige

Razón:
- el prompt pide tabs por nivel o mejor alternativa, pero el repo ya ofrece tabs operativas
- sin evidencia de fallo de UX, sustituirlas sería sobrealcance

### Decision 5: separar dos problemas de cardinalidad que hoy están mezclados
Problema A:
- marcador de cardinalidad `1/N/M` por extremo

Problema B:
- texto de dependencia o etiqueta de relación sobre la arista

Acción de diseño:
- estudiar ambos problemas por separado en el renderer
- evitar una solución única si Graphviz trata de forma distinta `headlabel/taillabel` y `xlabel`

Razón:
- el prompt mezcla superposición de marcadores y de texto
- el código actual usa canales distintos para ambos tipos de información

### Decision 6: documentar alternativas de labeling antes de implementar la slice de cardinalidad
Alternativas a revisar en implementación:
- ajustar distancia y tamaño de `headlabel/taillabel`
- mover parte de la información a `labeldistance`, `labelangle` o atributos similares si Graphviz lo soporta de forma estable
- simplificar o acortar `xlabel` cuando el conflicto visual sea el verdadero problema
- reservar una estrategia fallback si Graphviz no permite control fino suficientemente estable

Razón:
- la geometría de labels en Graphviz puede depender del layout final
- conviene diseñar con un plan de salida si la mejora perfecta no es alcanzable solo por atributos de arista

### Decision 7: mantener la configuración actual de paginación y caché
Acción de diseño:
- no abrir cambios nuevos sobre `metadata/cache.py`
- no tocar la lógica de compartición Word/HTML salvo impacto directo demostrado

Razón:
- esa parte ya está cubierta y validada en v0.6.1
- no hay evidencia en el prompt de v0.6.2 que justifique tocarla

### Decision 8: resolver panning y zoom en la capa HTML del viewer, no en el renderer Graphviz
Acción de diseño:
- mantener el SVG generado como artefacto base del renderer
- encapsular el comportamiento de navegación en la página HTML mediante controles propios del viewer
- evaluar librería externa solo si la solución actual o una solución ligera nativa no cubre correctamente zoom, pan, reset y fit

Razón:
- el problema nuevo es de interacción del usuario con el SVG embebido, no de generación del grafo
- desplazar esta lógica al renderer mezclaría responsabilidades y haría más frágil la salida compartida con Word

### Decision 9: priorizar una solución progresiva para el viewer
Alternativas de diseño:
- opción A: fortalecer el visor actual con JavaScript propio y transformaciones controladas del SVG
- opción B: integrar `svg-pan-zoom` o librería equivalente si aporta estabilidad real y reduce complejidad accidental
- opción C: estrategia híbrida, manteniendo controles propios de UI sobre una librería encapsulada

Criterio de elección:
- compatibilidad con el HTML estático generado
- bajo acoplamiento con la plantilla Jinja
- no degradar accesibilidad, rendimiento ni portabilidad offline de la documentación generada
- capacidad de exponer acciones previsibles: zoom in, zoom out, fit, reset y pan dirigido

## Implementation plan

### Slice A: reducción de tamaño del nodo
Cambios previstos:
- src/util_bbdd/analysis/graphviz_ext.py
- tests/unit/test_graphviz_ext_helpers.py

Acciones:
- recalibrar anchos y límites de truncado para SVG no raster
- mantener legibilidad mínima de títulos, nombres de columnas y tipos
- validar que el aviso de columnas ocultas siga visible y coherente

Resultado esperado:
- nodos visualmente más compactos sin romper el contrato actual del renderer

### Slice B: reposicionamiento de cardinalidades
Cambios previstos:
- src/util_bbdd/analysis/graphviz_ext.py
- tests/unit/test_graphviz_ext_helpers.py
- opcional: tests/unit/test_html_generator_diagrams.py si cambia el texto explicativo o la leyenda

Acciones:
- revisar el uso actual de `taillabel`, `headlabel` y `xlabel`
- proponer una configuración de labels más legible cerca del nodo relacionado
- documentar límites del enfoque si Graphviz no ofrece control fino suficiente

Resultado esperado:
- menor superposición visual entre marcadores, aristas y etiquetas relacionales

### Slice C: revisión de UX HTML por densidad
Cambios previstos:
- src/util_bbdd/doc/html_generator.py
- src/util_bbdd/doc/templates/pages/detail.html.j2
- tests/unit/test_html_generator_diagrams.py

Acciones:
- mantener el modelo de tabs actual
- introducir solo mejoras incrementales de copy, ayudas o metadata si se detecta necesidad clara

Resultado esperado:
- continuidad con la UX existente y coste de cambio bajo

### Slice D: panning y zoom controlado por la propia página
Cambios previstos:
- src/util_bbdd/doc/html_generator.py
- src/util_bbdd/doc/templates/pages/detail.html.j2
- assets/scripts del visor si el proyecto ya separa JavaScript reutilizable
- tests/unit/test_html_generator_diagrams.py

Acciones:
- formalizar el contrato de viewer para zoom, pan, fit y reset desde la propia página
- decidir entre solución nativa ligera o integración encapsulada de `svg-pan-zoom` o similar
- asegurar que la navegación no interfiere con tabs, leyenda ni lectura del diagrama
- preservar funcionamiento offline del HTML generado

Resultado esperado:
- navegación más intuitiva en diagramas complejos sin alterar el contrato del renderer Graphviz
- control consistente del SVG desde la propia página, independientemente de la densidad del nivel mostrado

## Refactor plan

### Refactor autorizado en esta fase
- micro-refactor local en `graphviz_ext.py` si mejora legibilidad de constantes o helpers de estilos
- separación mínima de helpers de geometry/labels si reduce complejidad sin cambiar contratos

### Refactor no autorizado en esta fase
- mover clases entre módulos
- rediseñar analysis/base.py
- rehacer el pipeline HTML/Word
- abrir una nueva arquitectura de renderers

## PR action plan

### PR 1 recomendado
Objetivo:
- reducción de tamaño de nodo y validación asociada

Incluye:
- `graphviz_ext.py`
- `test_graphviz_ext_helpers.py`

No incluye:
- cambios HTML salvo impacto directo
- rediseño de tabs o payloads

### PR 2 recomendado
Objetivo:
- ajuste de cardinalidades y evaluación de etiquetas de arista

Incluye:
- `graphviz_ext.py`
- tests unitarios focalizados
- documentación de riesgos residuales si Graphviz impone límites geométricos

### PR 3 opcional
Objetivo:
- mejora incremental de UX HTML por densidad, solo si la revisión demuestra que la UI actual no basta

### PR 4 recomendado si Slice D introduce dependencia nueva o lógica propia relevante
Objetivo:
- encapsular panning y zoom de página con contrato estable de viewer

Incluye:
- plantilla HTML del detalle
- posible asset JS reutilizable del visor
- tests de payload o rendering necesarios

No incluye:
- cambios en generación Graphviz salvo ajustes mínimos de integración
- rediseño del modelo de datos del documento

## Test strategy

### Unit tests obligatorios
- `test_graphviz_ext_helpers.py`
  - validar nuevos anchos y límites del label
  - validar persistencia del aviso de columnas ocultas
  - validar que la solución de cardinalidad no rompe helpers actuales

- `test_html_generator_diagrams.py`
  - solo si cambia payload, copy o comportamiento visible en detalle HTML
  - validar presencia de controles y hooks del viewer si se implementa Slice D

- pruebas de integración ligera del viewer HTML
  - comprobar que el HTML generado expone un contenedor navegable
  - comprobar que el script o configuración del viewer se emite una sola vez por página

### Regression checks sugeridas para implementación
- `pytest tests/unit/test_graphviz_ext_helpers.py -q`
- `pytest tests/unit/test_html_generator_diagrams.py -q` si aplica
- `ruff check src tests`

## Security and performance review

### Security
- no se prevén nuevos riesgos de seguridad por esta slice visual
- mantener escape HTML/SVG actual intacto

### Performance
- la reducción de tamaño del nodo no debería afectar negativamente al pipeline
- la slice de cardinalidad no debe introducir nuevas rondas de consulta ni cachés adicionales
- el viewer de pan y zoom no debe introducir una librería pesada sin beneficio claro ni bloquear la apertura offline del HTML

## Risks
- compactar demasiado el nodo y degradar la lectura de columnas relevantes
- confiar en atributos de Graphviz que no se comporten igual en todos los layouts
- introducir cambios HTML innecesarios cuando el problema principal reside en el SVG generado
- acoplar la UX del visor a una librería externa difícil de mantener o incompatible con documentación offline
- duplicar controles de viewer si ya existe lógica parcial y no se consolida en un único contrato

## Open decisions
- si la reducción al 75 por ciento debe aplicarse también al modo raster o solo al baseline SVG/HTML
- si el texto relacional debe simplificarse en algunos casos además de mover cardinalidades
- si la UX actual de tabs necesita realmente una mejora en v0.6.2 o puede permanecer estable
- si el viewer debe resolverse con JavaScript propio, con `svg-pan-zoom` o con una abstracción híbrida
- si el panning libre por arrastre debe convivir con botones dirigidos actuales o sustituir parte de ellos

## Recommendation
- ejecutar primero una implementación mínima de Slice A sobre `graphviz_ext.py`
- después abordar Slice B con criterio experimental controlado y tests focalizados
- dejar Slice C solo si, tras revisar resultados, sigue habiendo un problema real de lectura en HTML
- abordar Slice D en paralelo a Slice C solo en la capa de viewer, manteniendo aislada la responsabilidad respecto al renderer
