"""Módulo results: Normalización y tipos de resultados de consultas.

Consolidación de:
- types.py - Type aliases para tipos de resultados
- normalizer.py - Normalización de resultados crudos de drivers
"""

# Imports desde types
# Imports desde normalizer
from .normalizer import ResultNormalizer
from .types import (
    CustomQueryResult,
    QueryResult,
    Row,
    RowOrNone,
    Rows,
)

__all__: list[str] = [
    # Types
    "Row",
    "Rows",
    "RowOrNone",
    "QueryResult",
    "CustomQueryResult",
    # Normalizer
    "ResultNormalizer",
]
