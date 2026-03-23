# PLAN

## Objetivo

Rediseñar el subsistema de análisis y renderizado de relaciones para soportar profundidad configurable, visualización parametrizable de columnas y cardinalidad por extremos, reutilizando la cache centralizada y sin compatibilidad hacia atrás.

## Rutas afectadas

- src/util_bbdd/analysis/base.py
- src/util_bbdd/analysis/graphviz_ext.py
- src/util_bbdd/analysis/matplotlib_graph.py
- src/util_bbdd/analysis/__init__.py
- src/util_bbdd/doc/html_generator.py
- src/util_bbdd/doc/word_generator.py
- src/util_bbdd/doc/print_config_manager.py
- src/util_bbdd/doc/database_documentation.py
- src/util_bbdd/metadata/cache.py
- tests/unit/test_analysis_relationship_base.py
- tests nuevos en analysis, doc y configuración

## Server/Client

No aplica. El repositorio es una librería Python y la ejecución es server-side/offline.

## Componentes implicados

### Núcleo de análisis

- RelationshipTraversalService
- GraphProjectionService
- ColumnSelectionPolicy
- CardinalityResolver
- GraphDocument

### Renderers

- GraphvizRelationshipRenderer
- HtmlDiagramAdapter
- WordDiagramAdapter
- MatplotlibRelationshipRenderer opcional o degradado a secundario

### Configuración

- GraphConfig
- ColumnMode
- LevelDirection
- GraphFormatOptions

## Tipos necesarios

- TableRelation
- GraphNode
- GraphEdge
- GraphLevel
- GraphDocument
- HiddenLevelsSummary
- ColumnDisplayConfig
- CardinalityEndMarker
- GraphBuildRequest
- GraphRenderResult

## Impactos en auth o roles

No aplica. No se observan componentes de autenticación, autorización o roles dentro del alcance auditado.

## Riesgos

- ruptura de API pública en analysis y doc
- migración obligatoria del bloque grafo en configuración
- necesidad de adaptar HTML y Word al nuevo contrato sin duplicar lógica
- riesgo de sobrealcance si se intenta rehacer Matplotlib en la misma iteración sin prioridad clara

## Arquitectura objetivo

### 1. Modelo de dominio intermedio

Introducir un modelo agnóstico a formato que represente el grafo ya resuelto:

- GraphDocument: resultado completo para una tabla raíz
- GraphLevel: conjunto de nodos y aristas por profundidad y sentido
- GraphNode: tabla, columnas visibles, flags de PK/FK/UK y metadatos visuales
- GraphEdge: extremos, columnas implicadas, cardinalidad por extremo y constraint
- HiddenLevelsSummary: niveles omitidos de entrada y salida

Este modelo será la única entrada para renderers y generadores documentales.

### 2. Separación por responsabilidad única

#### RelationshipTraversalService

Responsabilidad:
- recorrer el grafo de relaciones por profundidad
- deduplicar relaciones
- distinguir entrada y salida
- cortar por profundidad máxima
- producir un resultado navegable por niveles

#### ColumnSelectionPolicy

Responsabilidad:
- decidir qué columnas se muestran en cada nodo
- soportar modos compact, relations y all
- controlar show_data_types
- calcular si debe mostrarse indicador de truncado

#### CardinalityResolver

Responsabilidad:
- convertir metadatos en marcadores de cardinalidad por extremo
- desacoplar cálculo semántico de la representación visual

#### GraphProjectionService

Responsabilidad:
- transformar traversal y políticas en GraphDocument final
- enriquecer nodos con columnas visibles y símbolos

### 3. Renderers sobre protocolo estable

Definir un protocolo de renderizado para desacoplar la construcción del grafo de su salida final.

Propuesta:

```python
class RelationshipGraphRenderer(Protocol):
    def render(self, document: GraphDocument, request: GraphBuildRequest) -> GraphRenderResult:
        ...
```

Renderers previstos:
- Graphviz renderer para SVG, PNG y PDF
- adaptador HTML para pestañas por nivel y por sentido
- adaptador Word para diagramas por tabla y resumen de niveles omitidos

### 4. Contrato de configuración nuevo

Sustituir el bloque antiguo por una estructura orientada al nuevo dominio.

Propuesta:

```toml
[imprimir_config.imprimir.grafo]
enabled = true
max_depth = 3
direction = "both"
render_format = "svg"
images_paginated = true
max_subnodes = 10

[imprimir_config.imprimir.grafo.columns]
mode = "relations"
max_items = 8
show_data_types = false

[imprimir_config.imprimir.grafo.cardinality]
style = "end_markers"
show_constraint_name = false
```

Decisiones:
- eliminar first_level_only
- reemplazar show_columns por columns.mode
- mantener max_subnodes como limitador visual, ya no como proxy de profundidad

### 5. Integración con cache

Reutilizar src/util_bbdd/metadata/cache.py como única autoridad para:
- columnas de tabla
- PK, UNIQUE y FKs
- cardinalidad derivada

Extender solo si es necesario con caches de:
- traversal por contexto, tabla raíz, profundidad y dirección
- selección de columnas por tabla y política

No introducir una segunda cache paralela en renderers.

## Diseño por fases de implementación

### Fase 2.1

Extraer el dominio y el traversal sin cambiar todavía HTML/Word.

Entregables:
- nuevo núcleo de analysis
- tests de traversal multinivel
- tests de cardinalidad por extremos

### Fase 2.2

Reescribir Graphviz sobre GraphDocument.

Entregables:
- renderer Graphviz desacoplado
- compatibilidad con paginación visual
- soporte de columnas por política

### Fase 2.3

Adaptar HTML y Word al nuevo contrato.

Entregables:
- pestañas HTML por nivel y sentido
- indicador de niveles ocultos en HTML y Word
- actualización de PrintConfigManager

### Fase 2.4

Cerrar API pública y migración.

Entregables:
- exports finales en analysis/__init__.py
- tests de integración
- guía de migración de configuración y uso

## Decisiones explícitas de v0.6.0

- Breaking change aprobado
- No mantener first_level_only
- No añadir parámetros nuevos a GraphvizRelationshipGraphExt como solución transitoria
- No duplicar lógica de niveles en HTML y Word
- No tratar la paginación visual como sustituto del modelo multinivel

## Estrategia mínima de pruebas

- unit tests del traversal por profundidad, dirección y ciclos
- unit tests de selección de columnas por modo
- unit tests de cardinalidad por extremos
- tests de integración de PrintConfigManager con el nuevo contrato
- tests de HtmlGenerator y WordGenerator sobre payload y opciones de diagramas

## Criterio de salida de Fase 1

Fase 1 se considera cerrada porque ya existe:

- diagnóstico verificable del estado actual
- veredicto técnico sobre viabilidad y riesgo
- arquitectura objetivo con responsabilidades separadas
- plan de implementación incremental para Fase 2
