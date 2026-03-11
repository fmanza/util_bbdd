"""
Wrapper de compatibilidad: database_manager

Redirecciona a managers.sync para mantener compatibilidad.

Use:
    from util_bbdd import DatabaseManager  # Funciona
    from util_bbdd.database_manager import DatabaseManager  # También funciona (wrapper)
    from util_bbdd.managers import DatabaseManager  # Nuevo camino
"""

# Reexporta desde el nuevo módulo
from .managers.sync import DatabaseManager

__all__ = ["DatabaseManager"]
