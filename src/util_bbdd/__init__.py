"""
Módulo bbdd para operaciones de base de datos.

Soporta: MariaDB, Oracle, PostgreSQL, HSQLDB y SQL Server.
Migración DDL: Oracle → MariaDB (migrate.MigrationPlanner).
"""

from ._core.exceptions import (
    AuditConfigError,
    AuditDataError,
    AuditError,
    AuditExportError,
    AuditFileError,
    AuditValidationError,
    ConnectionError,
    DatabaseConfigurationError,
    DatabaseException,
    DatabaseOperationError,
    DocumentationConfigError,
    DocumentationError,
    DocumentationRenderError,
    DriverError,
    InvalidDatabaseType,
    PoolConnectionError,
    PoolExhaustedError,
    PoolTimeoutError,
    QueryError,
    QueryExecutionError,
    QueryNotFoundError,
    QueryParameterError,
    QueryTimeoutError,
    QueryValidationError,
    ValidationError,
)
from .async_utils import maybe_await
from .audit import AuditEvent, AuditSink, JsonLinesAuditSink, MemoryAuditSink, NullAuditSink
from .comparar import (
    ComparerError,
    DiffReportGenerationError,
    MetadataIntrospectionError,
    SchemaComparator,
    SchemaDiff,
    SchemaDiffValidationError,
)
from .connection.builder import build_conn_params
from .connection.performance_advisor import AdvisoryFinding, EngineReadinessAdvisor
from .dump import (
    DumpConfig,
    DumpConstraintError,
    DumpError,
    DumpOrchestrator,
    DumpReportError,
    DumpResult,
    TableDumpResult,
)
from .factory import ConnectionFactory, PoolFactory
from .managers.async_mgr import AsyncDatabaseManager
from .managers.sync_mgr import SyncDatabaseManager
from .metadata import AsyncMetadataProvider, SyncMetadataProvider
from .migrate import MigrationPlan, MigrationPlanner, MigrationWarning

__all__: list[str] = [
    "SyncDatabaseManager",
    "AsyncDatabaseManager",
    "SyncMetadataProvider",
    "AsyncMetadataProvider",
    "maybe_await",
    "build_conn_params",
    "ConnectionFactory",
    "PoolFactory",
    "SchemaComparator",
    "SchemaDiff",
    # Excepciones de comparar/
    "ComparerError",
    "SchemaDiffValidationError",
    "MetadataIntrospectionError",
    "DiffReportGenerationError",
    # Excepciones canónicas
    "DatabaseException",
    "ConnectionError",
    "PoolConnectionError",
    "PoolExhaustedError",
    "PoolTimeoutError",
    "DriverError",
    "ValidationError",
    "InvalidDatabaseType",
    "DatabaseOperationError",
    "DatabaseConfigurationError",
    "QueryError",
    "QueryNotFoundError",
    "QueryValidationError",
    "QueryParameterError",
    "QueryTimeoutError",
    "QueryExecutionError",
    # Volcado de datos
    "DumpOrchestrator",
    "DumpConfig",
    "DumpResult",
    "TableDumpResult",
    "DumpError",
    "DumpConstraintError",
    "DumpReportError",
    # Auditoría centralizada (util_bbdd.audit, sesión 2026-10-02c)
    "AuditEvent",
    "AuditSink",
    "JsonLinesAuditSink",
    "MemoryAuditSink",
    "NullAuditSink",
    # Auditoría de bulk
    "AuditError",
    "AuditConfigError",
    "AuditFileError",
    "AuditDataError",
    "AuditExportError",
    "AuditValidationError",
    # Migración DDL
    "MigrationPlanner",
    "MigrationPlan",
    "MigrationWarning",
    # Verificador de condiciones de ejecución por motor
    "EngineReadinessAdvisor",
    "AdvisoryFinding",
    # Documentación
    "DocumentationError",
    "DocumentationConfigError",
    "DocumentationRenderError",
]
