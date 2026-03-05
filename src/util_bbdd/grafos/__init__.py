"""
Módulo de generación de grafos de relaciones entre tablas de base de datos

Exporta las implementaciones especializadas y la clase generadora principal.
"""

from .graphviz_relationship_graph import GraphvizRelationshipGraph
from .graphviz_relationship_graph_ext import GraphvizRelationshipGraphExt
from .matplotlib_relationship_graph import MatplotlibRelationshipGraph
from .relationship_graph_base import DatabaseRelationshipGraphBase, TableRelation

__all__: list[str] = [
    "GraphvizRelationshipGraph",
    "GraphvizRelationshipGraphExt",
    "MatplotlibRelationshipGraph",
    "DatabaseRelationshipGraphBase",
    "TableRelation",
]
