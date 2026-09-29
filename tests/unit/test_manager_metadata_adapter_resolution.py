"""Resolución del adapter de lecturas especializadas por el registro global (``_get_metadata_adapter``).

Los managers ya no instancian un adapter por motor: ``_get_metadata_adapter()`` lo pide a ``_get_adapter_*("source")``,
que lo resuelve por ``db_type`` en el registro global y lo cachea en la instancia.
"""

from __future__ import annotations

import asyncio

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd._core.exceptions import DatabaseConfigurationError
from util_bbdd.managers import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.managers._manager_storage import (
    get_async_storage_inventory_strategy,
    get_sync_storage_inventory_strategy,
)
from util_bbdd.metadata.mariadb import MariaDBAsyncAdapter, MariaDBSyncAdapter


def _sync_manager(db_type: str) -> SyncDatabaseManager:
    manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
    manager.db_type = db_type
    return manager


def _async_manager(db_type: str) -> AsyncDatabaseManager:
    manager = AsyncDatabaseManager.__new__(AsyncDatabaseManager)
    manager.db_type = db_type
    return manager


class TestGetMetadataAdapter:
    def test_sync_resolves_registered_mariadb_adapter(self) -> None:
        manager = _sync_manager("mariadb")
        adapter: Any = manager._get_metadata_adapter()
        assert isinstance(adapter, MariaDBSyncAdapter)
        assert adapter.manager is manager

    def test_async_resolves_registered_mariadb_adapter(self) -> None:
        manager = _async_manager("mariadb")
        adapter: Any = manager._get_metadata_adapter()
        assert isinstance(adapter, MariaDBAsyncAdapter)
        assert adapter.manager is manager

    def test_sync_adapter_is_cached_per_instance(self) -> None:
        manager = _sync_manager("mariadb")
        assert manager._get_metadata_adapter() is manager._get_metadata_adapter()
        assert _sync_manager("mariadb")._get_metadata_adapter() is not manager._get_metadata_adapter()

    def test_async_adapter_is_cached_per_instance(self) -> None:
        manager = _async_manager("mariadb")
        assert manager._get_metadata_adapter() is manager._get_metadata_adapter()

    def test_sync_unregistered_db_type_raises(self) -> None:
        with pytest.raises(DatabaseConfigurationError, match="hsqldb"):
            _sync_manager("hsqldb")._get_metadata_adapter()

    def test_async_unregistered_db_type_raises(self) -> None:
        with pytest.raises(DatabaseConfigurationError, match="hsqldb"):
            _async_manager("hsqldb")._get_metadata_adapter()


class TestStorageStrategiesUseMetadataAdapter:
    def test_sync_mariadb_strategy_delegates_to_metadata_adapter(self) -> None:
        manager = MagicMock()
        manager._get_metadata_adapter.return_value.storage_inventory.return_value = {"primary": [("f",)]}
        result = get_sync_storage_inventory_strategy("mariadb").execute(manager, "db1", None)
        assert result == {"primary": [("f",)]}
        manager._get_metadata_adapter.return_value.storage_inventory.assert_called_once_with("db1")

    def test_async_mariadb_strategy_delegates_to_metadata_adapter(self) -> None:
        manager = MagicMock()
        manager._get_metadata_adapter.return_value.storage_inventory = AsyncMock(return_value={"primary": []})
        result = asyncio.run(get_async_storage_inventory_strategy("mariadb").execute(manager, "db1", None))
        assert result == {"primary": []}
        manager._get_metadata_adapter.return_value.storage_inventory.assert_awaited_once_with("db1")

    def test_async_hsqldb_strategy_is_awaitable_and_empty(self) -> None:
        result = asyncio.run(get_async_storage_inventory_strategy("hsqldb").execute(MagicMock(), "db1", None))
        assert result == {"primary": []}
