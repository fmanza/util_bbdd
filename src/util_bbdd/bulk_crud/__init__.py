"""
bbdd bulk_crud package

Proporciona operaciones CRUD en lote con auditoría.
"""

from .audit_manager import AuditManager
from .bulk_crud import bulk_crud

BulkCrudManager = bulk_crud

__all__: list[str] = ["bulk_crud", "AuditManager", "BulkCrudManager"]
