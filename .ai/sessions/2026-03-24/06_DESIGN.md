# DESIGN

## Objective
Definir un diseño técnico implementable para v0.6.1 centrado en UX HTML de diagramas, semántica visible y contratos de payload, sin mezclar todavía la feature con un refactor amplio del subsistema analysis.

## Design scope
- mejorar la experiencia visual del detalle HTML de tablas con diagramas SVG
- aclarar la semántica de niveles visibles y niveles ocultos
- formalizar el contrato de datos entre analysis, doc/html y plantillas
- conservar la capacidad actual de generar diagramas paginados
- preservar compatibilidad operativa con Word mientras no se apruebe un breaking change explícito sobre ese canal

## Out of scope
- limpieza global de mypy
- reorganización arquitectónica amplia de src/util_bbdd/analysis
- reescritura de GraphvizRelationshipGraphExt
- actualización de README, CHANGELOG, pyproject.toml o versión
- creación de PR y etiquetado

## Files affected

### Productive code
- src/util_bbdd/analysis/base.py
- src/util_bbdd/analysis/graphviz_ext.py
- src/util_bbdd/doc/html_generator.py
- src/util_bbdd/doc/templates/pages/detail.html.j2
- src/util_bbdd/doc/word_generator.py
- opcional para assets HTML: src/util_bbdd/doc/data/html_assets/

### Tests
- tests/unit/test_analysis_graph_document.py
- tests/unit/test_html_generator_diagrams.py
- tests/unit/test_doc_generators_helpers.py
- opcional si se separa lógica de payload: nuevo test unitario específico del contrato de diagram summary

## Current contracts verified

### analysis/base.py
- GraphDocument ya expone:
  - root_table
  - nodes
  - levels
  - edges
  - relations
  - tables
  - max_depth
  - direction
  - hidden_levels
  - total_incoming_levels
  - total_outgoing_levels
- HiddenLevelsSummary ya expone:
  - incoming_hidden_levels
  - outgoing_hidden_levels

### analysis/graphviz_ext.py
- generate_graphviz_level_graphs_ext ya devuelve:
  - summary
  - outgoing
  - incoming
- summary ya contiene:
  - root_table
  - max_depth
  - total_outgoing_levels
  - total_incoming_levels
  - hidden_outgoing_levels
  - hidden_incoming_levels
- cada item de outgoing/incoming ya contiene:
  - depth
  - path
  - title

### doc/html_generator.py
- _build_diagram_tab_payload transforma summary y grupos en:
  - diagram_tabs
  - diagram_paths
  - diagram_summary
- la plantilla HTML consume hoy:
  - entity.diagram_summary.max_depth
  - entity.diagram_summary.total_outgoing_levels
  - entity.diagram_summary.total_incoming_levels
  - group.direction_label
  - group.total_levels
  - group.hidden_levels
  - item.title
  - item.path

### doc/word_generator.py
- ya existe resumen textual basado en hidden levels
- esto obliga a no romper la semántica de GraphDocument ni de HiddenLevelsSummary en la primera slice

## Proposed design decisions

### Decision 1: mantener GraphDocument como contrato base
No introducir un nuevo modelo intermedio en esta fase.

Razón:
- ya existe cobertura de tests
- ya es consumido por más de un renderer
- cambiarlo ahora ampliaría innecesariamente el alcance

### Decision 2: formalizar diagram_summary como contrato estable de salida HTML
En lugar de dejar summary como un dict implícito, la implementación debe tratarlo como un contrato estable con estas claves mínimas:
- root_table: str
- max_depth: int
- total_outgoing_levels: int
- total_incoming_levels: int
- hidden_outgoing_levels: int
- hidden_incoming_levels: int
- visible_outgoing_levels: int
- visible_incoming_levels: int
- has_hidden_outgoing_levels: bool
- has_hidden_incoming_levels: bool
- has_any_hidden_levels: bool

Razón:
- la plantilla necesita banderas explícitas para UX sin recomputar lógica
- simplifica testeo y evita duplicidad entre plantilla, HTML generator y Word generator

### Decision 3: enriquecer diagram_tabs sin romper el consumo actual
Cada grupo debe evolucionar hacia este payload:
- group_id: str
- direction: outgoing | incoming
- direction_label: str
- direction_help: str
- total_levels: int
- visible_levels: int
- hidden_levels: int
- has_hidden_levels: bool
- items: list

Cada item debe evolucionar hacia:
- tab_id: str
- title: str
- short_title: str
- depth: int
- path: str
- direction: outgoing | incoming
- aria_label: str

Razón:
- permite títulos visibles cortos y accesibilidad correcta
- evita construir frases en la plantilla

### Decision 4: conservar nomenclatura funcional en español, mejorar el texto explicativo
No eliminar los conceptos “Salida” y “Entrada”.

Sí cambiar:
- “Salida oculta” por texto explicativo en resumen/tooltip
- “Entrada oculta” por texto explicativo en resumen/tooltip

Texto funcional propuesto:
- Salida oculta: niveles de tablas hijas o dependientes existentes pero no mostrados por el límite de profundidad visible
- Entrada oculta: niveles de tablas padre o referenciadoras existentes pero no mostrados por el límite de profundidad visible

Razón:
- mantiene continuidad con el código y con Word
- elimina ambigüedad para el usuario final

### Decision 5: primera slice solo para tablas, no para vistas
Decisión implementada:
- las vistas no participan en el nuevo diagrama enriquecido en la implementación actual

Razón:
- el prompt ya reconoce que pueden degradar la legibilidad
- afecta modelo, filtros y documentación
- no es necesario para validar UX ni contrato del payload

Consecuencia:
- la política actual queda fijada como exclusión explícita de vistas en el flujo de diagramas
- el detalle HTML de vistas debe mostrar un aviso claro explicando que la vista se documenta, pero no participa en el grafo relacional actual
- una slice posterior podrá ampliar esta política solo si analysis modela vistas como nodos reales del grafo

### Decision 6: zoom/pan en HTML, no en Graphviz
Implementar interacción visual en el contenedor HTML del SVG embebido, no modificando el layout generado por Graphviz.

Controles mínimos:
- ampliar
- reducir
- reset
- ajuste al contenedor
- paneo por arrastre

Razón:
- reduce riesgo sobre analysis
- desacopla UX de la generación del SVG
- respeta el benchmark y mejora la usabilidad real

### Decision 7: limitar columnas por nodo sin romper la generación actual
Mantener la limitación actual en GraphvizRelationshipGraphExt, pero hacer explícito en la UI cuando existan columnas truncadas.

Contrato propuesto a futuro por nodo:
- visible_columns_count
- total_columns_count
- is_truncated

Nota:
- esta parte solo entra en implementación si ya existe un punto claro donde el renderer conoce ambas cantidades sin coste alto
- si no existe, se deja para una segunda slice del renderer

Estado:
- implementado en esta sesión como cap de columnas visibles por nodo, aviso explícito de columnas ocultas y truncado de textos largos para estabilizar el tamaño visual del nodo

### Decision 8: optimización local sin refactor de analysis
Decisión implementada:
- reutilizar GraphDocument cuando Word necesita construir resumen y render del diagrama de una misma tabla
- evitar recomputar columnas relacionadas por nodo creando un lookup por documento antes de dibujar nodos

Razón:
- reduce trabajo redundante sin alterar el contrato base ni mezclar la feature con una reorganización amplia del subsistema analysis

### Decision 9: extender la semántica de niveles ocultos a Word
Decisión implementada:
- Word mantiene el resumen cuantitativo y añade texto explicativo para Salida oculta y Entrada oculta

Razón:
- alinea la comprensión funcional entre HTML, SVG y Word sin cambiar GraphDocument

## Implementation plan

### Slice A: formalizar payload del detalle HTML
Cambios previstos:
- src/util_bbdd/doc/html_generator.py

Acciones:
- enriquecer summary antes de entregarlo a la plantilla
- enriquecer diagram_tabs con visible_levels, has_hidden_levels, direction_help y aria_label
- mantener las claves antiguas mientras dure la transición de plantilla/tests

Resultado esperado:
- contrato claro y testeable sin tocar todavía la lógica de render Graphviz

### Slice B: mejorar UX del detalle HTML
Cambios previstos:
- src/util_bbdd/doc/templates/pages/detail.html.j2
- assets HTML si hace falta JS/CSS auxiliar

Acciones:
- añadir barra de controles por panel SVG
- encapsular cada object SVG en un viewport controlado
- añadir copy y tab behavior sin romper el script actual
- mostrar ayuda visible sobre el significado de niveles ocultos

Resultado esperado:
- diagramas navegables en tablas con muchas relaciones

### Slice C: aclarar semántica del pie Graphviz
Cambios previstos:
- src/util_bbdd/analysis/graphviz_ext.py

Acciones:
- revisar el texto del footer generado por _add_graph_footer
- sustituir mensajes ambiguos por textos más claros y consistentes con HTML/Word

Resultado esperado:
- uniformidad de lenguaje entre SVG, HTML y Word

Estado:
- implementado para SVG y extendido en esta sesión también a Word

### Slice D: endurecer contratos con tests
Cambios previstos:
- tests/unit/test_html_generator_diagrams.py
- tests/unit/test_analysis_graph_document.py
- tests/unit/test_doc_generators_helpers.py

Acciones:
- validar banderas nuevas del summary
- validar payload enriquecido de tabs
- validar texto explicativo de hidden levels
- validar que el render HTML contiene controles y etiquetas esperadas

Resultado esperado:
- capacidad de evolucionar el detalle HTML sin regresiones silenciosas

### Slice E: rendimiento interformato reutilizando el caché existente
Cambios previstos:
- src/util_bbdd/doc/database_documentation.py
- src/util_bbdd/doc/html_generator.py
- src/util_bbdd/doc/word_generator.py
- tests/unit/test_database_documentation.py
- tests/unit/test_doc_generators_helpers.py

Acciones:
- mover la decisión de construir `GraphvizRelationshipGraphExt` al nivel de orquestación cuando la misma ejecución genere Word y HTML con diagramas
- permitir inyectar un `graph_generator` opcional en Word y HTML manteniendo el fallback actual
- reutilizar así `_graph_document_cache_by_context` ya disponible por instancia en `analysis/base.py`
- evitar crear un caché nuevo en `metadata/cache.py` para un problema que ya tiene mecanismo de reutilización suficiente

Resultado esperado:
- una misma corrida multi-formato deja de recomputar el `GraphDocument` base por separado en Word y HTML

Estado:
- implementado en esta sesión sobre la capa de orquestación documental y validado con tests unitarios focalizados y smoke test funcional

## Refactor plan

### Refactor autorizado en esta fase
- micro-refactor local dentro de html_generator.py si ayuda a separar:
  - construcción de summary
  - construcción de tabs
  - construcción de metadata UX

### Refactor no autorizado en esta fase
- mover clases entre módulos de analysis
- rediseñar GraphDocument
- unificar analysis Graphviz y matplotlib en una nueva jerarquía
- limpieza transversal de tipado o dependencias

## PR action plan

### PR 1 recomendado
Objetivo:
- UX HTML + contrato de payload + tests

Incluye:
- html_generator.py
- detail.html.j2
- assets HTML si hacen falta
- ajustes mínimos en graphviz_ext.py de texto/metadata
- tests unitarios afectados

No incluye:
- rediseño de analysis/base.py
- política completa de vistas
- cleanup de mypy

### PR 2 opcional posterior
Objetivo:
- política de vistas
- mejoras de columnas truncadas por nodo
- optimización adicional de tiempos si el profiling lo justifica

### PR 3 recomendado tras cerrar la slice actual
Objetivo:
- reutilización interformato del generador Graphviz para aprovechar el caché existente de `GraphDocument`

Incluye:
- `database_documentation.py`
- `html_generator.py`
- `word_generator.py`
- tests unitarios del flujo multi-formato

No incluye:
- nuevo caché en `metadata/cache.py`
- refactor transversal de `analysis`
- cambios de contrato en payload HTML o Word

Estado:
- implementado y validado en esta sesión

## Test strategy

### Unit tests obligatorios
- test_analysis_graph_document.py
  - mantener semántica de hidden levels
  - si se añaden visibles, validar visible_outgoing_levels y visible_incoming_levels
- test_html_generator_diagrams.py
  - validar payload enriquecido
  - validar render de ayudas, labels y controles HTML
- test_doc_generators_helpers.py
  - validar que Word sigue expresando hidden levels con semántica coherente

### Regression checks obligatorias
- pytest -q
- ruff check .

### Regression checks informativas
- mypy src
  - solo para medir no regresión local, no como gate de salida

## Security and performance review

### Security
- mantener escape de rutas y atributos HTML
- no inyectar texto libre no escapado en SVG o plantilla
- no abrir enlaces SVG con href calculados fuera del mapa de navegación conocido

### Performance
- no regenerar SVG adicionales si ya se dispone del flujo por niveles
- evitar parseos redundantes de SVG cuando no haya enlaces que inyectar
- si se aborda optimización real, hacerlo con medición explícita y fuera de esta primera slice
- la siguiente slice natural debe priorizar reutilización interformato del generador antes de abrir nuevas líneas de optimización local

## Risks
- que el JS de zoom/pan interfiera con el comportamiento del object SVG en algunos navegadores
- que la ampliación del payload rompa tests frágiles de detalle HTML
- que los textos del footer diverjan entre Graphviz, HTML y Word si no se centralizan

## Open decisions
- aprobar o no la exclusión inicial de vistas
- decidir si el texto “Salida oculta” se mantiene visible literalmente o solo como ayuda secundaria
- decidir si la leyenda de cardinalidad vive en HTML, en el SVG o en ambos

### Slice F: clasificación visual de tablas por tipología de nodo
Cambios previstos:
- src/util_bbdd/analysis/base.py
- src/util_bbdd/analysis/graphviz_ext.py
- tests/unit/test_analysis_graph_document.py
- tests/unit/test_graphviz_ext_helpers.py
- opcional: src/util_bbdd/doc/html_generator.py

Acciones:
- introducir una tipología visual de nodo calculada desde `analysis/base.py`
- limitar la primera heurística a tipos realmente inferibles con el modelo actual: `entity`, `association`, `hierarchy`
- aplicar colores pastel por tipología en Graphviz manteniendo un acento claro para la raíz
- no ampliar todavía colores de relaciones más allá de `FK`, porque el contrato actual no modela otros tipos reales

Resultado esperado:
- el diagrama deja de comunicar solo raíz frente a relacionadas y empieza a reflejar semántica estructural de tablas

Estado:
- implementado en esta sesión sobre `analysis/base.py` y `graphviz_ext.py` con tests focalizados
- extendido en esta sesión con exposición explícita en la leyenda HTML y con una heurística más robusta para tablas puente con PK compuesta basada en FKs

## Recommendation
Estado actualizado:
- Slice A + Slice B + tests asociados: ya implementadas
- Slice C: resuelta en SVG y Word
- Slice D: cubierta por la batería focalizada ya ejecutada
- Slice E: implementada y validada
- Slice F: implementada y validada

Recomendación actual:
- la tipología ya se expone en la leyenda HTML; el siguiente paso natural pasa a ser decidir si esta semántica heurística debe documentarse también en la documentación pública de v0.6.1 y si conviene endurecer más la heurística con reglas opcionales por motor o por patrón de tabla puente

Decisión actual:
- la slice de endurecimiento para tablas puente complejas no entra antes del cierre de v0.6.1
- motivo: la heurística actual ya cubre el caso simple y el caso con PK compuesta, no hay hallazgo bloqueante abierto, y ampliar ahora la clasificación aumentaría el riesgo de regresión visual cerca del corte de release
- criterio de reentrada: abordar esta slice justo después del cierre de v0.6.1 o solo antes si aparece un caso real reproducible que rompa la legibilidad esperada del diagrama
