"""
Database Type Validators - Factory Pattern

Exports factory function get_type_validator() to return appropriate validator
for each database motor type.
"""

import logging

from collections.abc import Callable
from functools import cache

from .base_validator import QueryParameterValidator
from .hsqldb_validator import HSQLDBValidator
from .mariadb_validator import MariaDBValidator
from .mysql_validator import MySQLValidator
from .oracle_validator import OracleValidator
from .postgresql_validator import PostgreSQLValidator
from .sqlite_validator import SQLiteValidator
from .sqlserver_validator import SQLServerValidator

logger: logging.Logger = logging.getLogger(__name__)

ValidatorFactory = Callable[[], QueryParameterValidator]
"""Fábrica de validadores concretos por tipo de base de datos."""

# Mapping de tipos de BD a sus validadores
_VALIDATOR_REGISTRY: dict[str, ValidatorFactory] = {
    "mariadb": MariaDBValidator,
    "mysql": MySQLValidator,
    "oracle": OracleValidator,
    "postgresql": PostgreSQLValidator,
    "hsqldb": HSQLDBValidator,
    "sqlserver": SQLServerValidator,
    "sqlite": SQLiteValidator,
}


@cache
def _get_cached_validator(db_type_lower: str) -> QueryParameterValidator:
    """Obtiene validador cacheado por db_type normalizado."""
    validator_factory = _VALIDATOR_REGISTRY[db_type_lower]
    validator = validator_factory()
    logger.debug(f"Created validator for db_type='{db_type_lower}' -> {validator.__class__.__name__}")
    return validator


def get_type_validator(db_type: str) -> QueryParameterValidator:
    """Factory para obtener el validador apropiado para un tipo de BD.

    Args:
        db_type: Tipo de BD ('mariadb', 'mysql', 'oracle', 'postgresql', 'hsqldb',
                 'sqlserver', 'sqlite')

    Returns:
        Instancia del validador correspondiente

    Raises:
        ValueError: Si el tipo de BD no es soportado

    Examples:
        >>> validator = get_type_validator("mariadb")
        >>> validator.db_type
        'mariadb'
        >>> isinstance(validator, QueryParameterValidator)
        True
    """
    db_type_lower: str = db_type.lower().strip()

    if db_type_lower not in _VALIDATOR_REGISTRY:
        supported: str = ", ".join(sorted(_VALIDATOR_REGISTRY.keys()))
        raise ValueError(f"Unsupported database type '{db_type}'. Supported types: {supported}")

    return _get_cached_validator(db_type_lower)


__all__ = [
    "QueryParameterValidator",
    "MariaDBValidator",
    "MySQLValidator",
    "OracleValidator",
    "PostgreSQLValidator",
    "HSQLDBValidator",
    "SQLServerValidator",
    "SQLiteValidator",
    "get_type_validator",
]
