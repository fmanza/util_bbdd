"""Utilidades de inspección de tablas SQLAlchemy, independientes de bulk_crud."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Column, Engine, Table, func, select
from sqlalchemy.orm import Session


def get_column_case_insensitive(table: Table, column_name: str) -> Column[Any] | None:
    """Devuelve la columna de una tabla ignorando el casing del nombre."""
    index: dict[str, Column[Any]] = {col.name.lower(): col for col in table.columns}
    return index.get(column_name.lower())


def get_max_column_value(engine: Engine, table: Table, column_name: str) -> int:
    """Devuelve MAX(column) + 1; retorna 1 si la columna está vacía o el máximo es negativo.

    Raises:
        ValueError: Si la columna no existe en la tabla.
    """
    col: Column[Any] | None = next(
        (c for c in table.columns if c.name.lower() == column_name.lower()), None
    )
    if col is None:
        raise ValueError(f"Columna '{column_name}' no encontrada en la tabla '{table.name}'")

    with Session(engine) as session:
        max_val: int | None = session.execute(select(func.max(col))).scalar_one_or_none()

    if max_val is None or max_val < 0:
        return 1
    return max_val + 1


__all__: list[str] = [
    "get_column_case_insensitive",
    "get_max_column_value",
]
