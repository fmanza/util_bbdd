"""
Módulo wrapper para grafos - Compatibilidad hacia atrás en raíz.

Importa desde el nuevo módulo consolidado en util_bbdd.analysis
"""

from .analysis import (
    DatabaseRelationshipGraphBase,
    GraphvizRelationshipGraph,
    GraphvizRelationshipGraphExt,
    MatplotlibRelationshipGraph,
    TableRelation,
)

__all__ = [
    "GraphvizRelationshipGraph",
    "GraphvizRelationshipGraphExt",
    "MatplotlibRelationshipGraph",
    "DatabaseRelationshipGraphBase",
    "TableRelation",
]
