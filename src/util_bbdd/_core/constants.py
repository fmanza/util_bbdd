"""Constantes y enumeraciones para util_bbdd.

Define valores constantes y enums utilizados en toda la librería
para evitar strings magic y centralizar configuración.
"""

from enum import Enum


class DatabaseType(str, Enum):
    """Tipos de bases de datos soportadas."""

    MARIADB = "mariadb"
    MYSQL = "mysql"
    ORACLE = "oracle"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    SQLSERVER = "sqlserver"
    HSQLDB = "hsqldb"

    def __str__(self) -> str:
        """Retorna valor en minúsculas."""
        return self.value


class OperationType(str, Enum):
    """Tipos de operaciones de base de datos."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CONNECT = "CONNECT"
    EXECUTE = "EXECUTE"
    CLOSE = "CLOSE"

    def __str__(self) -> str:
        """Retorna valor."""
        return self.value


class RouterineType(str, Enum):
    """Tipos de rutinas de base de datos."""

    PROCEDURE = "PROCEDURE"
    FUNCTION = "FUNCTION"

    def __str__(self) -> str:
        """Retorna valor."""
        return self.value


# Constantes de configuración
DEFAULT_POOL_SIZE: int = 5
"""Tamaño de pool por defecto."""

DEFAULT_CONNECTION_TIMEOUT: float = 30.0
"""Timeout de conexión por defecto (segundos)."""

DEFAULT_QUERY_TIMEOUT: float = 300.0
"""Timeout de query por defecto (segundos)."""

DEFAULT_CLOSE_TIMEOUT: float = 10.0
"""Timeout de cierre por defecto (segundos)."""

# Constantes de caché
DEFAULT_CACHE_MAX_SIZE: int = 1000
"""Tamaño máximo de caché por defecto."""

# Constantes de mensajes comunes
MSG_EXECUTOR_NOT_INITIALIZED: str = "Ejecutor de consultas no inicializado"
"""Mensaje cuando ejecutor no está listo."""

MSG_CONNECTION_NOT_AVAILABLE: str = "Conexión no disponible"
"""Mensaje cuando conexión no está disponible."""

MSG_INVALID_DB_TYPE: str = "Tipo de base de datos no soportado"
"""Mensaje cuando tipo de BD es inválido."""

__all__ = [
    # Enums
    "DatabaseType",
    "OperationType",
    "RouterineType",
    # Constantes
    "DEFAULT_POOL_SIZE",
    "DEFAULT_CONNECTION_TIMEOUT",
    "DEFAULT_QUERY_TIMEOUT",
    "DEFAULT_CLOSE_TIMEOUT",
    "DEFAULT_CACHE_MAX_SIZE",
    # Mensajes
    "MSG_EXECUTOR_NOT_INITIALIZED",
    "MSG_CONNECTION_NOT_AVAILABLE",
    "MSG_INVALID_DB_TYPE",
]
