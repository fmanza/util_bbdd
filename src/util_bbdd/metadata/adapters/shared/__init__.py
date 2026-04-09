"""Funciones puras genéricas para procesamiento de DDL y metadatos."""

from __future__ import annotations

from .column_formatter import build_generic_columns_hint, normalize_column_type
from .constraint_extractor import extract_constraint_from_ddl
from .routine_normalizer import normalize_routine_type

__all__: list[str] = [
    "normalize_column_type",
    "normalize_routine_type",
    "extract_constraint_from_ddl",
    "build_generic_columns_hint",
]
