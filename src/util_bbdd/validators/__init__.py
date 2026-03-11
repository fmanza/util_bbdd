"""
Database Type Validators - Factory Pattern

Exports factory function get_type_validator() to return appropriate validator
for each database motor type.
"""

import logging

from .base_validator import DatabaseTypeValidator
from .hsqldb_validator import HSQLDBValidator
from .mariadb_validator import MariaDBValidator
from .oracle_validator import OracleValidator
from .postgresql_validator import PostgreSQLValidator
from .sqlite_validator import SQLiteValidator
from .sqlserver_validator import SQLServerValidator

logger: logging.Logger = logging.getLogger(__name__)

# Mapping de tipos de BD a sus validadores
_VALIDATOR_REGISTRY = {
    "mariadb": MariaDBValidator,
    "oracle": OracleValidator,
    "postgresql": PostgreSQLValidator,
    "hsqldb": HSQLDBValidator,
    "sqlserver": SQLServerValidator,
    "sqlite": SQLiteValidator,
}


def get_type_validator(db_type: str) -> DatabaseTypeValidator:
    """Factory para obtener el validador apropiado para un tipo de BD.

    Args:
        db_type: Tipo de BD ('mariadb', 'oracle', 'postgresql', 'hsqldb',
                 'sqlserver', 'sqlite')

    Returns:
        Instancia del validador correspondiente

    Raises:
        ValueError: Si el tipo de BD no es soportado

    Examples:
        >>> validator = get_type_validator("mariadb")
        >>> validator.db_type
        'mariadb'
        >>> isinstance(validator, DatabaseTypeValidator)
        True
    """
    db_type_lower: str = db_type.lower()

    if db_type_lower not in _VALIDATOR_REGISTRY:
        supported: str = ", ".join(sorted(_VALIDATOR_REGISTRY.keys()))
        raise ValueError(f"Unsupported database type '{db_type}'. Supported types: {supported}")

    validator_class = _VALIDATOR_REGISTRY[db_type_lower]
    validator = validator_class()

    logger.debug(f"Created validator for db_type='{db_type}' -> {validator.__class__.__name__}")
    return validator


__all__ = [
    "DatabaseTypeValidator",
    "MariaDBValidator",
    "OracleValidator",
    "PostgreSQLValidator",
    "HSQLDBValidator",
    "SQLServerValidator",
    "SQLiteValidator",
    "get_type_validator",
]
