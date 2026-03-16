"""Módulo managers: Gestor de operaciones de base de datos.

Proporciona gestor de conexiones, queries y operaciones para bases de datos
con interfaces sync y async.

Consolidación de:
- sync_mgr.py (database_manager.py) - Gestor síncrono de base de datos
- async_mgr.py (async_database_manager.py) - Gestor asíncrono de base de datos
"""

from .async_mgr import AsyncDatabaseManager
from .sync_mgr import SyncDatabaseManager

__all__: list[str] = [
    # Managers
    "SyncDatabaseManager",
    "AsyncDatabaseManager",
]
