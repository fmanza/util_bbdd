"""Filas de las consultas por schema de los extractores, agrupadas por tabla o vista (D1, 0.21.0).

Los extractores leen cada tipo de objeto (columnas, PK, FK, índices, columnas de vistas, cuerpos de rutinas) con una
consulta por schema en lugar de una por tabla: 823 consultas → 8 para 200 tablas y 20 vistas (sesión
2026-09-30-migrate-d1-extract-batching). La primera columna de esas consultas es el nombre del objeto; el resto, en el
orden que ya leían los extractores con la consulta por tabla.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

Row = tuple[Any, ...]


class ObjectRows(dict[str, list[Row]]):
    """``{nombre exacto: [filas]}`` con búsqueda tolerante a mayúsculas (H1, auditoría 0.21.0)."""

    def for_object(self, name: str) -> list[Row]:
        """Filas de ``name``; si no hay coincidencia exacta, las de la única que solo difiere en mayúsculas.

        Las consultas por tabla anteriores filtraban con ``TABLE_NAME = …``, que en MySQL/MariaDB y SQL Server no
        distingue mayúsculas: si una vista del catálogo devuelve el nombre con otra capitalización, la tabla no debe
        quedarse sin filas. Con varias candidatas no se adivina.
        """
        if name in self:
            return self[name]
        folded = name.casefold()
        candidates = [key for key in self if key.casefold() == folded]
        return self[candidates[0]] if len(candidates) == 1 else []


def group_by_object(rows: Iterable[Any]) -> ObjectRows:
    """``{nombre exacto: [fila sin la primera columna, ...]}`` conservando el orden de las filas."""
    grouped = ObjectRows()
    for row in rows:
        if not row:
            continue
        grouped.setdefault(str(row[0]).strip(), []).append(tuple(row[1:]))
    return grouped


__all__: list[str] = ["ObjectRows", "group_by_object"]
