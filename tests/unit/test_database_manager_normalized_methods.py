"""Tests unitarios para wrappers normalizados de SyncDatabaseManager."""

from __future__ import annotations

import logging

from unittest.mock import MagicMock

from util_bbdd.managers import SyncDatabaseManager
from util_bbdd.metadata import DatabaseMetadataCache


class TestDatabaseManagerNormalizedMethods:
    """Valida métodos de normalización sin depender de conexión real."""

    def test_get_tables_normalized_maps_raw_rows(self) -> None:
        manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
        manager.get_tables = MagicMock(return_value=[("users",), ("orders",)])

        result = SyncDatabaseManager.get_tables_normalized(manager)

        assert result == [
            {"name": "users", "raw": ("users",)},
            {"name": "orders", "raw": ("orders",)},
        ]

    def test_get_columns_normalized_maps_raw_rows(self) -> None:
        manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
        manager.get_columns = MagicMock(return_value=[(0, "id", "INTEGER"), (1, "name", "TEXT")])

        result = SyncDatabaseManager.get_columns_normalized(manager, "users")

        assert result == [
            {"name": "id", "data_type": "INTEGER", "raw": (0, "id", "INTEGER")},
            {"name": "name", "data_type": "TEXT", "raw": (1, "name", "TEXT")},
        ]

    def test_get_columns_charset_collation_returns_empty_for_oracle_without_query(self) -> None:
        manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
        mock_executor = MagicMock()
        manager.db_type = "oracle"
        manager.conn_params = {"user": "DA_DPSS"}
        manager.database = ""
        manager.db_cache = DatabaseMetadataCache()
        manager.logger = logging.getLogger("test.sync_mgr")
        manager.sync_query_executor = mock_executor
        manager.get_database_version = MagicMock(
            return_value="Oracle Database 12c Enterprise Edition Release 12.1.0.2.0 - Production"
        )

        result = manager.get_columns_charset_collation("V_SAAD_VALORACIONEVE")

        assert result == []
        mock_executor.execute_query_many.assert_not_called()

    def test_get_columns_charset_collation_uses_oracle_collation_query_for_12_2_plus(self) -> None:
        manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
        manager.db_type = "oracle"
        manager.conn_params = {"user": "DA_DPSS"}
        manager.database = ""
        manager.db_cache = DatabaseMetadataCache()
        manager.logger = logging.getLogger("test.sync_mgr")
        manager.get_database_version = MagicMock(
            return_value="Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production"
        )
        manager._execute_metadata_many = MagicMock(return_value=[("COL1", None, "BINARY_CI")])

        result = manager.get_columns_charset_collation("V_SAAD_VALORACIONEVE")

        assert result == [("COL1", None, "BINARY_CI")]
        manager._execute_metadata_many.assert_called_once_with(
            "columns_charset_collation",
            params={"tabla": "V_SAAD_VALORACIONEVE", "database": "DA_DPSS"},
            error_message="Error obteniendo charset/collation de columnas",
            table_name="V_SAAD_VALORACIONEVE",
        )
