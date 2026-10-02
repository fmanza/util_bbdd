"""Saneado de texto para los ficheros de auditoría (OWASP: inyección de fórmulas en CSV y de líneas en logs).

La escritura segura en Excel (``openpyxl``) es otra cosa y vive en ``_core/export_safety.py``: allí las fórmulas se
guardan como texto; aquí, en un CSV que se abrirá con una hoja de cálculo, se antepone un apóstrofo.
"""

from __future__ import annotations

from typing import ClassVar


class AuditText:
    """Transformaciones de texto sin estado comunes a los destinos de auditoría."""

    #: Una celda que empieza así se ejecutaría como fórmula al abrir el CSV en una hoja de cálculo.
    FORMULA_PREFIXES: ClassVar[tuple[str, ...]] = ("=", "+", "-", "@", "\t", "\r")

    @staticmethod
    def safe_csv_cell(text: str) -> str:
        """``text`` con un apóstrofo delante si empieza como una fórmula de hoja de cálculo.

        Example:
            >>> AuditText.safe_csv_cell("=HYPERLINK(1)")
            "'=HYPERLINK(1)"
        """
        return f"'{text}" if text.startswith(AuditText.FORMULA_PREFIXES) else text

    @staticmethod
    def error_summary(error: BaseException) -> str:
        """Clase y primera línea del error del driver (sin la sentencia ni los parámetros que añade SQLAlchemy)."""
        origin: BaseException = getattr(error, "orig", None) or error
        lines = str(origin).strip().splitlines()
        return f"{type(error).__name__}: {lines[0] if lines else ''}"


__all__: list[str] = ["AuditText"]
