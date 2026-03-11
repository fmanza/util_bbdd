"""Tests unitarios para wrappers normalizados de DatabaseManager."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.managers import DatabaseManager


class TestDatabaseManagerNormalizedMethods:
    """Valida métodos de normalización sin depender de conexión real."""

    def test_get_tables_normalized_maps_raw_rows(self) -> None:
        manager = DatabaseManager.__new__(DatabaseManager)
        manager.get_tables = MagicMock(return_value=[("users",), ("orders",)])

        result = DatabaseManager.get_tables_normalized(manager)

        assert result == [
            {"name": "users", "raw": ("users",)},
            {"name": "orders", "raw": ("orders",)},
        ]

    def test_get_columns_normalized_maps_raw_rows(self) -> None:
        manager = DatabaseManager.__new__(DatabaseManager)
        manager.get_columns = MagicMock(return_value=[(0, "id", "INTEGER"), (1, "name", "TEXT")])

        result = DatabaseManager.get_columns_normalized(manager, "users")

        assert result == [
            {"name": "id", "data_type": "INTEGER", "raw": (0, "id", "INTEGER")},
            {"name": "name", "data_type": "TEXT", "raw": (1, "name", "TEXT")},
        ]
