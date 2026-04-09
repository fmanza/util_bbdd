"""Módulo bulk: Operaciones CRUD en lote con auditoría.

Proporciona operaciones INSERT, UPDATE y DELETE en lote desde DataFrames de pandas
con auditoría integrada y soporte multi-BD.

Consolidación de:
- crud.py - Clase bulk_crud para operaciones CRUD en lote
- audit.py - AuditManager para gestión de auditoría
- normalize.py - Funciones de normalización de datos para SQL
"""

from .audit import AuditError, AuditManager, AuditTransaction
from .crud import bulk_crud
from .normalize import normalize_records_for_sql, normalize_sql_literal

__all__: list[str] = [
    # Clase CRUD principal
    "bulk_crud",
    # Auditoría
    "AuditManager",
    "AuditTransaction",
    "AuditError",
    # Normalización
    "normalize_records_for_sql",
    "normalize_sql_literal",
]
