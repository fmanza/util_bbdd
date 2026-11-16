"""Filtro de tablas y vistas de la documentación (``imprimir["filtro"]``, 5.5.0).

Desde 5.9.0 la clase vive en :mod:`util_bbdd.metadata.table_filter` (la comparten ``migrate`` y ``dump``); este módulo
la reexporta para no cambiar las importaciones de ``doc``.
"""

from __future__ import annotations

from ...metadata.table_filter import FILTER_KEY, TableFilter

__all__: list[str] = ["FILTER_KEY", "TableFilter"]
