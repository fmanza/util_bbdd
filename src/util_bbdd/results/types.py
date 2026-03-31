"""Tipos de retorno compartidos para ejecución de consultas."""

from __future__ import annotations

from typing import Any

Row = tuple[Any, ...]
"""Fila única devuelta por un cursor DB-API."""

Rows = list[Row]
"""Colección materializada de filas."""

RowOrNone = Row | None
"""Resultado para operaciones que pueden devolver 0 o 1 fila."""

QueryResult = RowOrNone | Rows
"""Unión de resultado singular/múltiple usada solo en capas internas."""
