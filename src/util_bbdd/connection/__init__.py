"""Módulo de conexión: factorías centrales para crear y gestionar conexiones BD.

Proporciona abstracciones consolidadas para:
- Creación de conexiones (factory)
- Configuración de conexiones y pools (config)
- Parámetros de conexión (params, builder)
- Protocolos e interfaces (protocols)
- Cierre de conexiones (close)

Nota: Los archivos originales (connect_factory, connection_configs, etc.)
      se mantienen para compatibilidad hacia atrás. Usar archivos consolidados
      para nuevo código.
"""

# ============================================================================
# Protocolos (debe ser primero para que otros lo importen)
# ============================================================================
# ============================================================================
# Nuevos archivos consolidados (usar estos)
# ============================================================================
from .builder import build_conn_params
from .close import (
    DEFAULT_CLOSE_TIMEOUT_SECONDS,
    FORCE_CLOSE_TIMEOUT_SECONDS,
    normalize_close_mode,
    parse_close_timeout,
    run_close_operation_async,
    run_close_operation_sync,
)
from .config import (
    HSQLDBConnectionConfig,
    MariaDBConnectionConfig,
    MariaDBPoolConfig,
    MySQLConnectionConfig,
    MySQLPoolConfig,
    OracleConnectionConfig,
    OraclePoolConfig,
    PostgreSQLConnectionConfig,
    PostgreSQLPoolConfig,
    SQLiteConnectionConfig,
    SQLitePoolConfig,
    SQLServerConnectionConfig,
    SQLServerPoolConfig,
)
from .factory import ConnectionFactory
from .params import ConnectionParamsManager
from .protocols import (
    AsyncCloseMode,
    AsyncConnectionProtocol,
    AsyncPoolProtocol,
    ConnectionPoolProtocol,
)

__all__: list[str] = [
    # Consolidados - Core
    "ConnectionFactory",
    "ConnectionParamsManager",
    "build_conn_params",
    "ConnectionPoolProtocol",
    "AsyncConnectionProtocol",
    "AsyncPoolProtocol",
    "AsyncCloseMode",
    "parse_close_timeout",
    "normalize_close_mode",
    "run_close_operation_sync",
    "run_close_operation_async",
    "DEFAULT_CLOSE_TIMEOUT_SECONDS",
    "FORCE_CLOSE_TIMEOUT_SECONDS",
    # Configs
    "MariaDBConnectionConfig",
    "MariaDBPoolConfig",
    "MySQLConnectionConfig",
    "MySQLPoolConfig",
    "OracleConnectionConfig",
    "OraclePoolConfig",
    "PostgreSQLConnectionConfig",
    "PostgreSQLPoolConfig",
    "SQLiteConnectionConfig",
    "SQLitePoolConfig",
    "SQLServerConnectionConfig",
    "SQLServerPoolConfig",
    "HSQLDBConnectionConfig",
    # Advisor de rendimiento
    "EngineReadinessAdvisor",
    "EngineReadinessReport",
    "AdvisoryFinding",
]

from .performance_advisor import AdvisoryFinding, EngineReadinessAdvisor, EngineReadinessReport
