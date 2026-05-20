"""Extractores de esquemas para el módulo migrate."""

from .base import SchemaExtractor
from .mariadb import MariaDBSchemaExtractor
from .oracle import OracleSchemaExtractor
from .postgresql import PostgreSQLSchemaExtractor
from .sqlserver import SQLServerSchemaExtractor

__all__: list[str] = [
    "SchemaExtractor",
    "OracleSchemaExtractor",
    "MariaDBSchemaExtractor",
    "SQLServerSchemaExtractor",
    "PostgreSQLSchemaExtractor",
]
