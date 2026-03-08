"""
Excepciones personalizadas para el módulo de manejo de bases de datos
"""


class DatabaseError(Exception):
    """Excepción base para errores relacionados con bases de datos"""

    def __init__(self, message: str, db_type: str | None = None, details: str | None = None):
        """
        Inicializa la excepción de base de datos

        Args:
            message: Mensaje de error principal
            db_type: Tipo de base de datos (opcional)
            details: Detalles adicionales del error (opcional)
        """
        self.message: str = message
        self.db_type: str | None = db_type
        self.details: str | None = details
        full_message: str = f"{message}"
        if db_type:
            full_message += f" (BD: {db_type})"
        if details:
            full_message += f"\nDetalles: {details}"
        super().__init__(full_message)

    def __str__(self) -> str:
        return self.args[0] if self.args else self.message


class DatabaseConnectionError(DatabaseError):
    """Excepción para errores de conexión a la base de datos"""

    pass


class DatabasePoolError(DatabaseError):
    """Excepción para errores del pool de conexiones"""

    pass


class DatabasePoolExhaustedError(DatabasePoolError):
    """Excepción cuando el pool de conexiones está agotado"""

    def __init__(
        self,
        message: str = "Pool de conexiones agotado",
        max_connections: int | None = None,
        db_type: str | None = None,
    ):
        """
        Inicializa la excepción de pool agotado

        Args:
            message: Mensaje de error
            max_connections: Número máximo de conexiones en el pool
            db_type: Tipo de base de datos
        """
        details = f"Máximo de conexiones: {max_connections}" if max_connections else None
        super().__init__(message, db_type, details)


class DatabasePoolTimeoutError(DatabasePoolError):
    """Excepción cuando se agota el timeout esperando una conexión del pool"""

    def __init__(
        self,
        message: str = "Timeout esperando conexión del pool",
        timeout_seconds: float | None = None,
        db_type: str | None = None,
    ):
        """
        Inicializa la excepción de timeout del pool

        Args:
            message: Mensaje de error
            timeout_seconds: Segundos de timeout
            db_type: Tipo de base de datos
        """
        details = f"Timeout: {timeout_seconds}s" if timeout_seconds else None
        super().__init__(message, db_type, details)


class DatabaseDriverError(DatabaseError):
    """Excepción para errores relacionados con drivers de base de datos"""

    def __init__(
        self,
        message: str,
        driver_name: str | None = None,
        install_command: str | None = None,
        db_type: str | None = None,
    ):
        """
        Inicializa la excepción de driver

        Args:
            message: Mensaje de error
            driver_name: Nombre del driver
            install_command: Comando para instalar el driver
            db_type: Tipo de base de datos
        """
        self.driver_name = driver_name
        self.install_command = install_command
        full_message = message
        if driver_name:
            full_message += f"\nDriver: {driver_name}"
        if install_command:
            full_message += f"\nInstalar con: {install_command}"
        super().__init__(full_message, db_type)


class DatabaseValidationError(DatabaseError):
    """Excepción para errores de validación de parámetros de base de datos"""

    pass


class DatabaseOperationError(DatabaseError):
    """Excepción para errores durante operaciones de base de datos"""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        table_name: str | None = None,
        db_type: str | None = None,
    ):
        """
        Inicializa la excepción de operación

        Args:
            message: Mensaje de error
            operation: Tipo de operación (SELECT, INSERT, UPDATE, DELETE)
            table_name: Nombre de la tabla
            db_type: Tipo de base de datos
        """
        self.operation = operation
        self.table_name = table_name
        details = ""
        if operation:
            details += f"Operación: {operation}"
        if table_name:
            if details:
                details += f" | Tabla: {table_name}"
            else:
                details += f"Tabla: {table_name}"
        super().__init__(message, db_type, details if details else None)


class DatabaseConfigurationError(DatabaseError):
    """Excepción para errores de configuración de base de datos"""

    pass


# ============================================================================
# Query-related exceptions (NEW in v0.2.0)
# ============================================================================


class QueryError(DatabaseError):
    """Base para errores de resolución y ejecución de queries"""

    pass


class QueryNotFoundError(QueryError):
    """Query no existe en registry"""

    pass


class QueryValidationError(QueryError):
    """Validación de parámetros de query falló"""

    pass


class QueryParameterError(QueryError):
    """Parámetro específico de query es inválido"""

    pass


class QueryTimeoutError(QueryError):
    """Ejecución de query excedió timeout"""

    pass


class DatabaseTypeNotSupportedError(DatabaseError):
    """Tipo de BD no soportado o no reconocido"""

    pass


# ============================================================================
# Backward compatibility aliases (DEPRECATED)
# ============================================================================

# Alias deprecated: DatabaseQueryError -> QueryNotFoundError
# Mantiene compatibilidad con código legado
DatabaseQueryError = QueryNotFoundError
