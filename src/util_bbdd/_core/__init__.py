"""Módulo _core: Abstracciones internas y tipos comunes.

Este módulo centraliza:
- Tipos y type aliases (types.py)
- Excepciones (exceptions.py)
- Protocols/interfaces (contracts.py)
- Constantes y enums (constants.py)

Nota: El prefijo _ indica que es interno (no parte del API público oficial),
      aunque está disponible para acceso especializado.
"""

# Importaciones desde tipos
# Importaciones desde constantes
from .constants import (
    DEFAULT_CACHE_MAX_SIZE,
    DEFAULT_CLOSE_TIMEOUT,
    DEFAULT_CONNECTION_TIMEOUT,
    DEFAULT_POOL_SIZE,
    DEFAULT_QUERY_TIMEOUT,
    MSG_CONNECTION_NOT_AVAILABLE,
    MSG_EXECUTOR_NOT_INITIALIZED,
    MSG_INVALID_DB_TYPE,
    OperationType,
    RouterineType,
)

# Importaciones desde contracts
from .contracts import (
    ConnectionProvider as ConnectionProviderProtocol,
    ConnectionReleaser as ConnectionReleaserProtocol,
    DatabaseValidator,
    MetadataFetcher,
    PoolConnection,
    QueryExecutor,
)

# Importaciones desde excepciones
from .exceptions import (
    ConnectionError,
    DatabaseConfigurationError,
    DatabaseException,
    DatabaseOperationError,
    DDLBuildError,
    DriverConfigurationError,
    DriverError,
    DriverNotFoundError,
    InvalidConnectionConfig,
    InvalidDatabaseType,
    InvalidQueryParameters,
    MetadataError,
    MetadataFetchError,
    MetadataNormalizationError,
    PoolConnectionError,
    PoolTimeoutError,
    QueryError,
    QueryExecutionError,
    QueryNotFoundError,
    QueryTimeoutError,
    QueryValidationError,
    ValidationError,
)
from .types import (
    ConnectionConfig,
    ConnectionID,
    ConnectionProvider,
    ConnectionReleaser,
    DDLStatement,
    QueryParams,
    RowOrNone,
    Rows,
    SchemaContext,
)

__all__ = [
    # Tipos
    "RowOrNone",
    "Rows",
    "SchemaContext",
    "DDLStatement",
    "QueryParams",
    "ConnectionConfig",
    "ConnectionID",
    "ConnectionProvider",
    "ConnectionReleaser",
    # Excepciones
    "DatabaseException",
    "ConnectionError",
    "PoolConnectionError",
    "PoolTimeoutError",
    "QueryError",
    "QueryTimeoutError",
    "QueryExecutionError",
    "QueryNotFoundError",
    "QueryValidationError",
    "MetadataError",
    "MetadataFetchError",
    "MetadataNormalizationError",
    "DDLBuildError",
    "ValidationError",
    "InvalidDatabaseType",
    "InvalidConnectionConfig",
    "InvalidQueryParameters",
    "DriverError",
    "DriverNotFoundError",
    "DriverConfigurationError",
    "DatabaseOperationError",
    "DatabaseConfigurationError",
    # Protocols
    "ConnectionProviderProtocol",
    "ConnectionReleaserProtocol",
    "QueryExecutor",
    "PoolConnection",
    "DatabaseValidator",
    "MetadataFetcher",
    # Constantes y enums
    "DatabaseType",
    "OperationType",
    "RouterineType",
    "DEFAULT_POOL_SIZE",
    "DEFAULT_CONNECTION_TIMEOUT",
    "DEFAULT_QUERY_TIMEOUT",
    "DEFAULT_CLOSE_TIMEOUT",
    "DEFAULT_CACHE_MAX_SIZE",
    "MSG_EXECUTOR_NOT_INITIALIZED",
    "MSG_CONNECTION_NOT_AVAILABLE",
    "MSG_INVALID_DB_TYPE",
]
