"""Jerarquía centralizada de excepciones para util_bbdd.

Proporciona excepciones organizadas por categoría de error:
- ConnectionError: Errores de conexión y pool
- QueryError: Errores en ejecución de queries
- MetadataError: Errores en operaciones de metadatos
- ValidationError: Errores de validación
- DriverError: Errores de drivers
"""


class DatabaseException(Exception):
    """Excepción base para todas las excepciones de util_bbdd."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        db_type: str | None = None,
        details: str | None = None,
    ) -> None:
        """Inicializa excepción con contexto de operación.

        Args:
            message: Mensaje de error principal
            operation: Tipo de operación (SELECT, INSERT, CONNECT, etc.)
            db_type: Tipo de base de datos (mariadb, oracle, etc.)
            details: Detalles adicionales del error
        """
        self.message: str = message
        self.operation: str = operation or "UNKNOWN"
        self.db_type: str = db_type or "UNKNOWN"
        self.details: str | None = details

        formatted_msg: str = f"{message}"
        if operation:
            formatted_msg += f" (Operación: {operation})"
        if db_type:
            formatted_msg += f" (BD: {db_type})"
        if details:
            formatted_msg += f" - {details}"

        super().__init__(formatted_msg)


# ============================================================================
# Categoría 1: Errores de Conexión y Pool
# ============================================================================


class ConnectionError(DatabaseException):
    """Error en conexión a base de datos."""

    pass


class PoolConnectionError(ConnectionError):
    """Error obteniendo/devolviendo conexión del pool."""

    pass


class PoolTimeoutError(ConnectionError):
    """Timeout esperando conexión disponible del pool."""

    pass


# ============================================================================
# Categoría 2: Errores en Ejecución de Queries
# ============================================================================


class QueryError(DatabaseException):
    """Error en ejecución de query."""

    pass


class QueryTimeoutError(QueryError):
    """Query excedió timeout permitido."""

    pass


class QueryExecutionError(QueryError):
    """Error durante ejecución de query."""

    pass


class QueryNotFoundError(QueryError):
    """Query no encontrada en el registry."""

    pass


class QueryValidationError(QueryError):
    """Error validando parámetros de query."""

    pass


# ============================================================================
# Categoría 3: Errores en Operaciones de Metadatos
# ============================================================================


class MetadataError(DatabaseException):
    """Error en operación de metadatos."""

    pass


class MetadataFetchError(MetadataError):
    """Error obteniendo metadatos."""

    pass


class MetadataNormalizationError(MetadataError):
    """Error normalizando metadatos."""

    pass


class DDLBuildError(MetadataError):
    """Error constructuyendo sentencia DDL."""

    pass


# ============================================================================
# Categoría 4: Errores de Validación
# ============================================================================


class ValidationError(DatabaseException):
    """Error de validación."""

    pass


class InvalidDatabaseType(ValidationError):
    """Tipo de base de datos no válido o no soportado."""

    pass


class InvalidConnectionConfig(ValidationError):
    """Configuración de conexión inválida."""

    pass


class InvalidQueryParameters(ValidationError):
    """Parámetros de query inválidos."""

    pass


# ============================================================================
# Categoría 5: Errores de Drivers
# ============================================================================


class DriverError(DatabaseException):
    """Error relacionado con drivers."""

    pass


class DriverNotFoundError(DriverError):
    """Driver requerido no está instalado."""

    pass


class DriverConfigurationError(DriverError):
    """Error configurando driver."""

    pass


# ============================================================================
# Errores Específicos de Operaciones
# ============================================================================


class DatabaseOperationError(DatabaseException):
    """Error genérico en operación de base de datos."""

    pass


class DatabaseConfigurationError(DatabaseException):
    """Error en configuración de SyncDatabaseManager."""

    pass


__all__ = [
    # Base
    "DatabaseException",
    # Conexión
    "ConnectionError",
    "PoolConnectionError",
    "PoolTimeoutError",
    # Query
    "QueryError",
    "QueryTimeoutError",
    "QueryExecutionError",
    "QueryNotFoundError",
    "QueryValidationError",
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
]
