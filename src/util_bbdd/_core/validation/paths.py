"""Validación de rutas de fichero o directorio recibidas por los puntos de entrada públicos.

v1.1.0: ``audit_csv_path``, ``rejects_csv_path``, ``path_sql``, ``output_dir`` y ``bulk_audit_path`` aceptan ``str``
además de ``Path``; hasta v1.0.0 un ``str`` fallaba con errores poco claros (``'str' object has no attribute 'parent'``)
y, en ``DumpConfig.output_dir``, después de cargar los datos.
"""

from __future__ import annotations

import os

from pathlib import Path
from typing import Any, overload

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


class PathField:
    """Campo de dataclass que acepta ``str`` o ``os.PathLike[str]`` al asignarse y se lee siempre como ``Path``.

    T-09 (tech-debt 2026-10-16): con el campo anotado ``StrPath`` y la conversión en ``__post_init__``, mypy veía
    ``cfg.output_dir`` como ``str | PathLike`` aunque en ejecución fuera ``Path``. Con un descriptor, mypy toma el tipo de
    ``__init__`` de :meth:`__set__` (``StrPath``) y el de lectura de :meth:`__get__` (``Path``). También valida al
    reasignar el atributo. Sin ``slots=True``: guarda el valor en ``__dict__`` de la instancia.

    Example:
        >>> from dataclasses import dataclass
        >>> @dataclass
        ... class Config:
        ...     output_dir: PathField = PathField(Path())
        >>> Config("salida").output_dir == Path("salida")
        True
    """

    def __init__(self, default: Path) -> None:
        self._default: Path = default
        self._name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, obj: None, owner: type | None = None) -> Path: ...
    @overload
    def __get__(self, obj: object, owner: type | None = None) -> Path: ...
    def __get__(self, obj: object | None, owner: type | None = None) -> Path:
        # Sin instancia, el valor por defecto: ``dataclass`` lo usa como default del campo.
        if obj is None:
            return self._default
        value: Path = obj.__dict__[self._name]
        return value

    def __set__(self, obj: object, value: StrPath) -> None:
        obj.__dict__[self._name] = validate_path(value, self._name)


class OptionalPathField:
    """Como :class:`PathField`, pero opcional: ``None`` (el valor por defecto) se guarda tal cual.

    ``label`` es el nombre del mensaje de error si no es el del atributo (p. ej. ``"audit.csv_path"`` en los paquetes de
    opciones de ``bulk``, v3.0.0, donde dos paquetes tienen un campo ``csv_path``).
    """

    def __init__(self, label: str | None = None) -> None:
        self._name: str = ""
        self._label: str | None = label

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, obj: None, owner: type | None = None) -> Path | None: ...
    @overload
    def __get__(self, obj: object, owner: type | None = None) -> Path | None: ...
    def __get__(self, obj: object | None, owner: type | None = None) -> Path | None:
        if obj is None:
            return None
        value: Path | None = obj.__dict__[self._name]
        return value

    def __set__(self, obj: object, value: StrPath | None) -> None:
        obj.__dict__[self._name] = validate_optional_path(value, self._label or self._name)
