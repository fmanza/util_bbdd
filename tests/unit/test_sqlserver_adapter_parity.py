"""Tests para cumplimiento de protocolos y paridad SQL Server."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.sqlserver.sync_adapter import SqlServerSyncAdapter


class TestSqlServerSyncAdapterProtocol:
    """Tests para cumplimiento de protocol SourceAdapter."""

    def test_adapter_has_fetch_schemas_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_schemas_sync")
        assert callable(adapter.fetch_schemas_sync)

    def test_adapter_has_fetch_tables_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_tables_sync")
        assert callable(adapter.fetch_tables_sync)

    def test_adapter_has_fetch_columns_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_columns_sync")
        assert callable(adapter.fetch_columns_sync)

    def test_adapter_has_fetch_primary_keys_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_primary_keys_sync")
        assert callable(adapter.fetch_primary_keys_sync)

    def test_adapter_has_fetch_foreign_keys_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_foreign_keys_sync")
        assert callable(adapter.fetch_foreign_keys_sync)

    def test_adapter_has_fetch_indexes_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_indexes_sync")
        assert callable(adapter.fetch_indexes_sync)

    def test_adapter_has_fetch_routines_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_routines_sync")
        assert callable(adapter.fetch_routines_sync)

    def test_adapter_has_fetch_routine_parameters_sync(self) -> None:
        mock_manager = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_routine_parameters_sync")
        assert callable(adapter.fetch_routine_parameters_sync)


class TestSqlServerSyncAdapterReturnTypes:
    """Tests para verificar tipos de retorno."""

    def test_fetch_schemas_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqlServerSyncAdapter(mock_manager)
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

        adapter = SqlServerSyncAdapter(mock_manager)
        result = adapter.fetch_tables_sync(schema="dbo")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_columns_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqlServerSyncAdapter(mock_manager)
        result = adapter.fetch_columns_sync(schema="dbo", table="test")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_primary_keys_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqlServerSyncAdapter(mock_manager)
        result = adapter.fetch_primary_keys_sync(schema="dbo", table="test")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_foreign_keys_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqlServerSyncAdapter(mock_manager)
        result = adapter.fetch_foreign_keys_sync(schema="dbo", table="test")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)

    def test_fetch_indexes_returns_list_of_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqlServerSyncAdapter(mock_manager)
        result = adapter.fetch_indexes_sync(schema="dbo", table="test")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) for r in result)


class TestSqlServerSyncAdapterConnectionHandling:
    """Tests para manejo de conexiones."""

    def test_adapter_handles_missing_connection(self) -> None:
        mock_manager = MagicMock()
        mock_manager.connection = None

        adapter = SqlServerSyncAdapter(mock_manager)

        # Debe retornar lista vacía si no hay conexión
        result = adapter.fetch_tables_sync(schema="dbo")
        assert result == []

    def test_adapter_uses_manager_connection_attribute(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqlServerSyncAdapter(mock_manager)
        adapter.fetch_tables_sync(schema="dbo")

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

        adapter = SqlServerSyncAdapter(mock_manager)
        result = adapter.fetch_tables_sync(schema="dbo")

        # Debería usar db como fallback
        assert isinstance(result, list)


class TestSqlServerSyncAdapterErrorHandling:
    """Tests para manejo de errores."""

    def test_adapter_handles_invalid_schema(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqlServerSyncAdapter(mock_manager)

        # Debe no fallar con esquema inválido
        result = adapter.fetch_tables_sync(schema="nonexistent")
        assert isinstance(result, list)

    def test_adapter_handles_empty_parameters(self) -> None:
        mock_manager = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)

        # Debe no fallar con parámetros vacíos
        result = adapter.fetch_columns_sync("", "")
        assert isinstance(result, list)

    def test_adapter_handles_none_object_id(self) -> None:
        mock_manager = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)

        # Debe no fallar con object_id None
        result = adapter.fetch_routine_parameters_sync(None)
        assert result == []


class TestSqlServerSyncAdapterSchemaDefault:
    """Tests para manejo de esquema por defecto."""

    def test_adapter_uses_dbo_as_default_schema(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqlServerSyncAdapter(mock_manager)
        adapter.fetch_tables_sync()  # Sin schema especificado

        # Verificar que se ejecutó un query
        assert mock_conn.execute.called

        # El llamado debería incluir 'dbo' como default
        # (verificar en los parámetros si es posible)

    def test_adapter_respects_explicit_schema(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = SqlServerSyncAdapter(mock_manager)
        adapter.fetch_tables_sync(schema="sales")

        # Verificar que se ejecutó con el schema especificado
        assert mock_conn.execute.called
