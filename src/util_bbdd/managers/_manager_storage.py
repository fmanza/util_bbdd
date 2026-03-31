"""Helpers internos para selección de inventario de almacenamiento."""

from __future__ import annotations


def get_storage_inventory_handler[HandlerT](db_type: str, handlers: dict[str, HandlerT]) -> HandlerT | None:
    """Devuelve el handler de inventario apropiado para el motor."""
    return handlers.get(db_type)
