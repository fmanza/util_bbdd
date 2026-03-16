"""
Módulo bbdd para operaciones de base de datos.

Soporta: MariaDB, Oracle, PostgreSQL, HSQLDB y SQL Server
"""

from .async_utils import maybe_await
from .connection.builder import build_conn_params
from .factory import ConnectionFactory, PoolFactory
from .managers.async_mgr import AsyncDatabaseManager
from .managers.sync_mgr import SyncDatabaseManager
from .metadata import AsyncMetadataProvider, DatabaseMetadataCache, RelationshipMetadataCache, SyncMetadataProvider

__all__: list[str] = [
    "SyncDatabaseManager",
    "AsyncDatabaseManager",
    "SyncMetadataProvider",
    "AsyncMetadataProvider",
    "maybe_await",
    "build_conn_params",
    "ConnectionFactory",
    "PoolFactory",
    "DatabaseMetadataCache",
    "RelationshipMetadataCache",
]
