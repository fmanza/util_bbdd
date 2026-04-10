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


class PoolExhaustedError(PoolConnectionError):
    """Pool de conexiones agotado (sin conexiones disponibles)."""

    def __init__(
        self,
        message: str = "Pool de conexiones agotado",
        max_connections: int | None = None,
        operation: str | None = None,
        db_type: str | None = None,
    ) -> None:
        details = f"Máximo de conexiones: {max_connections}" if max_connections is not None else None
        super().__init__(message, operation=operation, db_type=db_type, details=details)
        self.max_connections = max_connections


class PoolTimeoutError(ConnectionError):
    """Timeout esperando conexión disponible del pool."""

    def __init__(
        self,
        message: str = "Timeout esperando conexión del pool",
        timeout_seconds: float | None = None,
        operation: str | None = None,
        db_type: str | None = None,
    ) -> None:
        details = f"Timeout: {timeout_seconds}s" if timeout_seconds is not None else None
        super().__init__(message, operation=operation, db_type=db_type, details=details)
        self.timeout_seconds = timeout_seconds


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


class QueryParameterError(QueryError):
    """Parámetro específico de query es inválido."""

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

    def __init__(
        self,
        message: str,
        driver_name: str | None = None,
        install_command: str | None = None,
        db_type: str | None = None,
        operation: str | None = None,
        details: str | None = None,
    ) -> None:
        self.driver_name = driver_name
        self.install_command = install_command
        extra: list[str] = []
        if driver_name:
            extra.append(f"Driver: {driver_name}")
        if install_command:
            extra.append(f"Instalar con: {install_command}")
        combined_details = " | ".join(extra) if extra else details
        super().__init__(message, operation=operation, db_type=db_type, details=combined_details)


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
    "PoolExhaustedError",
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
