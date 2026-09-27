"""Módulo bulk: Operaciones CRUD en lote con auditoría.

Proporciona operaciones INSERT, UPDATE y DELETE en lote desde DataFrames de pandas
con auditoría integrada y soporte multi-BD.

Consolidación de:
- crud.py - Clase bulk_crud para operaciones CRUD en lote
- audit.py - AuditManager para gestión de auditoría
- normalize.py - Funciones de normalización de datos para SQL
"""

from ._execution.parallel_loader import ParallelBulkLoader, ParallelLoadResult, PartitionResult
from ._execution.range_partitioner import HashPartitioner, RangePartitioner
from ._models import MaintenanceScopeConstraintResult, MaintenanceScopeResult, PKSyncResult
from .audit import AuditError, AuditManager
from .crud import BulkCrud
from .normalize import normalize_records_for_sql, normalize_sql_literal

__all__: list[str] = [
    # Clase CRUD principal
    "BulkCrud",
    # Carga masiva paralela por particiones
    "ParallelBulkLoader",
    "ParallelLoadResult",
    "PartitionResult",
    # Particionamiento para cargas masivas
    "HashPartitioner",
    "RangePartitioner",
    # Resultados de sync PK
    "PKSyncResult",
    # Resultados de maintenance_scope
    "MaintenanceScopeConstraintResult",
    "MaintenanceScopeResult",
    # Auditoría
    "AuditManager",
    "AuditError",
    # Normalización
    "normalize_records_for_sql",
    "normalize_sql_literal",
]
