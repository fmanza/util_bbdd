"""Metadatos de base de datos: único punto de lectura del catálogo (ADR-003).

- ``source`` / ``model``: ``CatalogSource`` lee cada tipo de objeto con una consulta por schema y devuelve un
  ``SchemaSnapshot`` inmutable de modelos neutros.
- ``catalog_registry`` y ``<motor>/catalog.py``: SQL de catálogo por motor (``CatalogDialect``).
- ``reflection``: tipos y objetos de SQLAlchemy por lotes (``comparar``, ``dump``, ``bulk``).
- ``facts``, ``ddl``, ``storage``: consultas puntuales, DDL e inventario de almacenamiento.
"""

# Lectura por lotes (ADR-003)
from ._adaptive_executor import AdaptiveCatalogExecutor
from ._charset_detection import (
    CharsetDiagnosis,
    CharsetState,
    CharsetStateDetector,
)
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
from .snapshot_cache import SnapshotCache
from .source import AsyncCatalogSource, CatalogSource, SqlAlchemyCatalogExecutor

__all__: list[str] = [
    # Contracts
    "Row",
    "Rows",
    "SyncMetadataProvider",
    "AsyncMetadataProvider",
    # Lectura por lotes (ADR-003)
    "ALL_KINDS",
    "AdaptiveCatalogExecutor",
    "AsyncCatalogExecutor",
    "AsyncCatalogSource",
    "AsyncMetadataSource",
    "CatalogDialect",
    "CatalogDialectNotFoundError",
    "CatalogExecutor",
    "CatalogQuery",
    "CatalogSource",
    "CharsetDiagnosis",
    "CharsetState",
    "CharsetStateDetector",
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
