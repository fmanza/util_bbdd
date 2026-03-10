"""Tipos de retorno compartidos para ejecución de consultas."""

from __future__ import annotations

from typing import Any, TypeAlias

Row: TypeAlias = tuple[Any, ...]
"""Fila única devuelta por un cursor DB-API."""

Rows: TypeAlias = list[Row]
"""Colección materializada de filas."""

RowOrNone: TypeAlias = Row | None
"""Resultado para operaciones que pueden devolver 0 o 1 fila."""

QueryResult: TypeAlias = RowOrNone | Rows
"""Unión de resultado singular/múltiple usada solo en capas internas."""
