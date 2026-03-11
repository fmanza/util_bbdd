"""Módulo analysis: Análisis de relaciones entre tablas de bases de datos.

Proporciona visualización y análisis de relaciones mediante grafos usando
Graphviz y Matplotlib.

Consolidación de:
- base.py - Clase base DatabaseRelationshipGraphBase y TableRelation
- graphviz.py - Implementación con Graphviz
- graphviz_ext.py - Implementación extendida con Graphviz (con columnas)
- matplotlib_graph.py - Implementación con Matplotlib y NetworkX
"""

from .base import DatabaseRelationshipGraphBase, TableRelation
from .graphviz import GraphvizRelationshipGraph
from .graphviz_ext import GraphvizRelationshipGraphExt
from .matplotlib_graph import MatplotlibRelationshipGraph

__all__: list[str] = [
    # Clase base y tipos
    "DatabaseRelationshipGraphBase",
    "TableRelation",
    # Implementaciones
    "GraphvizRelationshipGraph",
    "GraphvizRelationshipGraphExt",
    "MatplotlibRelationshipGraph",
]
