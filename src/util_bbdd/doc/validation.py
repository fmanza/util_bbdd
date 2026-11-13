"""Validación previa de las entradas de la documentación Markdown, sin conectar a la base de datos (5.7.0).

Pensada para quien recibe el fichero antes de generar (p. ej. una aplicación web al subirlo): aplica exactamente las
mismas reglas que :class:`~util_bbdd.doc.DatabaseDocumentation` al construirse con ``imprimir["markdown"]["trace_map"]``.
"""

from __future__ import annotations

import os

from .infrastructure.renderers.markdown._trace import TraceMap


def validate_trace_map(path: str | os.PathLike[str]) -> None:
    """Valida un mapa de trazabilidad (``.toml`` o ``.json``) sin conectar a la base de datos.

    Las reglas son las de ``imprimir["markdown"]["trace_map"]`` (esquema estricto: un campo desconocido es error) y
    los errores del contenido se informan todos juntos. Los mensajes nombran el fichero, nunca su ruta.

    Args:
        path: Ruta del mapa de trazabilidad.

    Raises:
        DocumentationConfigError: Extensión no admitida, fichero ilegible, mayor de 1 MB, con sintaxis inválida o
            con contenido que no sigue el esquema.

    Example:
        >>> from util_bbdd.doc import validate_trace_map
        >>> from util_bbdd.exceptions import DocumentationConfigError
        >>> try:
        ...     validate_trace_map("trazas.toml")  # no devuelve nada si es válido
        ... except DocumentationConfigError as error:
        ...     print(error)
    """
    TraceMap.load(path)


__all__: list[str] = ["validate_trace_map"]
