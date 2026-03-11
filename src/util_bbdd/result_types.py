"""
⚠️ DEPRECATED: Use `from util_bbdd.results import ...` instead

This module is kept for backward compatibility only.
All types have been moved to util_bbdd.results module.
"""

from .results.types import (
    QueryResult,
    Row,
    RowOrNone,
    Rows,
)

__all__ = ["Row", "Rows", "RowOrNone", "QueryResult"]
