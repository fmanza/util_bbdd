# PLAN

## objetivo
- preparar la siguiente slice funcional de v0.6.1 como clasificación visual de tablas para que el renderer deje de distinguir solo entre tabla principal y tabla relacionada
- cubrir el gap real que sigue abierto respecto al prompt: colores pastel por tipo de tabla, sin inventar todavía tipos de relación que el modelo no expone

## rutas afectadas
- src/util_bbdd/analysis/base.py
- src/util_bbdd/analysis/graphviz_ext.py
- src/util_bbdd/doc/html_generator.py
- tests/unit/test_analysis_graph_document.py
- tests/unit/test_graphviz_ext_helpers.py
- opcional: tests/unit/test_html_generator_diagrams.py si la leyenda HTML se amplía con tipos de tabla

## server/client
- no aplica

## componentes implicados
- `GraphNode` y `GraphDocument` como contrato base del renderer
- `DatabaseRelationshipGraphBase` como punto adecuado para calcular tipología de nodo a partir de metadatos reales
- `GraphvizRelationshipGraphExt` como consumidor de la tipología visual para aplicar color y semántica al nodo
- `HtmlGenerator` solo si se decide reflejar la nueva tipología en la leyenda HTML

## tipos necesarios
- nuevo enum o string restringido para tipología visual de tabla
- nuevo campo opcional o explícito en `GraphNode` para almacenar esa tipología

## impactos en auth o roles
- ninguno

## riesgos
- introducir heurísticas pobres que etiqueten mal tablas reales y degraden la legibilidad en lugar de mejorarla
- mezclar en la misma slice clasificación de nodos y clasificación de tipos de relación, cuando el modelo actual solo expone `FK`
- acoplar la clasificación a reglas demasiado específicas de un motor concreto

# AUDIT_PLAN

## riesgos funcionales
- hoy el color del nodo depende solo de `is_root`; cambiarlo exige una heurística estable y testeable
- una clasificación demasiado agresiva puede cambiar de forma visible diagramas existentes sin mejorar realmente la comprensión

## riesgos técnicos
- `TableRelation.relation_type` sigue fijado a `FK` en `analysis/base.py`, así que la parte de colores por tipo de relación no es aún una slice honesta
- la clasificación de tablas sí es viable con metadatos ya disponibles: PK, FK, columnas y autorrelaciones
- conviene calcular la tipología en `analysis/base.py` para que quede disponible a cualquier renderer y no solo a Graphviz

## riesgos de seguridad
- sin riesgos nuevos relevantes; la slice es de semántica visual y no altera entradas externas ni consultas

## simplificaciones posibles
- limitar esta slice a tipología de tablas y dejar los tipos de relación para una fase posterior
- modelar la clasificación inicial con tres estados operativos y verificables:
  - `entity`
  - `association`
  - `hierarchy`
- mantener `view` fuera de alcance porque la política actual sigue siendo exclusión explícita de vistas del grafo

# IMPLEMENT

## cambios por archivo

### src/util_bbdd/analysis/base.py
- añadir la tipología visual al modelo de nodo
- calcular la tipología con heurísticas acotadas y documentadas
- proponer reglas iniciales:
  - `hierarchy`: tabla con FK autorreferenciada o patrón claro de parent-child interno
  - `association`: tabla puente con al menos dos FKs y predominio de columnas relacionales sobre columnas de negocio
  - `entity`: caso general restante

### src/util_bbdd/analysis/graphviz_ext.py
- sustituir la lógica binaria `main vs related` por una paleta basada en tipología del nodo, manteniendo un acento claro para la tabla raíz
- mantener contraste y legibilidad del texto
- no modificar aún el color por tipo de relación, porque el contrato actual sigue siendo `FK`

### src/util_bbdd/doc/html_generator.py
- ampliar la leyenda HTML con tipos de tabla visibles en el renderer
- reflejar solo los tipos realmente soportados por el modelo

### tests/unit/test_analysis_graph_document.py
- validar la clasificación de nodos en escenarios sintéticos mínimos
- cubrir entidad, asociación y jerarquía
- cubrir tabla puente con PK compuesta basada en FKs y columnas adicionales

### tests/unit/test_graphviz_ext_helpers.py
- validar la traducción de tipología a color visual del nodo
- validar que la tabla raíz conserva un tratamiento visual distinguible aunque comparta tipología

## código
- implementado en esta sesión sobre `analysis/base.py` y `graphviz_ext.py` con cobertura focalizada en análisis y helpers del renderer
- extendido en esta sesión a `html_generator.py` y a la plantilla de detalle para exponer la tipología en la leyenda HTML

## explicación breve
- el renderer actual ya resolvió profundidad, cardinalidad, UX HTML y rendimiento interformato
- el gap funcional más directo respecto al prompt es la semántica de color por tipo de tabla
- esta slice es más honesta que intentar colorear tipos de relación no modelados todavía por `analysis`

# AUDIT_CODE

## bugs potenciales
- riesgo de considerar como `association` una tabla de negocio con varias FKs pero identidad propia
- riesgo de etiquetar mal tablas jerárquicas si la heurística solo mira autorreferencias simples

## edge cases
- tablas con PK compuesta y varias FKs
- tablas autorreferenciadas con columnas adicionales de negocio
- tablas de auditoría o catálogo con una sola FK pero semántica de entidad
- tablas sin PK explícita en motores permisivos

## performance
- el cálculo de tipología debe apoyarse en metadatos ya consultados o cacheados
- no debe introducir rondas extra de análisis por nodo fuera del flujo actual del documento de grafo

## seguridad
- sin cambios de superficie

## tipado
- preferible un enum específico frente a strings libres si el estilo del módulo lo permite

## deuda técnica
- la clasificación inicial será heurística; conviene documentarla como aproximación visual, no como taxonomía absoluta del modelo de datos
- la nueva regla de PK compuesta reduce falsos negativos en tablas puente, pero no resuelve todavía todos los casos híbridos

# VERSION

## commit message
- docs(v0.6.1): prepare table visual classification slice

## changelog
- no actualizar todavía; la slice queda implementada pero fuera aún de la fase de versionado global

## impacto
- deja definido el siguiente objetivo funcional conectado con el prompt original y con el estado real del modelo actual
- deja además ejecutados los dos pasos naturales posteriores: exposición HTML de la tipología y refinado heurístico de `association`

## rollback
- eliminar el artefacto de sesión si se decide no seguir esta línea

## pruebas sugeridas
- pytest tests/unit/test_analysis_graph_document.py tests/unit/test_graphviz_ext_helpers.py tests/unit/test_html_generator_diagrams.py -q
- prueba manual con una base que tenga una tabla puente y una tabla autorreferenciada

## validation status
- pytest tests/unit/test_analysis_graph_document.py tests/unit/test_graphviz_ext_helpers.py tests/unit/test_html_generator_diagrams.py -q
- resultado: 17 passed
