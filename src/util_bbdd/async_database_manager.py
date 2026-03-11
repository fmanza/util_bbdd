"""
Wrapper de compatibilidad: async_database_manager

Redirecciona a managers.async_mgr para mantener compatibilidad.

Use:
    from util_bbdd import AsyncDatabaseManager  # Funciona
    from util_bbdd.async_database_manager import AsyncDatabaseManager  # También funciona (wrapper)
    from util_bbdd.managers import AsyncDatabaseManager  # Nuevo camino
"""

# Reexporta desde el nuevo módulo
# Compatibilidad con tests que hacen patch a estos módulos
from .executors.async_query_executor import AsyncQueryExecutor
from .factory.async_sqlalchemy_engine_factory import AsyncSQLAlchemyEngineFactory
from .managers.async_mgr import AsyncDatabaseManager

__all__ = ["AsyncDatabaseManager", "AsyncQueryExecutor", "AsyncSQLAlchemyEngineFactory"]
