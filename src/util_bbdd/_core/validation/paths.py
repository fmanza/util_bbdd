"""Validación de rutas de fichero o directorio recibidas por los puntos de entrada públicos.

v1.1.0: ``audit_csv_path``, ``rejects_csv_path``, ``path_sql``, ``output_dir`` y ``bulk_audit_path`` aceptan ``str``
además de ``Path``; hasta v1.0.0 un ``str`` fallaba con errores poco claros (``'str' object has no attribute 'parent'``)
y, en ``DumpConfig.output_dir``, después de cargar los datos.
"""

from __future__ import annotations

import os

from pathlib import Path
from typing import Any

#: Ruta aceptada por la API pública: ``str`` o cualquier ``os.PathLike[str]`` (``pathlib.Path`` incluido).
type StrPath = str | os.PathLike[str]


def validate_path(value: Any, name: str) -> Path:
    """Devuelve ``value`` como ``Path`` si es un ``str`` o un ``os.PathLike[str]``; si no, ``ValueError``.

    No resuelve la ruta ni expande ``~`` ni variables de entorno: es la misma ruta que pasa quien llama.

    Args:
        value: Ruta a validar.
        name: Nombre del parámetro, para el mensaje de error.

    Returns:
        La ruta como ``Path``.

    Raises:
        ValueError: Si ``value`` no es ``str`` ni ``os.PathLike[str]``.

    Example:
        >>> validate_path("salida/audit.csv", "audit_csv_path").name
        'audit.csv'
    """
    if isinstance(value, Path):
        return value
    if isinstance(value, str) or (isinstance(value, os.PathLike) and isinstance(os.fspath(value), str)):
        return Path(value)
    raise ValueError(f"{name} debe ser una ruta (str o Path), recibido: {type(value).__name__}")


def validate_optional_path(value: Any, name: str) -> Path | None:
    """Como :func:`validate_path`, pero ``None`` se devuelve tal cual (parámetro opcional sin indicar)."""
    return None if value is None else validate_path(value, name)
