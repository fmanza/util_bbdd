"""Módulo _drivers: Abstracción e integración de drivers de bases de datos.

Este módulo centraliza:
- Validación de tipos de BD (validator.py)
- Configuración de drivers
- Selection logic para drivers

Nota: El prefijo _ indica que es interno, aunque disponible para acceso especializado.
"""

from .driver_status import DriverStatus, get_driver_status
from .driver_validator import DriverValidator
from .validator import (
    DatabaseTypeValidator,
    get_database_validator,
    get_db_type_info,
    get_supported_db_types,
    validate_db_type,
)

__all__: list[str] = [
    "DatabaseTypeValidator",
    "DriverStatus",
    "DriverValidator",
    "get_driver_status",
    "get_database_validator",
    "validate_db_type",
    "get_db_type_info",
    "get_supported_db_types",
]
