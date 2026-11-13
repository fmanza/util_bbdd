"""Documentación de bases de datos en Word, Excel, HTML y Markdown.

API pública: :class:`DatabaseDocumentation`, su resultado (:class:`DocumentationResult`) y, desde 5.7.0,
:func:`validate_trace_map` (valida un mapa de trazabilidad sin conectar). Los generadores por formato
(``infrastructure/renderers``) son internos desde 0.41.0: se eligen con ``formatos=[...]``.
"""

from .database_documentation import DatabaseDocumentation
from .domain.models import DocumentationResult
from .validation import validate_trace_map

__all__: list[str] = ["DatabaseDocumentation", "DocumentationResult", "validate_trace_map"]
