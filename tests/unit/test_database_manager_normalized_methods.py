"""Tests unitarios para wrappers normalizados de SyncDatabaseManager."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.managers import SyncDatabaseManager


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
