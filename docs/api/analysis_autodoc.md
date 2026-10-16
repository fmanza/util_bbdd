# Análisis de Relaciones

`util_bbdd.analysis` construye el grafo de relaciones de una tabla (`GraphDocument`) y lo dibuja con Graphviz (extra
`analysis`) o Matplotlib (extra `analysis-matplotlib`). Referencia curada: [Grafos de Relaciones](analysis.md).

---

## DatabaseRelationshipGraphBase

::: util_bbdd.analysis.base.DatabaseRelationshipGraphBase
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## GraphvizRelationshipGraphExt

::: util_bbdd.analysis.graphviz_ext.GraphvizRelationshipGraphExt
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## MatplotlibRelationshipGraph

::: util_bbdd.analysis.matplotlib_graph.MatplotlibRelationshipGraph
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## Modelo del grafo

::: util_bbdd.analysis.base.GraphDocument
    options:
      show_source: false
      heading_level: 3

::: util_bbdd.analysis.base.LevelDirection
    options:
      show_source: false
      heading_level: 3

::: util_bbdd.analysis.base.TableRelation
    options:
      show_source: false
      heading_level: 3
