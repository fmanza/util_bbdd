"""Documentación de bases de datos en Word, Excel y HTML.

API pública: :class:`DatabaseDocumentation` y su resultado, :class:`DocumentationResult`. Los generadores por formato
(``infrastructure/renderers``) son internos desde 0.41.0: se eligen con ``formatos=[...]``.
"""

from .database_documentation import DatabaseDocumentation
from .domain.models import DocumentationResult

__all__: list[str] = ["DatabaseDocumentation", "DocumentationResult"]
