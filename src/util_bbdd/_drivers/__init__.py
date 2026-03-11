"""Módulo _drivers: Abstracción e integración de drivers de bases de datos.

Este módulo centraliza:
- Validación de tipos de BD (validator.py)
- Configuración de drivers
- Selection logic para drivers

Nota: El prefijo _ indica que es interno, aunque disponible para acceso especializado.
"""

from .validator import DatabaseTypeValidator

__all__: list[str] = [
    "DatabaseTypeValidator",
]
