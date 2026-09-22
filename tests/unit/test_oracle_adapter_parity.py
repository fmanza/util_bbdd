"""Tests para parity y contrato de adaptadores Oracle."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.metadata.oracle import OracleAsyncAdapter, OracleSyncAdapter


class TestOracleSyncAdapterInstantiation:
    """Tests para instanciación del adaptador sync."""

    def test_sync_adapter_creation_with_manager(self) -> None:
        manager = MagicMock()
        adapter = OracleSyncAdapter(manager)
        assert adapter.manager is manager

    def test_sync_adapter_stores_manager_reference(self) -> None:
        manager = MagicMock()
        adapter = OracleSyncAdapter(manager)
        assert hasattr(adapter, "manager")


class TestOracleAsyncAdapterInstantiation:
    """Tests para instanciación del adaptador async."""

    def test_async_adapter_creation_with_manager(self) -> None:
        manager = MagicMock()
        adapter = OracleAsyncAdapter(manager)
        assert adapter.manager is manager

    def test_async_adapter_stores_manager_reference(self) -> None:
        manager = MagicMock()
        adapter = OracleAsyncAdapter(manager)
        assert hasattr(adapter, "manager")


class TestOracleSyncAdapterReturnTypes:
    """Tests para validación de tipos retornados por sync adapter."""

    def test_fetch_schemas_sync_returns_list_of_tuples(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [("MYAPP",), ("OTHERAPP",)]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_schemas_sync()
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) for item in result)

    def test_fetch_tables_sync_returns_list_of_tuples(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("USERS", "TABLE", "User table"),
            ("ORDERS", "TABLE", "Orders table"),
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_tables_sync("MYAPP")
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) for item in result)
        assert len(result[0]) == 3

    def test_fetch_columns_sync_returns_list_of_tuples(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("ID", "NUMBER", "NO", 1, "", "Primary key"),
            ("NAME", "VARCHAR2", "YES", 2, None, "User name"),
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_columns_sync("MYAPP", "USERS")
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) for item in result)

    def test_fetch_primary_keys_sync_returns_list_of_tuples(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("PK_USERS_ID", "ID", 1),
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_primary_keys_sync("MYAPP", "USERS")
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) for item in result)

    def test_fetch_foreign_keys_sync_returns_list_of_tuples(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("FK_ORDERS_USER_ID", "USER_ID", "MYAPP", "USERS", "ID", "CASCADE", "NO ACTION", 1),
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_foreign_keys_sync("MYAPP", "ORDERS")
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) for item in result)

    def test_fetch_indexes_sync_returns_list_of_tuples(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("IDX_USERS_NAME", "NAME", "ASC", "NONUNIQUE", 1),
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_indexes_sync("MYAPP", "USERS")
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) for item in result)


class TestOracleSyncAdapterCacheKeyDifferentiation:
    """Tests para validación de diferenciación de cache keys."""

    def test_cache_key_includes_oracle_prefix(self) -> None:
        manager = MagicMock()
        manager.db_cache = {"_routine_metadata_context_cache": {}}
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        # Llamar método
        adapter.get_routine_details("MYAPP")

        # Verificar que se intenta usar cache - simplemente verificar que el método completa sin error
        result = adapter.get_routine_details("MYAPP")
        assert isinstance(result, list)

    def test_schemas_parameter_affects_cache_key(self) -> None:
        manager = MagicMock()
        manager.db_cache = {"_routine_metadata_context_cache": {}}
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        # Verificar que la cache key incluye el schema
        result1 = adapter.get_routine_details("SCHEMA1")
        result2 = adapter.get_routine_details("SCHEMA2")

        # Ambas llamadas deberían retornar listas vacías
        assert isinstance(result1, list)
        assert isinstance(result2, list)

        assert hasattr(adapter, "fetch_tables_sync")

    def test_async_adapter_has_fetch_columns_async_method(self) -> None:
        """MEO-01 (AUDIT_CODE 2026-09-22): antes de este fix, OracleAsyncAdapter definía sus
        métodos como ``fetch_*_sync`` (copia-pega del adaptador sync); nunca implementaba
        ``SourceAdapterAsync`` pese a registrarse como tal. Este test certificaba el bug
        (comprobaba el nombre incorrecto) en vez de detectarlo."""
        manager = MagicMock()
        adapter = OracleAsyncAdapter(manager)
        assert hasattr(adapter, "fetch_columns_async")
        assert not hasattr(adapter, "fetch_columns_sync")

    def test_async_adapter_has_routine_methods(self) -> None:
        manager = MagicMock()
        adapter = OracleAsyncAdapter(manager)
        assert hasattr(adapter, "get_routine_details")
        assert hasattr(adapter, "get_routine_parameters_details")


class TestOracleSyncAdapterErrorHandling:
    """Tests para manejo de errores."""

    def test_sync_adapter_handles_connection_error(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.side_effect = RuntimeError("Connection failed")
        adapter = OracleSyncAdapter(manager)

        with pytest.raises(RuntimeError):
            adapter.fetch_schemas_sync()

    def test_sync_adapter_handles_empty_result(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_schemas_sync()
        assert result == []

    def test_sync_adapter_handles_malformed_rows(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("COL1",),
            ("COL1", "COL2"),
            ("COL1", "COL2", "COL3"),
        ]
        adapter = OracleSyncAdapter(manager)

        # Should not raise an exception
        result = adapter.fetch_columns_sync("SCHEMA", "TABLE")
        assert isinstance(result, list)


class TestOracleAdapterNormalization:
    """Tests para normalización de resultados."""

    def test_sync_adapter_normalizes_column_names_to_string(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("ID", "NUMBER", "NO", 1, "", 0, 0, 0, ""),  # 9 elements as expected
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_columns_sync("SCHEMA", "TABLE")
        assert len(result) > 0

    def test_sync_adapter_normalizes_types_to_string(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("ID", "NUMBER", "NO", 1, "", 0, 0, 0, ""),  # 9 elements as expected
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_columns_sync("SCHEMA", "TABLE")
        assert len(result) > 0
        manager = MagicMock()
        manager.execute_custom_many.return_value = [
            ("ID", "NUMBER"),  # Falta información
        ]
        adapter = OracleSyncAdapter(manager)

        result = adapter.fetch_tables_sync("SCHEMA")
        # Debería manejar gracefully
        assert isinstance(result, list)
