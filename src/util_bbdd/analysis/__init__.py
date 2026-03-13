"""Módulo analysis: Análisis de relaciones entre tablas de bases de datos.

Proporciona visualización y análisis de relaciones mediante grafos usando
Graphviz y Matplotlib.

Consolidación de:
- base.py - Clase base DatabaseRelationshipGraphBase y TableRelation
- graphviz.py - Implementación con Graphviz
- graphviz_ext.py - Implementación extendida con Graphviz (con columnas)
- matplotlib_graph.py - Implementación con Matplotlib y NetworkX
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .base import DatabaseRelationshipGraphBase, TableRelation
    from .graphviz_ext import GraphvizRelationshipGraphExt
    from .matplotlib_graph import MatplotlibRelationshipGraph

__all__: list[str] = [
    # Clase base y tipos
    "DatabaseRelationshipGraphBase",
    "TableRelation",
    # Implementaciones
    "GraphvizRelationshipGraphExt",
    "MatplotlibRelationshipGraph",
]

_SYMBOL_TO_MODULE: dict[str, str] = {
    "DatabaseRelationshipGraphBase": "base",
    "TableRelation": "base",
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
