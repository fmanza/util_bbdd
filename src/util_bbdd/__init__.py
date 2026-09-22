"""
Módulo bbdd para operaciones de base de datos.

Soporta: MariaDB, Oracle, PostgreSQL, HSQLDB y SQL Server.
Migración DDL: Oracle → MariaDB (migrate.MigrationPlanner).
"""

from ._core.exceptions import (
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
from .comparar import (
    ComparerError,
    DiffReportGenerationError,
    MetadataIntrospectionError,
    SchemaComparator,
    SchemaDiff,
    SchemaDiffValidationError,
)
from .connection.builder import build_conn_params
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
from .metadata import AsyncMetadataProvider, DatabaseMetadataCache, RelationshipMetadataCache, SyncMetadataProvider
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
    "DatabaseMetadataCache",
    "RelationshipMetadataCache",
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
    # Migración DDL
    "MigrationPlanner",
    "MigrationPlan",
    "MigrationWarning",
    # Documentación
    "DocumentationError",
    "DocumentationConfigError",
    "DocumentationRenderError",
]
