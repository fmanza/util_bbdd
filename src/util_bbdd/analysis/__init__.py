"""Módulo analysis: Análisis de relaciones entre tablas de bases de datos.

Proporciona visualización y análisis de relaciones mediante grafos usando
Graphviz y Matplotlib.

Consolidación de:
- contracts.py - Protocol RelationshipGraphSource (lo que se exige de la fuente de metadatos)
- base.py - Clase base DatabaseRelationshipGraphBase y TableRelation
- graphviz_ext.py - Implementación extendida con Graphviz (con columnas)
- matplotlib_graph.py - Implementación con Matplotlib y NetworkX
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .base import (
        CardinalityEndMarker,
        ColumnDisplayConfig,
        ColumnVisualizationMode,
        DatabaseRelationshipGraphBase,
        GraphDocument,
        GraphEdge,
        GraphLevel,
        GraphNode,
        HiddenLevelsSummary,
        LevelDirection,
        TableRelation,
    )
    from .contracts import RelationshipGraphSource
    from .graphviz_ext import GraphvizRelationshipGraphExt
    from .matplotlib_graph import MatplotlibRelationshipGraph

__all__: list[str] = [
    # Contrato de la fuente de metadatos
    "RelationshipGraphSource",
    # Clase base y tipos
    "DatabaseRelationshipGraphBase",
    "TableRelation",
    "LevelDirection",
    "ColumnVisualizationMode",
    "ColumnDisplayConfig",
    "CardinalityEndMarker",
    "GraphNode",
    "GraphEdge",
    "GraphLevel",
    "HiddenLevelsSummary",
    "GraphDocument",
    # Implementaciones
    "GraphvizRelationshipGraphExt",
    "MatplotlibRelationshipGraph",
]

_SYMBOL_TO_MODULE: dict[str, str] = {
    "RelationshipGraphSource": "contracts",
    "DatabaseRelationshipGraphBase": "base",
    "TableRelation": "base",
    "LevelDirection": "base",
    "ColumnVisualizationMode": "base",
    "ColumnDisplayConfig": "base",
    "CardinalityEndMarker": "base",
    "GraphNode": "base",
    "GraphEdge": "base",
    "GraphLevel": "base",
    "HiddenLevelsSummary": "base",
    "GraphDocument": "base",
    "GraphvizRelationshipGraphExt": "graphviz_ext",
    "MatplotlibRelationshipGraph": "matplotlib_graph",
}


def __getattr__(name: str) -> Any:
    module_name: str | None = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
