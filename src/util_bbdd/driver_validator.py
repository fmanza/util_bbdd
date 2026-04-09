"""Fachada legacy del validador de drivers.

La implementación canónica reside en util_bbdd._foundation.driver_validator.
Este módulo mantiene la ruta pública histórica para compatibilidad.
"""

from ._foundation.driver_validator import DriverValidator

__all__: list[str] = [
    "DriverValidator",
]
