"""DEPRECATED: Usar query.QueryRegistry en su lugar.

Este archivo se mantiene solo para compatibilidad hacia atrás.
El contenido real está en query/registry.py
"""

from .query.registry import PARAMETER_PATTERN, QueryRegistry

__all__ = ["QueryRegistry", "PARAMETER_PATTERN"]
