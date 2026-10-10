"""Jerarquía pública de excepciones de util_bbdd.

Punto de importación estable de todas las excepciones de la librería (API 1.0). La implementación vive en
``util_bbdd._core.exceptions``; este módulo solo la reexporta. Todas heredan de :class:`DatabaseException`, la única
que se exporta también desde la raíz ``util_bbdd``.

Example:
    >>> from util_bbdd.exceptions import DatabaseException, QueryNotFoundError
    >>> issubclass(QueryNotFoundError, DatabaseException)
    True
"""

from ._core.exceptions import (
    AuditConfigError,
    AuditDataError,
    AuditError,
    AuditExportError,
    AuditFileError,
    AuditValidationError,
    ComparerError,
    ConnectionError,
    DatabaseConfigurationError,
    DatabaseException,
    DatabaseOperationError,
    DDLBuildError,
    DiffReportGenerationError,
    DocumentationConfigError,
    DocumentationError,
    DocumentationRenderError,
    DriverConfigurationError,
    DriverError,
    DriverNotFoundError,
    DumpConstraintError,
    DumpError,
    DumpReportError,
    InvalidConnectionConfig,
    InvalidDatabaseType,
    InvalidQueryParameters,
    MetadataError,
    MetadataFetchError,
    MetadataIntrospectionError,
    MetadataNormalizationError,
    PoolConnectionError,
    PoolExhaustedError,
    PoolTimeoutError,
    QueryError,
    QueryExecutionError,
    QueryNotFoundError,
    QueryParameterError,
    QueryTimeoutError,
    QueryValidationError,
    SchemaDiffValidationError,
    ValidationError,
)

__all__: list[str] = [
    # Base
    "DatabaseException",
    # Conexión
    "ConnectionError",
    "PoolConnectionError",
    "PoolExhaustedError",
    "PoolTimeoutError",
    # Query
    "QueryError",
    "QueryTimeoutError",
    "QueryExecutionError",
    "QueryNotFoundError",
    "QueryValidationError",
    "QueryParameterError",
    # Metadatos
    "MetadataError",
    "MetadataFetchError",
    "MetadataNormalizationError",
    "DDLBuildError",
    # Validación
    "ValidationError",
    "InvalidDatabaseType",
    "InvalidConnectionConfig",
    "InvalidQueryParameters",
    # Drivers
    "DriverError",
    "DriverNotFoundError",
    "DriverConfigurationError",
    # Genéricos
    "DatabaseOperationError",
    "DatabaseConfigurationError",
    # Comparación de esquemas
    "ComparerError",
    "SchemaDiffValidationError",
    "MetadataIntrospectionError",
    "DiffReportGenerationError",
    # Documentación
    "DocumentationError",
    "DocumentationConfigError",
    "DocumentationRenderError",
    # Volcado de datos
    "DumpError",
    "DumpConstraintError",
    "DumpReportError",
    # Auditoría
    "AuditError",
    "AuditConfigError",
    "AuditFileError",
    "AuditDataError",
    "AuditExportError",
    "AuditValidationError",
]
