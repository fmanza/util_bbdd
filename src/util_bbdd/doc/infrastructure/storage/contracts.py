"""Tipos compartidos del runtime de inventario de almacenamiento."""

from __future__ import annotations

from typing import Any, Protocol


class StorageInventoryManagerProtocol(Protocol):
    """Contrato mínimo del manager requerido por el runtime de inventario."""

    db_type: str
    database: str
    conn_params: dict[str, Any]

    def get_storage_rows(self, query_name: str, **params: Any) -> Any:
        """Filas de una consulta de ``metadata.storage`` (``QueryNotFoundError`` si el motor no la tiene)."""
        ...
