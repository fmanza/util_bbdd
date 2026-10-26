"""Módulo dump: volcado de datos entre esquemas/bases de datos.

Permite copiar datos de un esquema origen a un esquema destino (igual o distinto
motor), detectando el orden de carga óptimo por dependencias FK, gestionando
constraints y generando un informe Excel de auditoría.

Motores soportados para gestión de constraints: SQL Server, MariaDB, PostgreSQL, Oracle.

Ejemplo básico::

    from pathlib import Path
    from sqlalchemy import create_engine
    from util_bbdd.dump import DumpConfig, DumpOrchestrator

    config = DumpConfig(
        source_engine=create_engine("postgresql+psycopg2://user:pw@src/db"),
        target_engine=create_engine("mssql+pymssql://user:pw@dst/db"),
        source_schema="public",
        target_schema="dbo",
        chunk_size=10_000,
        output_dir=Path("reports"),
        truncate_target=True,
    )
    result = DumpOrchestrator(config).run()
    print(f"Informe: {result.report}")
    print(f"Tablas cargadas: {len(result.table_results)}")
"""

from .._core.exceptions import DumpConstraintError, DumpError, DumpReportError
from ._constraints import ConstraintManager, ConstraintResult, restore_constraints
from ._indexes import IndexManager
from ._models import (
    DumpAuditSummary,
    DumpConfig,
    DumpPlan,
    DumpPlanTable,
    DumpPlanWarning,
    DumpResult,
    DumpWarningCode,
    IndexActionResult,
    PKSyncResult,
    TableDumpResult,
)
from .orchestrator import DumpOrchestrator
from .reporters import DumpReporter

__all__: list[str] = [
    "ConstraintManager",
    "ConstraintResult",
    "DumpAuditSummary",
    "DumpConfig",
    "DumpConstraintError",
    "DumpError",
    "DumpOrchestrator",
    "DumpPlan",
    "DumpPlanTable",
    "DumpPlanWarning",
    "DumpReportError",
    "DumpReporter",
    "DumpResult",
    "DumpWarningCode",
    "IndexActionResult",
    "IndexManager",
    "PKSyncResult",
    "TableDumpResult",
    "restore_constraints",
]
