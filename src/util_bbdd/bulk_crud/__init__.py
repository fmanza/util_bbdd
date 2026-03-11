"""
bbdd bulk_crud package - Wrapper para compatibilidad hacia atrás.

Importa desde el nuevo módulo consolidado en util_bbdd.bulk
"""

from ..bulk import AuditManager, BulkCrudManager, bulk_crud

__all__: list[str] = ["bulk_crud", "AuditManager", "BulkCrudManager"]
