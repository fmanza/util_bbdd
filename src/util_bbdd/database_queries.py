"""Fachada legacy del manejador unificado de consultas de base de datos.

La implementación canónica reside en util_bbdd._foundation.queries.
Este módulo mantiene la ruta pública histórica para compatibilidad.
"""

from ._foundation.queries import DatabaseQueries

__all__: list[str] = [
    "DatabaseQueries",
]
