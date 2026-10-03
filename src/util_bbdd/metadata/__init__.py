"""Módulo metadata: Gestión centralizada de metadatos de BD.

Consolidación de:
- cache.py - Cachés de metadatos y análisis de relaciones
- contracts.py - Protocolos para proveedores de metadatos
- normalizer.py - Normalización de resultados de metadatos
"""

# Imports desde cache
# Imports desde builder
from .async_manager import AsyncMetadataManager
from .builder import DDLBuilder
from .cache import (
    DatabaseMetadataCache,
    RelationshipMetadataCache,
)

# Lectura por lotes (ADR-003)
from .catalog_registry import (
    CatalogDialectNotFoundError,
    get_catalog_dialect,
    register_catalog_dialect,
    supported_catalog_engines,
)

# Imports desde contracts
from .contracts import (
    AsyncCatalogExecutor,
    AsyncMetadataProvider,
    AsyncMetadataSource,
    CatalogDialect,
    CatalogExecutor,
    CatalogQuery,
    MetadataSource,
    Row,
    Rows,
    SyncMetadataProvider,
)

# Imports desde fetcher
from .fetcher import MetadataFetcher

# Imports desde manager
from .manager import MetadataManager
from .model import (
    ALL_KINDS,
    CheckMeta,
    ColumnMeta,
    DatabaseMeta,
    ForeignKeyMeta,
    IdentityMeta,
    IndexMeta,
    Kind,
    KindNotLoadedError,
    PrimaryKeyMeta,
    RoutineKey,
    RoutineMeta,
    RoutineParameterMeta,
    SchemaSnapshot,
    TableMeta,
    UniqueMeta,
    ViewMeta,
)

# Imports desde normalizer
from .normalizer import (
    NormalizedColumnRow,
    NormalizedTableRow,
    normalize_column_rows,
    normalize_rows_as_dicts,
    normalize_table_rows,
)
from .snapshot_cache import SnapshotCache
from .source import AsyncCatalogSource, CatalogSource, SqlAlchemyCatalogExecutor

__all__: list[str] = [
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
    "AsyncMetadataManager",
    # Lectura por lotes (ADR-003)
    "ALL_KINDS",
    "AsyncCatalogExecutor",
    "AsyncCatalogSource",
    "AsyncMetadataSource",
    "CatalogDialect",
    "CatalogDialectNotFoundError",
    "CatalogExecutor",
    "CatalogQuery",
    "CatalogSource",
    "CheckMeta",
    "ColumnMeta",
    "DatabaseMeta",
    "ForeignKeyMeta",
    "IdentityMeta",
    "IndexMeta",
    "Kind",
    "KindNotLoadedError",
    "MetadataSource",
    "PrimaryKeyMeta",
    "RoutineKey",
    "RoutineMeta",
    "RoutineParameterMeta",
    "SchemaSnapshot",
    "SnapshotCache",
    "SqlAlchemyCatalogExecutor",
    "TableMeta",
    "UniqueMeta",
    "ViewMeta",
    "get_catalog_dialect",
    "register_catalog_dialect",
    "supported_catalog_engines",
]
