"""Fachada legacy del validador de tipos de BD.

La implementación canónica reside en util_bbdd._drivers.validator.
Este módulo mantiene la ruta pública histórica para compatibilidad.
"""

from ._drivers.validator import (
    DatabaseTypeValidator,
    get_database_validator,
    get_db_type_info,
    get_supported_db_types,
    validate_db_type,
)

__all__: list[str] = [
    "DatabaseTypeValidator",
    "get_database_validator",
    "validate_db_type",
    "get_db_type_info",
    "get_supported_db_types",
]
