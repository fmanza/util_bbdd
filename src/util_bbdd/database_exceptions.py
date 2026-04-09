"""Fachada legacy de excepciones de base de datos.

La implementación canónica reside en util_bbdd._foundation.exceptions.
Este módulo mantiene la ruta pública histórica para compatibilidad.
"""

from ._foundation.exceptions import (
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

__all__: list[str] = [
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
]
