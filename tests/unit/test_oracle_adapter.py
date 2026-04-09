"""Tests para adaptadores Oracle (sync y async)."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.oracle import OracleAsyncAdapter, OracleSyncAdapter


class TestOracleSyncAdapterBasics:
    """Tests básicos para OracleSyncAdapter."""

    def test_instantiation_with_manager(self) -> None:
        manager = MagicMock()
        adapter = OracleSyncAdapter(manager)
        assert adapter.manager is manager

    def test_instantiation_without_errors(self) -> None:
        manager = MagicMock()
        adapter = OracleSyncAdapter(manager)
        assert adapter is not None

    def test_adapter_is_duck_typeable(self) -> None:
        """Verifica que el adaptador implementa la interfaz esperada."""
        manager = MagicMock()
        adapter = OracleSyncAdapter(manager)

        # SourceAdapter protocol methods
        assert callable(getattr(adapter, "fetch_schemas_sync", None))
        assert callable(getattr(adapter, "fetch_tables_sync", None))
        assert callable(getattr(adapter, "fetch_columns_sync", None))
        assert callable(getattr(adapter, "fetch_primary_keys_sync", None))
        assert callable(getattr(adapter, "fetch_foreign_keys_sync", None))
        assert callable(getattr(adapter, "fetch_indexes_sync", None))


class TestOracleAsyncAdapterBasics:
    """Tests básicos para OracleAsyncAdapter."""

    def test_instantiation_with_manager(self) -> None:
        manager = MagicMock()
        adapter = OracleAsyncAdapter(manager)
        assert adapter.manager is manager

    def test_instantiation_without_errors(self) -> None:
        manager = MagicMock()
        adapter = OracleAsyncAdapter(manager)
        assert adapter is not None

    def test_async_adapter_is_duck_typeable(self) -> None:
        """Verifica que el adaptador async implementa la interfaz esperada."""
        manager = MagicMock()
        adapter = OracleAsyncAdapter(manager)

        # Async versions of SourceAdapter protocol methods
        assert callable(getattr(adapter, "fetch_schemas_sync", None))
        assert callable(getattr(adapter, "fetch_tables_sync", None))
        assert callable(getattr(adapter, "fetch_columns_sync", None))


class TestOracleSyncAdapterFetchSchemasSync:
    """Tests para fetch_schemas_sync()."""

    def test_fetch_schemas_sync_empty_result(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_schemas_sync()
        assert result == []

    def test_fetch_schemas_sync_with_schemas(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("MYAPP",),
            ("OTHERAPP",),
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_schemas_sync()
        assert len(result) == 2
        assert result[0] == ("MYAPP",)
        assert result[1] == ("OTHERAPP",)

    def test_fetch_schemas_sync_calls_execute_custom_many(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_schemas_sync()
        manager.execute_custom_many.assert_called_once()

    def test_fetch_schemas_sync_passes_empty_params(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_schemas_sync()
        # Verificar que se pasaron parámetros vacíos
        call_args = manager.execute_custom_many.call_args
        assert call_args[1]["params"] == {}


class TestOracleSyncAdapterFetchTablesSync:
    """Tests para fetch_tables_sync()."""

    def test_fetch_tables_sync_with_schema(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("USERS", "TABLE", "User table"),
            ("ORDERS", "TABLE", "Orders table"),
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_tables_sync("MYAPP")
        assert len(result) == 2
        assert result[0][0] == "USERS"
        assert result[0][1] == "TABLE"

    def test_fetch_tables_sync_passes_owner_parameter(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_tables_sync("SCHEMA1")
        call_args = manager.execute_custom_many.call_args
        assert call_args[1]["params"]["owner"] == "SCHEMA1"

    def test_fetch_tables_sync_without_schema(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_tables_sync(None)
        assert isinstance(result, list)

    def test_fetch_tables_sync_handles_missing_comment(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("USERS", "TABLE"),  # Missing comment
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_tables_sync("SCHEMA")
        assert len(result) == 1
        assert result[0][2] == ""


class TestOracleSyncAdapterFetchColumnsSync:
    """Tests para fetch_columns_sync()."""

    def test_fetch_columns_sync_requires_schema_and_table(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_columns_sync("SCHEMA", "USERS")
        call_args = manager.execute_custom_many.call_args
        assert call_args[1]["params"]["owner"] == "SCHEMA"
        assert call_args[1]["params"]["table_name"] == "USERS"

    def test_fetch_columns_sync_returns_decoded_rows(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("ID", "NUMBER", "N", 1, "", 0, 0, 0, "Primary key"),
            ("NAME", "VARCHAR2", "Y", 2, "", 100, None, None, "Name"),
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_columns_sync("SCHEMA", "USERS")
        assert len(result) == 2

    def test_fetch_columns_sync_handles_empty_result(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_columns_sync("SCHEMA", "USERS")
        assert result == []


class TestOracleSyncAdapterFetchPrimaryKeysSync:
    """Tests para fetch_primary_keys_sync()."""

    def test_fetch_primary_keys_sync_with_keys(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("PK_USERS_ID", "ID", 1),
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_primary_keys_sync("SCHEMA", "USERS")
        assert len(result) == 1
        assert result[0][0] == "PK_USERS_ID"

    def test_fetch_primary_keys_sync_passes_parameters(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_primary_keys_sync("SCHEMA", "USERS")
        call_args = manager.execute_custom_many.call_args
        assert call_args[1]["params"]["owner"] == "SCHEMA"
        assert call_args[1]["params"]["table_name"] == "USERS"


class TestOracleSyncAdapterForeignKeysSync:
    """Tests para fetch_foreign_keys_sync()."""

    def test_fetch_foreign_keys_sync_with_fk(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("FK_ORDERS_USER", "USER_ID", "SCHEMA", "USERS", "ID", "CASCADE", "", 1),
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_foreign_keys_sync("SCHEMA", "ORDERS")
        assert len(result) == 1

    def test_fetch_foreign_keys_sync_passes_parameters(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_foreign_keys_sync("SCHEMA", "ORDERS")
        call_args = manager.execute_custom_many.call_args
        assert call_args[1]["params"]["owner"] == "SCHEMA"
        assert call_args[1]["params"]["table_name"] == "ORDERS"


class TestOracleSyncAdapterIndexesSync:
    """Tests para fetch_indexes_sync()."""

    def test_fetch_indexes_sync_with_indexes(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("IDX_USERS_NAME", "NAME", "ASC", "NONUNIQUE", 1),
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_indexes_sync("SCHEMA", "USERS")
        assert len(result) == 1

    def test_fetch_indexes_sync_passes_parameters(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_indexes_sync("SCHEMA", "USERS")
        call_args = manager.execute_custom_many.call_args
        assert call_args[1]["params"]["owner"] == "SCHEMA"
        assert call_args[1]["params"]["table_name"] == "USERS"


class TestOracleAsyncAdapterBasicAsync:
    """Tests basicos para OracleAsyncAdapter (sin verdadero async)."""

    def test_async_adapter_has_manager(self) -> None:
        manager = MagicMock()
        adapter = OracleAsyncAdapter(manager)
        assert adapter.manager is manager

    def test_async_adapter_all_methods_exist(self) -> None:
        manager = MagicMock()
        adapter = OracleAsyncAdapter(manager)

        methods = [
            "fetch_schemas_sync",
            "fetch_tables_sync",
            "fetch_columns_sync",
            "fetch_primary_keys_sync",
            "fetch_foreign_keys_sync",
            "fetch_indexes_sync",
            "get_routine_details",
            "get_routine_parameters_details",
        ]

        for method in methods:
            assert hasattr(adapter, method), f"Missing method: {method}"
            assert callable(getattr(adapter, method))
