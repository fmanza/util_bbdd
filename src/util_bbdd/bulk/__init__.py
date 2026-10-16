"""Módulo bulk: Operaciones CRUD en lote con auditoría.

Proporciona operaciones INSERT, UPDATE y DELETE en lote desde DataFrames de pandas
con auditoría integrada y soporte multi-BD.

Consolidación de:
- crud.py - Clase bulk_crud para operaciones CRUD en lote
- audit.py - AuditManager para gestión de auditoría
- normalize.py - Funciones de normalización de datos para SQL
"""

from ._execution.parallel_loader import ParallelBulkLoader, ParallelLoadResult, PartitionResult
from ._execution.parallel_planner import ParallelPlan, ParallelPlanner, ParallelRule, PlanInput
from ._execution.range_partitioner import HashPartitioner, RangePartitioner
from ._models import MaintenanceScopeConstraintResult, MaintenanceScopeResult, PKSyncResult
from ._support.auto_increment import UpdateAutoIncrement
from .audit import AuditError, AuditManager
from .crud import BulkCrud
from .normalize import normalize_records_for_sql, normalize_sql_literal
from .options import (
    AuditOptions,
    BatchOptions,
    BulkOptions,
    ExecutionOptions,
    ParallelMode,
    ParallelOptions,
    RejectOptions,
    RetryOptions,
)

__all__: list[str] = [
    "UpdateAutoIncrement",
    # Clase CRUD principal
    "BulkCrud",
    # Paquetes de opciones de BulkCrud y ParallelBulkLoader (v3.0.0)
    "AuditOptions",
    "BatchOptions",
    "BulkOptions",
    "ExecutionOptions",
    "ParallelMode",
    "ParallelOptions",
    "RejectOptions",
    "RetryOptions",
    # Carga masiva paralela por particiones
    "ParallelBulkLoader",
    "ParallelLoadResult",
    "PartitionResult",
    # Planificador de la carga paralela (v3.0.0)
    "ParallelPlan",
    "ParallelPlanner",
    "ParallelRule",
    "PlanInput",
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
