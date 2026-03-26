# DISCOVERY

## Objective
Contrastar docs\v0.6.2\crear_prompt.md contra el código real actual para identificar qué parte del objetivo ya existe, qué parte sigue abierta y dónde debe concentrarse una eventual implementación sin mezclarla con refactor amplio.

## Scope reviewed
- src/util_bbdd/analysis/base.py
- src/util_bbdd/analysis/graphviz_ext.py
- src/util_bbdd/doc/html_generator.py
- src/util_bbdd/doc/templates/pages/detail.html.j2
- src/util_bbdd/doc/print_config_manager.py
- tests/unit/test_html_generator_diagrams.py
- tests/unit/test_graphviz_ext_helpers.py
- tests/unit/test_database_documentation.py

## Current renderer reality

### 1. El tamaño de nodo ya está controlado, pero no al nivel pedido por v0.6.2
- `graphviz_ext.py` ya fija un ancho visual de nodo y límites de truncado mediante constantes y estilos de label HTML.
- Para SVG no raster, el renderer usa hoy:
  - `table_width = 240`
  - `name_column_width = 160`
  - `type_column_width = 80`
  - límites de truncado para título, nombre de columna y tipo
- El renderer ya muestra aviso explícito cuando hay columnas ocultas por límite de visibilidad.
- Conclusión: el problema no es ausencia de control de tamaño, sino recalibración visual del tamaño actual para acercarlo al 75 por ciento solicitado.

### 2. La cardinalidad ya está separada del label central, pero no con geometría fija respecto al nodo relacionado
- `graphviz_ext.py` calcula cardinalidad y la traduce a marcadores por extremo con `CardinalityEndMarker`.
- Las aristas usan actualmente:
  - `xlabel` para la etiqueta relacional
  - `taillabel` para el marcador del origen
  - `headlabel` para el marcador del destino
- La leyenda HTML ya documenta que los marcadores de cardinalidad se muestran separados de la arista para mejorar la legibilidad.
- Conclusión: parte de la intención del prompt ya fue implementada en v0.6.1, pero el gap real sigue siendo la posición fina de esos marcadores cuando el layout Graphviz produce solapes o mala lectura.

### 3. La división en múltiples imágenes por densidad ya existe en analysis
- `base.py` expone `_split_relations_for_visualization()` con división paginada por bloques.
- `graphviz_ext.py` reutiliza esa división para generar varias páginas de relaciones cuando el volumen supera `max_subnodes`.
- `print_config_manager.py` ya normaliza `images_paginated` y `max_subnodes`.
- Conclusión: el requisito de mantener división en varias imágenes ya está cubierto en el núcleo actual.

### 4. Las pestañas por dirección y nivel ya existen en HTML
- `html_generator.py` ya construye `diagram_tabs`, `diagram_summary`, `visible_levels`, `hidden_levels`, `tab_id`, `short_title` y metadatos de ayuda por dirección.
- `detail.html.j2` ya renderiza grupos por dirección, tabs por nivel y paneles por cada diagrama SVG.
- Los tests unitarios ya validan esa estructura y su render final.
- Conclusión: el prompt v0.6.2 parte de una base más avanzada que la que describe; no hace falta diseñar tabs desde cero salvo que se quiera otra alternativa visual.

## Test evidence reviewed

### tests/unit/test_graphviz_ext_helpers.py
- valida truncado visual de textos y aviso de columnas ocultas
- valida el ancho del nodo y la paleta visual por tipo de tabla
- confirma que el tamaño del nodo ya se considera una preocupación explícita del renderer

### tests/unit/test_html_generator_diagrams.py
- valida `diagram_tabs`, `visible_levels`, `has_hidden_levels` y ayudas semánticas
- valida que la leyenda HTML ya incluye cardinalidad y tipo de relación actual
- valida el render de la UI de diagramas tabulados

### tests/unit/test_database_documentation.py
- valida compartición de `GraphvizRelationshipGraphExt` entre Word y HTML
- confirma que el rendimiento interformato ya no depende de crear un segundo sistema de caché

## Functional conclusions

### 1. v0.6.2 no es una iniciativa greenfield
La mayor parte de los fundamentos pedidos en el prompt ya existen:
- nodos con tamaño controlado
- truncado y cap de columnas
- cardinalidad separada de la arista principal
- imágenes paginadas por densidad
- tabs HTML por dirección y nivel

### 2. El gap principal es de ajuste geométrico y calibración visual
Lo pendiente parece concentrarse en:
- reducir el tamaño visual del nodo sin perder legibilidad
- mover mejor los marcadores de cardinalidad respecto a la arista y al nodo
- decidir si la alternativa a tabs por nivel debe ser realmente nueva o una mejora incremental sobre la UI actual

### 3. El prompt sobredimensiona el alcance respecto al estado real del repo
La petición habla como si hubiera que crear desde cero soporte de niveles, paginación y representación segmentada, pero el código ya lo soporta.
Eso reduce el espacio honesto de implementación a una slice de ajuste visual y semántico, no a una reescritura del subsistema.

### 4. La versión correcta queda fijada en v0.6.2
La referencia a 0.6.1 debe tratarse como residuo documental del prompt y no como instrucción funcional o de cierre.

## Recommended implementation slices

### Slice A · Calibración de nodo al 75 por ciento
- revisar `DEFAULT_TABLE_WIDTH`, anchos de columnas y truncados del label HTML de Graphviz
- validar el efecto en SVG y, si aplica, en salida raster/Word

### Slice B · Reposicionamiento de cardinalidades
- estudiar si Graphviz permite desplazar mejor `taillabel/headlabel` o si conviene usar otra estrategia de labeling
- documentar alternativas y tradeoffs antes de tocar el renderer

### Slice C · Revisión de UX HTML por densidad
- evaluar si la UI actual de tabs por dirección y nivel ya satisface el caso de lectura difícil
- si no basta, definir una mejora incremental y no una alternativa total

## Risks
- reducir demasiado el nodo y perder legibilidad de columnas y badges
- perseguir una posición geométrica perfecta de cardinalidad que dependa demasiado del layout interno de Graphviz
- abrir una nueva solución de tabs cuando la actual ya cubre buena parte del requerimiento

## Verdict
GO_CONDICIONAL para seguir con diseño técnico de slices visuales acotadas.

## Conditions to move forward
- mantener el trabajo bajo v0.6.2
- acotar la siguiente fase a ajuste visual y semántico, no a reescritura de analysis/doc
- decidir con evidencia si la mejora de cardinalidad es viable solo desde Graphviz o requiere otra capa de soporte
