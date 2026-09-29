"""Factory centralizado para resolver estrategias de metadata y storage."""

from __future__ import annotations

from ._manager_metadata_runtime import (
    MetadataFetchStrategy,
    get_metadata_fetch_strategy,
)
from ._manager_storage import (
    AsyncStorageInventoryStrategy,
    SyncStorageInventoryStrategy,
    get_async_storage_inventory_strategy,
    get_sync_storage_inventory_strategy,
)


class MetadataStrategyFactory:
    """Factory para resolver estrategias de metadata según motor."""

    @staticmethod
    def get_fetch_strategy(db_type: str) -> MetadataFetchStrategy:
        """
        Resuelve estrategia de fetch de metadata según driver.

        Args:
            db_type: Tipo de base de datos.

        Returns:
            Estrategia de fetch de metadata.
        """
        return get_metadata_fetch_strategy(db_type)

    @staticmethod
    def get_storage_strategy(db_type: str) -> SyncStorageInventoryStrategy:
        """
        Resuelve estrategia sync de inventario de almacenamiento según driver.

        Args:
            db_type: Tipo de base de datos.

        Returns:
            Estrategia sync de inventario de almacenamiento.
        """
        return get_sync_storage_inventory_strategy(db_type)

    @staticmethod
    def get_async_storage_strategy(db_type: str) -> AsyncStorageInventoryStrategy:
        """Resuelve estrategia async de inventario de almacenamiento según driver.

        Args:
            db_type: Tipo de base de datos.

        Returns:
            Estrategia async de inventario de almacenamiento.
        """
        return get_async_storage_inventory_strategy(db_type)


__all__: list[str] = ["MetadataStrategyFactory"]
