"""Nombres de fichero a partir de nombres del catálogo (tablas, vistas…), sin salir del directorio de salida."""

from __future__ import annotations


def safe_file_stem(raw_name: str) -> str:
    """Convierte un nombre del catálogo en un componente de ruta seguro: minúsculas, alfanuméricos y guiones.

    Oracle, PostgreSQL y SQL Server admiten casi cualquier carácter en un identificador entrecomillado (``/``,
    ``..``, ``:``…); usado tal cual en una ruta, puede escribir fuera del directorio de salida o fallar en Windows
    (DOC-03, S-04). Dos nombres distintos pueden dar el mismo resultado: si hace falta unicidad, la resuelve quien llama.

    Args:
        raw_name: Nombre tal como viene del motor.

    Returns:
        Nombre saneado, nunca vacío.

    Example:
        >>> safe_file_stem("../../etc/passwd")
        'etc-passwd'
        >>> safe_file_stem("My Table (v2)")
        'my-table-v2'
    """
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in raw_name)
    normalized = "-".join(part for part in normalized.split("-") if part)
    return normalized or "item"


__all__: list[str] = ["safe_file_stem"]
