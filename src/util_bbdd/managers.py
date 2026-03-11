"""
Wrapper raíz: managers

Proporciona acceso conveniente a la nueva estructura de managers.

Use:
    from util_bbdd.managers import DatabaseManager, AsyncDatabaseManager
    from util_bbdd import DatabaseManager, AsyncDatabaseManager  # También funciona
"""

from .managers import AsyncDatabaseManager, DatabaseManager

__all__ = ["DatabaseManager", "AsyncDatabaseManager"]
