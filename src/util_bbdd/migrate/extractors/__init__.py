"""Extractores de esquemas para el módulo migrate."""

from .base import SchemaExtractor
from .oracle import OracleSchemaExtractor

__all__: list[str] = [
    "SchemaExtractor",
    "OracleSchemaExtractor",
]
