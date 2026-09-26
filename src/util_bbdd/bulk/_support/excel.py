"""Utilidades de openpyxl compartidas por los informes de ``bulk`` (auditoría) y ``dump``."""

from __future__ import annotations

from typing import Any


def neutralize_formulas(worksheet: Any) -> None:
    """Guarda como texto las celdas que openpyxl ha tomado por fórmulas.

    H12 (audit-code 2026-09-25): openpyxl interpreta como fórmula toda cadena que empieza por ``=``, así que un nombre de
    tabla del catálogo o del CSV de auditoría como ``=HYPERLINK(...)`` se ejecutaría al abrir el Excel. Los informes de
    la librería nunca contienen fórmulas propias.
    """
    for row in worksheet.iter_rows():
        for cell in row:
            if cell.data_type == "f":
                cell.data_type = "s"


__all__: list[str] = ["neutralize_formulas"]
