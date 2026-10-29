"""Tipos de retorno compartidos para ejecución de consultas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Row = tuple[Any, ...]
"""Fila única devuelta por un cursor DB-API."""

Rows = list[Row]
"""Colección materializada de filas."""

RowOrNone = Row | None
"""Resultado para operaciones que pueden devolver 0 o 1 fila."""

QueryResult = RowOrNone | Rows
"""Unión de resultado singular/múltiple usada solo en capas internas."""


@dataclass(frozen=True)
class CustomQueryResult:
    """Resultado de ``execute_custom_result`` (5.0.0, G42 de util_bbdd_web): cabeceras y filas.

    Attributes:
        columns: Nombres de las columnas en el orden del ``SELECT``, tal como los da el driver, también sin filas y
            con nombres repetidos (``SELECT 1 AS a, 2 AS a`` → ``("a", "a")``). Vacío si la sentencia no devuelve
            un conjunto de resultados.
        rows: Filas (``Rows``), como las de ``execute_custom_many``.

    Example:
        >>> result = manager.execute_custom_result("SELECT id, nombre FROM clientes", max_rows=100)
        >>> result.columns
        ('id', 'nombre')
    """

    columns: tuple[str, ...] = ()
    rows: Rows = field(default_factory=list)


__all__: list[str] = ["CustomQueryResult", "Row", "Rows", "RowOrNone", "QueryResult"]
