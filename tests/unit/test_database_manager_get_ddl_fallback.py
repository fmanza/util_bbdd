"""``get_ddl`` de MariaDB: ``CREATE TABLE`` construido desde las columnas y la PK tipadas del snapshot."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.managers import SyncDatabaseManager
from util_bbdd.managers._manager_metadata_runtime import get_metadata_fetch_strategy
from util_bbdd.metadata import DatabaseMetadataCache
from util_bbdd.metadata.model import ColumnMeta, PrimaryKeyMeta


class TestDatabaseManagerMariaDbMetadataPaths:
    def _build_manager(self) -> SyncDatabaseManager:
        manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
        manager.db_type = "mariadb"
        manager.database = "db"
        manager.conn_params = {"database": "db"}
        manager.logger = MagicMock()
        manager.db_cache = DatabaseMetadataCache()
        manager._metadata_fetch_strategy = get_metadata_fetch_strategy(manager.db_type)
        return manager

    def test_get_ddl_uses_metadata_builder_as_primary_path(self) -> None:
        manager = self._build_manager()
        manager._execute_metadata_one = MagicMock()
        manager.get_columns = MagicMock(
            return_value=[
                ColumnMeta("users", "id", 1, "int", "int", False, identity="by default"),
                ColumnMeta("users", "name", 2, "varchar(50)", "varchar", True, default="'Óscar'"),
            ]
        )
        manager.get_primary_keys = MagicMock(return_value=PrimaryKeyMeta("users", "PRIMARY", ("id",)))

        ddl = manager.get_ddl("users")

        assert ddl.startswith("CREATE TABLE `users`")
        assert "`id` int NOT NULL auto_increment" in ddl
        assert "`name` varchar(50) NULL DEFAULT 'Óscar'" in ddl
        assert "PRIMARY KEY (`id`)" in ddl
        manager._execute_metadata_one.assert_not_called()
        manager.get_columns.assert_called_once_with("users")
        manager.get_primary_keys.assert_called_once_with("users")
