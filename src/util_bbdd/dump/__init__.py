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

from ._constraints import ConstraintManager, ConstraintResult
from ._models import DumpConfig, DumpResult, TableDumpResult
from ._protocols import BulkInserter
from .orchestrator import DumpOrchestrator
from .reporters import DumpReporter

__all__: list[str] = [
    "BulkInserter",
    "ConstraintManager",
    "ConstraintResult",
    "DumpConfig",
    "DumpOrchestrator",
    "DumpReporter",
    "DumpResult",
    "TableDumpResult",
]
