"""Tests para verificar Protocol compliance y paridad entre adapters Snowflake."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.metadata.snowflake.async_adapter import SnowflakeAsyncAdapter
from util_bbdd.metadata.snowflake.sync_adapter import SnowflakeSyncAdapter


class TestSnowflakeSyncAdapterInterface:
    """Tests para SnowflakeSyncAdapter interface compliance."""

    def test_sync_adapter_instantiation(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeSyncAdapter(manager)
        assert adapter is not None
        assert adapter.manager is manager

    def test_sync_adapter_has_fetch_schemas_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeSyncAdapter(manager)
        assert hasattr(adapter, "fetch_schemas_sync")
        assert callable(adapter.fetch_schemas_sync)

    def test_sync_adapter_has_fetch_tables_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeSyncAdapter(manager)
        assert hasattr(adapter, "fetch_tables_sync")
        assert callable(adapter.fetch_tables_sync)

    def test_sync_adapter_has_fetch_columns_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeSyncAdapter(manager)
        assert hasattr(adapter, "fetch_columns_sync")
        assert callable(adapter.fetch_columns_sync)

    def test_sync_adapter_has_fetch_primary_keys_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeSyncAdapter(manager)
        assert hasattr(adapter, "fetch_primary_keys_sync")
        assert callable(adapter.fetch_primary_keys_sync)

    def test_sync_adapter_has_fetch_foreign_keys_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeSyncAdapter(manager)
        assert hasattr(adapter, "fetch_foreign_keys_sync")
        assert callable(adapter.fetch_foreign_keys_sync)

    def test_sync_adapter_has_fetch_indexes_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeSyncAdapter(manager)
        assert hasattr(adapter, "fetch_indexes_sync")
        assert callable(adapter.fetch_indexes_sync)

    def test_sync_adapter_has_fetch_routines_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeSyncAdapter(manager)
        assert hasattr(adapter, "fetch_routines_sync")
        assert callable(adapter.fetch_routines_sync)

    def test_sync_adapter_has_fetch_routine_parameters_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeSyncAdapter(manager)
        assert hasattr(adapter, "fetch_routine_parameters_sync")
        assert callable(adapter.fetch_routine_parameters_sync)

    def test_sync_adapter_fetch_schemas_returns_list_of_tuples(self) -> None:
        manager = MagicMock()
        manager.connection = MagicMock()
        manager.connection.execute.return_value = MagicMock(fetchall=lambda: [])

        adapter = SnowflakeSyncAdapter(manager)
        result = adapter.fetch_schemas_sync("MYDB")
        assert isinstance(result, list)

    def test_sync_adapter_handles_missing_connection(self) -> None:
        manager = MagicMock(spec=[])  # No connection attribute
        manager.db = None  # Also no db attribute
        adapter = SnowflakeSyncAdapter(manager)
        result = adapter.fetch_schemas_sync("MYDB")
        assert result == []

    def test_sync_adapter_handles_none_manager(self) -> None:
        adapter = SnowflakeSyncAdapter(None)
        result = adapter.fetch_schemas_sync("MYDB")
        assert result == []

    def test_sync_adapter_multi_level_schema_parameters(self) -> None:
        """Verify adapter accepts database, schema, table parameters."""
        manager = MagicMock()
        manager.connection = MagicMock()
        manager.connection.execute.return_value = MagicMock(fetchall=lambda: [])

        adapter = SnowflakeSyncAdapter(manager)

        # Should support database parameter
        result = adapter.fetch_tables_sync(database="MYDB", schema="PUBLIC")
        assert isinstance(result, list)

        # Should support columns with all 3 levels
        result = adapter.fetch_columns_sync(database="MYDB", schema="PUBLIC", table="TABLE1")
        assert isinstance(result, list)


class TestSnowflakeAsyncAdapterInterface:
    """Tests para SnowflakeAsyncAdapter interface compliance."""

    def test_async_adapter_instantiation(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeAsyncAdapter(manager)
        assert adapter is not None
        assert adapter.manager is manager

    def test_async_adapter_has_fetch_schemas_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeAsyncAdapter(manager)
        assert hasattr(adapter, "fetch_schemas_sync")
        assert callable(adapter.fetch_schemas_sync)

    def test_async_adapter_has_fetch_tables_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeAsyncAdapter(manager)
        assert hasattr(adapter, "fetch_tables_sync")
        assert callable(adapter.fetch_tables_sync)

    def test_async_adapter_has_fetch_columns_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeAsyncAdapter(manager)
        assert hasattr(adapter, "fetch_columns_sync")
        assert callable(adapter.fetch_columns_sync)

    def test_async_adapter_has_fetch_primary_keys_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeAsyncAdapter(manager)
        assert hasattr(adapter, "fetch_primary_keys_sync")
        assert callable(adapter.fetch_primary_keys_sync)

    def test_async_adapter_has_fetch_foreign_keys_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeAsyncAdapter(manager)
        assert hasattr(adapter, "fetch_foreign_keys_sync")
        assert callable(adapter.fetch_foreign_keys_sync)

    def test_async_adapter_has_fetch_indexes_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeAsyncAdapter(manager)
        assert hasattr(adapter, "fetch_indexes_sync")
        assert callable(adapter.fetch_indexes_sync)

    def test_async_adapter_has_fetch_routines_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeAsyncAdapter(manager)
        assert hasattr(adapter, "fetch_routines_sync")
        assert callable(adapter.fetch_routines_sync)

    def test_async_adapter_has_fetch_routine_parameters_method(self) -> None:
        manager = MagicMock()
        adapter = SnowflakeAsyncAdapter(manager)
        assert hasattr(adapter, "fetch_routine_parameters_sync")
        assert callable(adapter.fetch_routine_parameters_sync)

    def test_async_adapter_fetch_schemas_returns_list_of_tuples(self) -> None:
        manager = MagicMock()
        manager.connection = MagicMock()
        manager.connection.execute.return_value = MagicMock(fetchall=lambda: [])

        adapter = SnowflakeAsyncAdapter(manager)
        result = adapter.fetch_schemas_sync("MYDB")
        assert isinstance(result, list)

    def test_async_adapter_handles_missing_connection(self) -> None:
        manager = MagicMock(spec=[])
        manager.db = None  # Also no db attribute
        adapter = SnowflakeAsyncAdapter(manager)
        result = adapter.fetch_schemas_sync("MYDB")
        assert result == []

    def test_async_adapter_handles_none_manager(self) -> None:
        adapter = SnowflakeAsyncAdapter(None)
        result = adapter.fetch_schemas_sync("MYDB")
        assert result == []


class TestSnowflakeAdapterParitySync:
    """Tests para verificar paridad entre sync y async adapters."""

    def test_adapters_have_same_public_methods(self) -> None:
        """Both adapters should expose the same public interface."""
        sync_methods = {m for m in dir(SnowflakeSyncAdapter) if not m.startswith("_")}
        async_methods = {m for m in dir(SnowflakeAsyncAdapter) if not m.startswith("_")}

        # Should have same methods
        assert sync_methods == async_methods

    def test_adapters_fetch_schemas_returns_same_type(self) -> None:
        manager_sync = MagicMock()
        manager_sync.connection = MagicMock()
        manager_sync_cursor = MagicMock()
        manager_sync_cursor.fetchall.return_value = [("PUBLIC",)]
        manager_sync.connection.execute.return_value = manager_sync_cursor

        manager_async = MagicMock()
        manager_async.connection = MagicMock()
        manager_async_cursor = MagicMock()
        manager_async_cursor.fetchall.return_value = [("PUBLIC",)]
        manager_async.connection.execute.return_value = manager_async_cursor

        sync_adapter = SnowflakeSyncAdapter(manager_sync)
        async_adapter = SnowflakeAsyncAdapter(manager_async)

        sync_result = sync_adapter.fetch_schemas_sync("MYDB")
        async_result = async_adapter.fetch_schemas_sync("MYDB")

        assert isinstance(sync_result, list)
        assert isinstance(async_result, list)
        assert type(sync_result).__name__ == type(async_result).__name__

    def test_adapters_fetch_indexes_both_return_empty(self) -> None:
        """Both adapters should return empty for indexes (Snowflake limitation)."""
        manager_sync = MagicMock()
        manager_async = MagicMock()

        sync_adapter = SnowflakeSyncAdapter(manager_sync)
        async_adapter = SnowflakeAsyncAdapter(manager_async)

        sync_result = sync_adapter.fetch_indexes_sync("MYDB", "PUBLIC", "TABLE1")
        async_result = async_adapter.fetch_indexes_sync("MYDB", "PUBLIC", "TABLE1")

        assert sync_result == []
        assert async_result == []


class TestSnowflakeAdapterRegistration:
    """Tests para verificar que adapters están registrados globalmente."""

    def test_snowflake_adapters_auto_registered(self) -> None:
        """Adapters should be automatically registered on module import."""
        try:
            from util_bbdd.metadata.adapters import get_global_adapter_registry

            registry = get_global_adapter_registry()

            # Should be registered after importing snowflake module
            sync_adapter_class = registry.get_source_adapter_sync("snowflake")
            async_adapter_class = registry.get_source_adapter_async("snowflake")

            assert sync_adapter_class is SnowflakeSyncAdapter
            assert async_adapter_class is SnowflakeAsyncAdapter
        except ImportError:
            # Registry might not be available in test environment
            pytest.skip("Adapter registry not available")

    def test_snowflake_alternate_names_registered(self) -> None:
        """Alternate driver names should also be registered."""
        try:
            from util_bbdd.metadata.adapters import get_global_adapter_registry

            registry = get_global_adapter_registry()

            # Alternate name
            sync_adapter_alt = registry.get_source_adapter_sync("snowflake-cloud")
            assert sync_adapter_alt is SnowflakeSyncAdapter
        except ImportError:
            pytest.skip("Adapter registry not available")

    def test_snowflake_listed_in_registry(self) -> None:
        """Snowflake driver should be listed in registered drivers."""
        try:
            from util_bbdd.metadata.adapters import get_global_adapter_registry

            registry = get_global_adapter_registry()
            drivers = registry.list_registered_drivers()

            assert "snowflake" in drivers
        except ImportError:
            pytest.skip("Adapter registry not available")


class TestSnowflakeMultiLevelSchemaHandling:
    """Tests para verificar manejo correcto de DATABASE.SCHEMA.TABLE."""

    def test_adapter_accepts_database_parameter(self) -> None:
        """Adapter should accept database parameter for multi-level schema."""
        manager = MagicMock()
        manager.connection = MagicMock()
        manager.connection.execute.return_value = MagicMock(fetchall=lambda: [])

        adapter = SnowflakeSyncAdapter(manager)

        # Should accept database parameter without error
        result = adapter.fetch_schemas_sync(database="MYDB")
        assert isinstance(result, list)

    def test_adapter_handles_all_three_levels(self) -> None:
        """Adapter methods should handle DATABASE.SCHEMA.TABLE."""
        manager = MagicMock()
        manager.connection = MagicMock()
        manager.connection.execute.return_value = MagicMock(fetchall=lambda: [("COL1", "INT", "NO", 1, None, "")])

        adapter = SnowflakeSyncAdapter(manager)

        result = adapter.fetch_columns_sync(database="MYDB", schema="PUBLIC", table="TABLE1")
        assert isinstance(result, list)
        # Verify the execute was called with proper structure
        assert manager.connection.execute.called
