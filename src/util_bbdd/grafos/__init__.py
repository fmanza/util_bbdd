"""
Módulo grafos - Wrapper para compatibilidad hacia atrás.

Importa desde el nuevo módulo consolidado en util_bbdd.analysis
"""

from ..analysis import (
    DatabaseRelationshipGraphBase,
    GraphvizRelationshipGraph,
    GraphvizRelationshipGraphExt,
    MatplotlibRelationshipGraph,
    TableRelation,
)

__all__: list[str] = [
    "GraphvizRelationshipGraph",
    "GraphvizRelationshipGraphExt",
    "MatplotlibRelationshipGraph",
    "DatabaseRelationshipGraphBase",
    "TableRelation",
]
