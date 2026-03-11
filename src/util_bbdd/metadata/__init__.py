"""Módulo metadata: Gestión centralizada de metadatos de BD.

Consolidación de:
- cache.py - Cachés de metadatos y análisis de relaciones
- contracts.py - Protocolos para proveedores de metadatos
- normalizer.py - Normalización de resultados de metadatos
"""

# Imports desde cache
# Imports desde builder
from .builder import DDLBuilder
from .cache import (
    DatabaseMetadataCache,
    RelationshipMetadataCache,
)

# Imports desde contracts
from .contracts import (
    AsyncMetadataProvider,
    Row,
    Rows,
    SyncMetadataProvider,
)

# Imports desde fetcher
from .fetcher import MetadataFetcher

# Imports desde manager
# Imports desde normalizer
from .normalizer import (
    NormalizedColumnRow,
    NormalizedTableRow,
    normalize_column_rows,
    normalize_rows_as_dicts,
    normalize_table_rows,
)

__all__ = [
    # Cache
    "DatabaseMetadataCache",
    "RelationshipMetadataCache",
    # Contracts
    "Row",
    "Rows",
    "SyncMetadataProvider",
    "AsyncMetadataProvider",
    # Normalizer
    "NormalizedTableRow",
    "NormalizedColumnRow",
    "normalize_table_rows",
    "normalize_column_rows",
    "normalize_rows_as_dicts",
    # Builder
    "DDLBuilder",
    # Fetcher
    "MetadataFetcher",
    # Manager
    "MetadataManager",
]
