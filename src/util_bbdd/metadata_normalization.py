"""
⚠️ DEPRECATED: Use `from util_bbdd.metadata import ...` instead

This module is kept for backward compatibility only.
All classes have been moved to util_bbdd.metadata module.
"""

from .metadata.normalizer import (
    NormalizedColumnRow,
    NormalizedTableRow,
    normalize_column_rows,
    normalize_rows_as_dicts,
    normalize_table_rows,
)

__all__ = [
    "NormalizedTableRow",
    "NormalizedColumnRow",
    "normalize_table_rows",
    "normalize_column_rows",
    "normalize_rows_as_dicts",
]
