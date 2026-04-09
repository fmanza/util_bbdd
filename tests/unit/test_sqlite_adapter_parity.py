"""Tests para cumplimiento de protocolos y paridad SQLite."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.sqlite.sync_adapter import SqliteSyncAdapter


class TestSqliteSyncAdapterProtocol:
    """Tests para cumplimiento de protocol SourceAdapter."""

    def test_adapter_has_fetch_schemas_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqliteSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_schemas_sync")
        assert callable(adapter.fetch_schemas_sync)

    def test_adapter_has_fetch_tables_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqliteSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_tables_sync")
        assert callable(adapter.fetch_tables_sync)

    def test_adapter_has_fetch_columns_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqliteSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_columns_sync")
        assert callable(adapter.fetch_columns_sync)

    def test_adapter_has_fetch_primary_keys_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqliteSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_primary_keys_sync")
        assert callable(adapter.fetch_primary_keys_sync)

    def test_adapter_has_fetch_foreign_keys_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqliteSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_foreign_keys_sync")
        assert callable(adapter.fetch_foreign_keys_sync)

    def test_adapter_has_fetch_indexes_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqliteSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_indexes_sync")
        assert callable(adapter.fetch_indexes_sync)

    def test_adapter_has_fetch_triggers_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqliteSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_triggers_sync")
        assert callable(adapter.fetch_triggers_sync)


class TestSqliteSyncAdapterReturnTypes:
    """Tests para verificar tipos de retorno."""

    def test_fetch_schemas_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        adapter = SqliteSyncAdapter(mock_manager)
        result = adapter.fetch_schemas_sync()
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_tables_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqliteSyncAdapter(mock_manager)
        result = adapter.fetch_tables_sync(schema="main")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_columns_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqliteSyncAdapter(mock_manager)
        result = adapter.fetch_columns_sync(schema="main", table="test")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_primary_keys_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqliteSyncAdapter(mock_manager)
        result = adapter.fetch_primary_keys_sync(schema="main", table="test")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_foreign_keys_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqliteSyncAdapter(mock_manager)
        result = adapter.fetch_foreign_keys_sync(schema="main", table="test")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_indexes_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqliteSyncAdapter(mock_manager)
        result = adapter.fetch_indexes_sync(schema="main", table="test")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)


class TestSqliteSyncAdapterConnectionHandling:
    """Tests para manejo de conexiones."""

    def test_adapter_handles_missing_connection(self) -> None:
        mock_manager = MagicMock()
        mock_manager.connection = None

        adapter = SqliteSyncAdapter(mock_manager)

        # Debe retornar lista vacía si no hay conexión
        result = adapter.fetch_tables_sync(schema="main")
        assert result == []

    def test_adapter_uses_manager_connection_attribute(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqliteSyncAdapter(mock_manager)
        adapter.fetch_tables_sync(schema="main")

        # Verificar que se usó la conexión del manager
        assert mock_conn.execute.called

    def test_adapter_uses_manager_db_attribute_fallback(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        # Sin atributo 'connection', pero con 'db'
        del mock_manager.connection
        mock_manager.db = mock_conn

        adapter = SqliteSyncAdapter(mock_manager)
        result = adapter.fetch_tables_sync(schema="main")

        # Debería usar db como fallback
        assert isinstance(result, list)


class TestSqliteSyncAdapterErrorHandling:
    """Tests para manejo de errores."""

    def test_adapter_handles_invalid_schema(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqliteSyncAdapter(mock_manager)

        # Debe no fallar con esquema inválido
        result = adapter.fetch_tables_sync(schema="nonexistent")
        assert isinstance(result, list)

    def test_adapter_handles_empty_parameters(self) -> None:
        mock_manager = MagicMock()
        adapter = SqliteSyncAdapter(mock_manager)

        # Debe no fallar con parámetros vacíos
        result = adapter.fetch_columns_sync("", "")
        assert isinstance(result, list)
