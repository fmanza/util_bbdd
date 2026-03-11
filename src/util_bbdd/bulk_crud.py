"""
Módulo wrapper para bulk_crud - Compatibilidad hacia atrás en raíz.

Importa desde el nuevo módulo consolidado en util_bbdd.bulk
"""

from .bulk import AuditManager, BulkCrudManager, bulk_crud

__all__ = ["bulk_crud", "BulkCrudManager", "AuditManager"]
