"""Filas de las consultas por schema de los extractores, agrupadas por tabla o vista (D1, 0.21.0).

Los extractores leen cada tipo de objeto (columnas, PK, FK, índices, columnas de vistas, cuerpos de rutinas) con una
consulta por schema en lugar de una por tabla: 823 consultas → 8 para 200 tablas y 20 vistas (sesión
2026-09-30-migrate-d1-extract-batching). La primera columna de esas consultas es el nombre del objeto; el resto, en el
orden que ya leían los extractores con la consulta por tabla.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def group_by_object(rows: Iterable[Any]) -> dict[str, list[tuple[Any, ...]]]:
    """``{nombre exacto: [fila sin la primera columna, ...]}`` conservando el orden de las filas."""
    grouped: dict[str, list[tuple[Any, ...]]] = {}
    for row in rows:
        if not row:
            continue
        grouped.setdefault(str(row[0]).strip(), []).append(tuple(row[1:]))
    return grouped


__all__: list[str] = ["group_by_object"]
