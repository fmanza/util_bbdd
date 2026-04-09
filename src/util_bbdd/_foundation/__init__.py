"""Base de datos - módulo foundation para excepciones, validadores y queries core."""

from .driver_validator import DriverValidator
from .exceptions import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseDriverError,
    DatabaseError,
    DatabaseOperationError,
    DatabasePoolError,
    DatabasePoolExhaustedError,
    DatabasePoolTimeoutError,
    DatabaseTypeNotSupportedError,
    DatabaseValidationError,
    InvalidQueryError,
    QueryError,
    QueryExecutionError,
    QueryExecutionTimeoutError,
    QueryNotFoundError,
    QueryParameterError,
    QueryTimeoutError,
    QueryValidationError,
    UtilBbddError,
)
from .queries import DatabaseQueries
from .validators_core import (
    DatabaseTypeValidator,
    get_database_validator,
    get_db_type_info,
    get_supported_db_types,
    validate_db_type,
)

__all__: list[str] = [
    # Exceptions
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabasePoolError",
    "DatabasePoolExhaustedError",
    "DatabasePoolTimeoutError",
    "DatabaseDriverError",
    "DatabaseValidationError",
    "DatabaseOperationError",
    "DatabaseConfigurationError",
    "QueryError",
    "QueryNotFoundError",
    "QueryValidationError",
    "QueryParameterError",
    "QueryTimeoutError",
    "DatabaseTypeNotSupportedError",
    "UtilBbddError",
    "QueryExecutionError",
    "InvalidQueryError",
    "QueryExecutionTimeoutError",
    # Validators
    "DatabaseTypeValidator",
    "get_database_validator",
    "validate_db_type",
    "get_db_type_info",
    "get_supported_db_types",
    # Driver validator
    "DriverValidator",
    # Queries
    "DatabaseQueries",
]
