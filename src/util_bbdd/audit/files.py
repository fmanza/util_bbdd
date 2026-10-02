"""Utilidades de fichero comunes a los destinos de auditoría: apartar un fichero ajeno, primera línea, tamaño, identidad.

Un CSV de auditoría o de rechazos abierto y guardado con otra herramienta (p. ej. Excel con otro delimitador) no se puede
leer ni seguir ampliando. En lugar de añadirle filas, se aparta como ``<nombre>.invalid-<fecha><ext>`` (no se pierde
nada) y se empieza uno nuevo.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


class AuditFiles:
    """Operaciones de fichero sin estado que comparten los destinos de auditoría."""

    #: Texto que devuelve :meth:`first_line` si el fichero no es UTF-8.
    NOT_UTF8: str = "<no es texto UTF-8>"

    @staticmethod
    def aside_path(path: Path) -> Path:
        """``<nombre>.invalid-<fecha><ext>``, con sufijo ``_2``, ``_3``… si ya existe (en Windows el renombrado fallaría)."""
        base = f"{path.stem}.invalid-{datetime.now():%Y%m%d_%H%M%S}"
        candidato = path.with_name(f"{base}{path.suffix}")
        n = 2
        while candidato.exists():
            candidato = path.with_name(f"{base}_{n}{path.suffix}")
            n += 1
        return candidato

    @staticmethod
    def first_line(path: Path) -> str:
        """Primera línea de ``path`` (con su fin de línea), o :attr:`NOT_UTF8` si no es UTF-8.

        Raises:
            OSError: Si no se puede abrir (quien llama decide si es un error).
        """
        try:
            with open(path, encoding="utf-8", newline="") as handle:
                return handle.readline()
        except UnicodeDecodeError:
            return AuditFiles.NOT_UTF8

    @staticmethod
    def has_header(first_line: str, header: str) -> bool:
        """``True`` si ``first_line`` está vacía (fichero vacío) o es ``header`` (con o sin BOM y fin de línea)."""
        return not first_line or first_line.lstrip("﻿").rstrip("\r\n") == header

    @staticmethod
    def set_aside(path: Path) -> Path:
        """Renombra ``path`` a :meth:`aside_path` y devuelve la ruta nueva.

        Raises:
            OSError: Si no se puede renombrar (p. ej. abierto en Excel en Windows).
        """
        aside = AuditFiles.aside_path(path)
        path.rename(aside)
        return aside

    @staticmethod
    def file_size(path: Path | None) -> int | None:
        """Tamaño de ``path`` en bytes, o ``None`` si no hay ruta o el fichero no existe."""
        if path is None:
            return None
        try:
            return path.stat().st_size if path.is_file() else None
        except OSError:
            return None

    @staticmethod
    def file_identity(path: Path | None) -> tuple[int, int] | None:
        """``(st_dev, st_ino)`` de ``path``, o ``None`` si no hay ruta o el fichero no existe.

        Distingue un fichero de otro nuevo con la misma ruta (p. ej. tras apartar uno con cabecera ajena): un
        desplazamiento guardado del primero ya no corresponde al segundo.
        """
        if path is None:
            return None
        try:
            stat = path.stat()
        except OSError:
            return None
        return stat.st_dev, stat.st_ino


__all__: list[str] = ["AuditFiles"]
