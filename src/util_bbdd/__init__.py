"""
Módulo bbdd para operaciones de base de datos.

Soporta: MariaDB, Oracle, PostgreSQL, HSQLDB y SQL Server
"""

from .connection.conn_params_builder import build_conn_params
from .database_manager import DatabaseManager
from .factory import ConnectFactory, PoolFactory
from .metadata_cache import DatabaseMetadataCache, RelationshipMetadataCache

__all__: list[str] = [
    "DatabaseManager",
    "build_conn_params",
    "ConnectFactory",
    "PoolFactory",
    "DatabaseMetadataCache",
    "RelationshipMetadataCache",
]
