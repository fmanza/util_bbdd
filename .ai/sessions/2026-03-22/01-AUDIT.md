# AUDIT_PLAN

## Veredicto

La refactorización propuesta para v0.6.0 es necesaria y está justificada por el estado actual del código. El subsistema de grafos cumple el caso base de primer nivel, pero no soporta profundidad configurable, mezcla responsabilidades de análisis y renderizado, y expone un contrato de configuración/documentación que ya condiciona el diseño de la solución.

Veredicto: APROBADO CON REFACTOR ESTRUCTURAL.

## Alcance auditado

- src/util_bbdd/analysis/base.py
- src/util_bbdd/analysis/graphviz_ext.py
- src/util_bbdd/analysis/matplotlib_graph.py
- src/util_bbdd/doc/html_generator.py
- src/util_bbdd/doc/word_generator.py
- src/util_bbdd/doc/print_config_manager.py
- src/util_bbdd/doc/database_documentation.py
- src/util_bbdd/metadata/cache.py
- tests/unit/test_analysis_relationship_base.py

## Hallazgos funcionales

### 1. El análisis de relaciones está limitado a primer nivel

Evidencia:
- DatabaseRelationshipGraphBase.analyze_table_relations resuelve solo relaciones salientes e incoming directas de una tabla.
- No existe una estructura de traversal por profundidad, niveles, dirección ni control de visitados para más de un salto.

Impacto:
- No se puede cumplir el objetivo principal de relaciones de n niveles.
- HTML y Word solo pueden renderizar lo que ya entrega ese análisis plano.

### 2. La paginación actual resuelve cantidad de relaciones, no profundidad ni semántica de niveles

Evidencia:
- _split_relations_for_visualization divide una lista lineal de relaciones según max_subnodes.
- El algoritmo no conoce niveles de entrada/salida ni grupos por profundidad.

Impacto:
- La paginación actual sirve como limitador visual, pero no cubre el requisito de pestañas por nivel ni el indicador de niveles omitidos.

### 3. La cardinalidad está calculada como etiqueta textual, no como modelo visual

Evidencia:
- GraphvizRelationshipGraphExt._determine_cardinality devuelve cadenas 1:N, 1:1, M:N o N:1.
- _add_edges_to_graph incrusta esa cardinalidad en xlabel junto al mapeo de columnas.

Impacto:
- No existe una representación separada para extremos de arista.
- No se puede situar 1 y n en nodos opuestos ni cambiar de estilo sin reescribir el renderer.

### 4. La visualización de columnas es binaria y no responde a los modos requeridos

Evidencia:
- El contrato actual solo maneja show_columns como booleano.
- _build_table_html_label renderiza todas las columnas si show_columns es true.

Impacto:
- No existen los modos COMPACT, RELATIONS y ALL.
- No puede limitarse por número máximo ni mostrar puntos suspensivos derivados de una política.

### 5. HTML y Word dependen directamente de GraphvizRelationshipGraphExt

Evidencia:
- HtmlGenerator y WordGenerator construyen GraphvizRelationshipGraphExt directamente.
- Ambos consumen métodos concretos generate_graphviz_graph_paginated_ext y generate_single_table_graph_ext.

Impacto:
- No hay frontera clara entre construcción de grafo y renderizado documental.
- Cualquier cambio de API en analysis obliga a tocar doc.

### 6. El contrato de configuración aún modela la versión antigua

Evidencia:
- PrintConfigManager.DEFAULT_GRAPH mantiene first_level_only y max_subnodes.
- resolve_for_html y resolve_for_word propagan show_columns, first_level_only y max_subnodes.
- database_documentation.py documenta grafo.max_subnodes como eje principal de configuración.

Impacto:
- La configuración actual no puede expresar profundidad máxima, modo de columnas, visibilidad de tipos o estrategia de cardinalidad.
- La migración a v0.6.0 implica rediseñar el contrato de configuración, no solo ampliar parámetros.

## Hallazgos técnicos

### 1. Mezcla de responsabilidades en graphviz_ext.py

El módulo concentra:
- acceso a metadatos de columnas
- cálculo de PK y UNIQUE
- inferencia de cardinalidad
- construcción de etiquetas HTML de nodos
- configuración visual de Graphviz
- renderizado de archivos
- paginación de salida

Consecuencia:
- alta probabilidad de regresión ante cambios
- baja reutilización por formatos alternativos
- testing unitario difícil, porque casi todo pasa por una clase concreta

### 2. La base de analysis no modela un dominio de grafo reutilizable

DatabaseRelationshipGraphBase devuelve listas planas de TableRelation y set de tablas. Falta un modelo intermedio que represente:
- niveles
- dirección de traversal
- nodos visibles vs omitidos
- columnas visibles por política
- cardinalidad por extremo

Consecuencia:
- cada renderer tendría que volver a inferir cosas visuales desde una lista plana

### 3. La cache está infrautilizada para el problema nuevo

Puntos positivos:
- metadata/cache.py ya separa metadatos BD y análisis derivado
- graphviz_ext.py ya usa RelationshipMetadataCache para PK, UNIQUE y cardinalidad

Límite actual:
- no existe cache de traversal por profundidad, ni de subgrafos normalizados, ni de columnas filtradas por modo

### 4. Existe acoplamiento al contrato público actual de analysis

analysis/__init__.py expone DatabaseRelationshipGraphBase, GraphvizRelationshipGraphExt y MatplotlibRelationshipGraph.

Consecuencia:
- la refactorización sin compatibilidad hacia atrás debe asumir cambio deliberado de exports públicos
- también exige guía de migración explícita

### 5. Matplotlib replica la limitación de primer nivel

MatplotlibRelationshipGraph hereda la misma base y usa analyze_table_relations, por lo que comparte la restricción funcional.

Consecuencia:
- si se mantiene como renderer soportado, debe migrar al mismo núcleo de traversal
- si no es prioritario en v0.6.0, hay que documentar su estado o degradarlo explícitamente

## Riesgos funcionales

- Riesgo alto de romper HTML y Word si se cambia analysis sin introducir una abstracción intermedia.
- Riesgo alto de incoherencia entre formatos si cada uno resuelve niveles y columnas por su cuenta.
- Riesgo medio de degradación visual si se intenta extender GraphvizRelationshipGraphExt sin extraer primero el dominio del grafo.

## Riesgos técnicos

- Riesgo alto de deuda técnica si se añaden parámetros nuevos sobre show_columns y first_level_only.
- Riesgo medio de consumo extra de memoria si el traversal multinivel no controla visitados, dirección y deduplicación de relaciones.
- Riesgo medio de duplicidad de cachés si el nuevo diseño no aprovecha metadata/cache.py como autoridad.

## Riesgos de seguridad

- No se observan riesgos críticos nuevos en Fase 1.
- Riesgo bajo de inyección en etiquetas SVG/HTML si nombres de tablas o columnas no se escapan de forma consistente en la nueva representación visual.
- Riesgo bajo de denegación de servicio lógica si se permite profundidad sin límites razonables o sin protección ante ciclos.

## Riesgos de rendimiento

- El índice de relaciones entrantes evita parte del coste, pero el salto a n niveles multiplicará consultas si no se cachea el traversal por contexto.
- El renderizado con columnas completas por tabla escalará mal en esquemas con muchas columnas si no se filtra antes de renderizar.
- HTML con pestañas por nivel exige reutilizar una estructura de grafo precomputada, no regenerar SVG por cada vista lógica.

## Cobertura actual de tests

Estado verificado:
- solo existe tests/unit/test_analysis_relationship_base.py para la base
- cubre primer nivel, parsing por motor, división paginada y reporte base

Gap:
- no hay tests de GraphvizRelationshipGraphExt
- no hay tests de integración con HtmlGenerator o WordGenerator para diagramas
- no hay tests de configuración de grafo en PrintConfigManager

## Simplificaciones posibles

### Simplificación recomendada 1

Separar construcción y renderizado.

Primero construir un modelo GraphDocument agnóstico de formato; después adaptarlo a Graphviz, HTML y Word.

### Simplificación recomendada 2

Unificar traversal y filtrado de columnas en analysis.

Los generadores doc no deben decidir profundidad, columnas visibles ni cardinalidad; solo consumir un resultado ya resuelto.

### Simplificación recomendada 3

Tratar Matplotlib como renderer secundario.

Si no entra en la primera entrega funcional de v0.6.0, dejarlo fuera del alcance operativo y documentarlo como pendiente o experimental.

### Simplificación recomendada 4

Sustituir show_columns y first_level_only por un único bloque de configuración de grafo.

Esto reduce ramas de compatibilidad y evita extender un contrato ya obsoleto.

## Conclusión operativa

La Fase 1 confirma que el cambio debe abordarse como refactorización estructural con breaking change controlado. Intentar añadir n niveles, pestañas HTML y modos de columnas sobre la clase actual aumentaría el acoplamiento y dejaría la deuda técnica en peor estado.

La siguiente fase debe empezar por extraer un núcleo de dominio de grafo y redefinir el contrato de configuración.
