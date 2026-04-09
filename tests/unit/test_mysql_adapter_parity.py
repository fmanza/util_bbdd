"""Tests para cumplimiento de protocolos y paridad MySQL."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.mysql.sync_adapter import MysqlSyncAdapter


class TestMysqlSyncAdapterProtocol:
    """Tests para cumplimiento de protocol SourceAdapter."""

    def test_adapter_has_fetch_schemas_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = MysqlSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_schemas_sync")
        assert callable(adapter.fetch_schemas_sync)

    def test_adapter_has_fetch_tables_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = MysqlSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_tables_sync")
        assert callable(adapter.fetch_tables_sync)

    def test_adapter_has_fetch_columns_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = MysqlSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_columns_sync")
        assert callable(adapter.fetch_columns_sync)

    def test_adapter_has_fetch_primary_keys_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = MysqlSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_primary_keys_sync")
        assert callable(adapter.fetch_primary_keys_sync)

    def test_adapter_has_fetch_foreign_keys_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = MysqlSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_foreign_keys_sync")
        assert callable(adapter.fetch_foreign_keys_sync)

    def test_adapter_has_fetch_indexes_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = MysqlSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_indexes_sync")
        assert callable(adapter.fetch_indexes_sync)

    def test_adapter_has_fetch_routines_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = MysqlSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_routines_sync")
        assert callable(adapter.fetch_routines_sync)

    def test_adapter_has_fetch_routine_parameters_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = MysqlSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_routine_parameters_sync")
        assert callable(adapter.fetch_routine_parameters_sync)


class TestMysqlSyncAdapterReturnTypes:
    """Tests para verificar tipos de retorno."""

    def test_fetch_schemas_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = MysqlSyncAdapter(mock_manager)
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

        adapter = MysqlSyncAdapter(mock_manager)
        result = adapter.fetch_tables_sync(schema="myschema")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_columns_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = MysqlSyncAdapter(mock_manager)
        result = adapter.fetch_columns_sync(schema="myschema", table="users")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_primary_keys_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = MysqlSyncAdapter(mock_manager)
        result = adapter.fetch_primary_keys_sync(schema="myschema", table="users")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_foreign_keys_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = MysqlSyncAdapter(mock_manager)
        result = adapter.fetch_foreign_keys_sync(schema="myschema", table="posts")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_indexes_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = MysqlSyncAdapter(mock_manager)
        result = adapter.fetch_indexes_sync(schema="myschema", table="users")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_routines_returns_list(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = MysqlSyncAdapter(mock_manager)
        result = adapter.fetch_routines_sync(schema="myschema")
        assert isinstance(result, list)

    def test_fetch_routine_parameters_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = MysqlSyncAdapter(mock_manager)
        result = adapter.fetch_routine_parameters_sync(schema="myschema", routine_name="sp_test")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)


class TestMysqlSyncAdapterConnectionHandling:
    """Tests para manejo de conexiones."""

    def test_prefers_connection_attribute(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn
        mock_manager.db = None  # Should prefer .connection

        adapter = MysqlSyncAdapter(mock_manager)
        adapter.fetch_schemas_sync()
        mock_conn.execute.assert_called_once()

    def test_fallback_to_db_attribute(self) -> None:
        mock_manager = MagicMock(spec=[])  # No 'connection' attribute
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.db = mock_conn

        adapter = MysqlSyncAdapter(mock_manager)
        adapter.fetch_schemas_sync()
        mock_conn.execute.assert_called_once()

    def test_returns_empty_when_no_connection(self) -> None:
        mock_manager = MagicMock(spec=[])  # No connection attributes
        mock_manager.connection = None
        mock_manager.db = None

        adapter = MysqlSyncAdapter(mock_manager)
        assert adapter.fetch_schemas_sync() == []
        assert adapter.fetch_tables_sync() == []
        assert adapter.fetch_columns_sync() == []
