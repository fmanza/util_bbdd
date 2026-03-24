# IMPLEMENT

## Approved scope
Implementación acotada de la slice actual de v0.6.1 sobre UX HTML de diagramas, contrato de payload, semántica visible y mejoras locales del renderer/Word, manteniendo fuera de alcance refactor amplio, vistas como nodos del grafo y versionado.

## Files changed
- src/util_bbdd/doc/html_generator.py
- src/util_bbdd/doc/templates/pages/detail.html.j2
- src/util_bbdd/analysis/graphviz_ext.py
- src/util_bbdd/doc/word_generator.py
- src/util_bbdd/doc/database_documentation.py
- src/util_bbdd/analysis/base.py
- src/util_bbdd/analysis/graphviz_ext.py
- tests/unit/test_html_generator_diagrams.py
- tests/unit/test_database_documentation.py
- tests/unit/test_doc_generators_helpers.py
- tests/unit/test_graphviz_ext_helpers.py
- tests/unit/test_analysis_graph_document.py
- .ai/sessions/2026-03-24/04_IMPLEMENT.md
- .ai/sessions/2026-03-24/05_AUDIT_CODE.md
- .ai/sessions/2026-03-24/06_DESIGN.md
- .ai/sessions/2026-03-24/TRACEABILITY.md

## Change summary
- Se formalizó el contrato de diagram_summary en HtmlGenerator con niveles visibles, flags de niveles ocultos y textos de ayuda por dirección.
- Se enriqueció diagram_tabs con direction_help, visible_levels, has_hidden_levels, short_title y aria_label.
- Se añadió UX HTML para diagramas SVG con barra de controles de zoom, ajuste, reset y movimiento por viewport.
- Se incorporó una leyenda visual HTML con significado de colores por dirección, marcadores de cardinalidad y el tipo de relación real actualmente soportado por el renderer.
- Se fijó la política de diagramado de vistas como exclusión explícita en la configuración y en el detalle HTML de vistas.
- Se aclaró el texto del footer Graphviz para explicar el significado de los niveles ocultos por profundidad.
- Se optimizó el flujo local de generación reutilizando GraphDocument entre el resumen Word y la renderización de imágenes cuando ambos ocurren en la misma tabla.
- Se implementó la Slice E compartiendo una única instancia de `GraphvizRelationshipGraphExt` entre Word y HTML cuando la misma ejecución genera ambos formatos con diagramas activos.
- Se evitó recomputar columnas relacionadas por nodo en Graphviz construyendo un lookup por documento antes de pintar los nodos.
- Se estabilizó el tamaño visual de los nodos de tabla limitando columnas visibles, truncando nombres largos con puntos suspensivos y fijando anchos de cabecera/columnas en el label HTML del renderer.
- Se extendió la semántica de Salida oculta y Entrada oculta en Word con texto explicativo, no solo con el contador de niveles no visibles.
- Se ampliaron los tests unitarios de diagramas HTML para cubrir el nuevo payload y el render del detalle.
- Se añadieron tests unitarios específicos para la compartición del generador entre formatos y para el fallback de construcción local en Word/HTML.
- Se añadieron tests unitarios directos para helpers del renderer Graphviz extendido y para la reutilización del documento precalculado en Word.
- Se implementó la Slice F añadiendo tipología visual de nodos en `analysis/base.py` con tres estados iniciales: `entity`, `association` y `hierarchy`.
- Se sustituyó la paleta binaria del renderer por colores pastel por tipología de tabla y se mantuvo el acento de raíz mediante borde reforzado.
- Se refinó la heurística de `association` para reconocer mejor tablas puente con PK compuesta basada en columnas FK, incluso cuando existen columnas adicionales.
- Se amplió la leyenda HTML del detalle para exponer los tipos de tabla realmente soportados por el modelo visual actual: entidad, asociación y jerarquía.
- Se ampliaron los tests de `analysis/base.py` y de helpers Graphviz para cubrir la clasificación visual y la traducción de tipología a color.
- Se ampliaron los tests HTML para cubrir el nuevo bloque de leyenda por tipo de tabla y el contrato enriquecido de `diagram_legend`.
- Se sincronizó la trazabilidad de sesión con el estado real tras la implementación.

## Decisions taken
- Mantener la implementación acotada a tablas y al detalle HTML de diagramas.
- Resolver la navegación visual en HTML sin reescribir el SVG generado por Graphviz.
- Mantener compatibilidad operativa con Word al no romper GraphDocument ni HiddenLevelsSummary.
- Resolver la leyenda en HTML a partir del contrato real actual, sin inventar nuevos tipos de relación no expuestos todavía por analysis.
- Mantener fuera del grafo a las vistas mientras analysis no las modele como nodos reales, pero exponer esa decisión de forma visible y testeable en HTML.
- Resolver la optimización de tiempos de forma local y segura, evitando reconstrucciones redundantes del documento del grafo sin introducir un refactor de analysis.
- Resolver la optimización interformato en la capa de orquestación documental, reutilizando un único generador de grafos cuando Word y HTML comparten la misma corrida.
- Tratar el tamaño fijo de tablas como estabilidad visual del nodo: cap de columnas, truncado de textos y ancho controlado del label HTML.
- Extender la semántica de niveles ocultos a Word en continuidad con HTML y con el footer del SVG.
- Resolver la semántica de color por tipo de tabla en el nivel de análisis, no solo en el renderer, para que cualquier salida futura pueda reutilizar la tipología.

## Tests added/updated
- tests/unit/test_html_generator_diagrams.py
	- validación de payload enriquecido
	- validación de ayudas semánticas de niveles ocultos
	- validación de la leyenda visual de diagramas
	- validación de la política explícita de exclusión de vistas en diagramas
	- validación de controles de navegación HTML
- tests/unit/test_doc_generators_helpers.py
	- validación de la semántica ampliada de niveles ocultos en Word
	- validación de reutilización de GraphDocument precalculado
	- validación de fallback y reutilización del generador opcional en Word y HTML
- tests/unit/test_database_documentation.py
	- validación de compartición de una única instancia del generador entre Word y HTML
	- validación de no construcción anticipada en ejecuciones de un único formato
- tests/unit/test_analysis_graph_document.py
	- validación de clasificación de nodos como entidad, asociación y jerarquía
	- validación de clasificación de tabla puente con PK compuesta basada en FKs aunque existan columnas adicionales
- tests/unit/test_graphviz_ext_helpers.py
	- validación del límite de columnas visibles
	- validación del truncado visual y del aviso de columnas ocultas en nodos Graphviz
	- validación de paleta visual por tipología de tabla
	- validación de acento de raíz mediante borde reforzado
- tests/unit/test_html_generator_diagrams.py
	- validación de `table_type_items` dentro de `diagram_legend`
	- validación de la nota heurística que aclara el carácter aproximado de la tipología visual
	- validación del render de la nueva sección de leyenda en la página detalle

## Validation commands
- get_errors sobre archivos editados: sin errores
- pytest focalizado:
	- tests/unit/test_database_documentation.py
	- tests/unit/test_doc_generators_helpers.py
	- resultado: 23 tests OK y 1 skipped en batería Slice E
	- smoke test funcional de orquestación Word+HTML: 1 instancia compartida construida y reutilizada en ambos formatos
	- validación ejecutada con el entorno `venv` del repo
- pytest focalizado Slice F:
	- tests/unit/test_analysis_graph_document.py
	- tests/unit/test_graphviz_ext_helpers.py
	- resultado: 10 tests OK
- pytest focalizado leyenda HTML + heurística refinada:
	- tests/unit/test_analysis_graph_document.py
	- tests/unit/test_graphviz_ext_helpers.py
	- tests/unit/test_html_generator_diagrams.py
	- resultado: 17 tests OK
- pytest focalizado previo:
	- tests/unit/test_html_generator_diagrams.py
	- tests/unit/test_analysis_graph_document.py
	- tests/unit/test_doc_generators_helpers.py
	- tests/unit/test_graphviz_ext_helpers.py
	- tests/unit/test_print_config_manager.py
	- resultado: 34 tests OK
- ruff check focalizado sobre archivos Python modificados: OK

## Residual risks
- La navegación implementada usa controles sobre el contenedor HTML del object SVG; no ofrece paneo interno nativo dentro del documento SVG embebido.
- La política de vistas queda resuelta para el estado actual del renderer, pero deberá revisarse si analysis incorpora soporte real de vistas en el grafo.
- El renderer sigue exponiendo solo relaciones FK; si se incorporan más tipos reales en analysis habrá que extender la leyenda y los contratos asociados.
- El truncado visual fija mejor el tamaño de los nodos, pero no impone una geometría absoluta a Graphviz cuando el layout global necesita redistribuir espacio.
- La validación funcional de la Slice E depende de que el workspace use el entorno `venv`; se detectó una `.venv` vacía que no sirve como entorno de validación para este repo.
- La tipología visual de tabla sigue siendo heurística; aunque ahora reconoce mejor tablas puente con PK compuesta, algunos esquemas híbridos pueden requerir ajuste posterior.

## Out-of-scope observations
- No se abordó limpieza global de mypy.
- No se actualizó README.md, CHANGELOG.md, pyproject.toml ni documentación de versión.
- No se incorporó soporte de vistas como nodos del grafo; solo se formalizó su exclusión actual.
