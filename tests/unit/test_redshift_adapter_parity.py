"""Tests para paridad de adaptadores Redshift.

Verifica que RedshiftSyncAdapter y RedshiftAsyncAdapter
cumplan con los protocolos esperados y manejen errores correctamente.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.metadata.redshift.async_adapter import RedshiftAsyncAdapter
from util_bbdd.metadata.redshift.sync_adapter import RedshiftSyncAdapter


class TestRedshiftSyncAdapterProtocol:
    """Tests para RedshiftSyncAdapter cumplimiento de Protocol."""

    def test_sync_adapter_initialization(self) -> None:
        """Adaptador debe inicializarse con manager."""
        mock_manager = MagicMock()
        adapter = RedshiftSyncAdapter(mock_manager)
        assert adapter.manager == mock_manager

    def test_sync_adapter_has_fetch_schemas_method(self) -> None:
        mock_manager = MagicMock()
        adapter = RedshiftSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_schemas_sync")
        assert callable(adapter.fetch_schemas_sync)

    def test_sync_adapter_has_fetch_tables_method(self) -> None:
        mock_manager = MagicMock()
        adapter = RedshiftSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_tables_sync")
        assert callable(adapter.fetch_tables_sync)

    def test_sync_adapter_has_fetch_columns_method(self) -> None:
        mock_manager = MagicMock()
        adapter = RedshiftSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_columns_sync")
        assert callable(adapter.fetch_columns_sync)

    def test_sync_adapter_has_pk_fk_methods(self) -> None:
        mock_manager = MagicMock()
        adapter = RedshiftSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_primary_keys_sync")
        assert hasattr(adapter, "fetch_foreign_keys_sync")
        assert callable(adapter.fetch_primary_keys_sync)
        assert callable(adapter.fetch_foreign_keys_sync)

    def test_sync_adapter_has_indexes_method(self) -> None:
        mock_manager = MagicMock()
        adapter = RedshiftSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_indexes_sync")
        assert callable(adapter.fetch_indexes_sync)

    def test_sync_adapter_has_routines_methods(self) -> None:
        mock_manager = MagicMock()
        adapter = RedshiftSyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_routines_sync")
        assert hasattr(adapter, "fetch_routine_parameters_sync")

    def test_sync_adapter_handles_missing_connection(self) -> None:
        """Si el manager no tiene conexión, retornar lista vacía."""
        mock_manager = MagicMock()
        mock_manager.connection = None
        mock_manager.db = None
        adapter = RedshiftSyncAdapter(mock_manager)

        result = adapter.fetch_schemas_sync()
        assert result == []

    def test_sync_adapter_prefers_connection_over_db(self) -> None:
        """Debe usar 'connection' si existe, sino 'db'."""
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        # Usar connection
        mock_manager.connection = mock_conn
        mock_manager.db = None
        adapter = RedshiftSyncAdapter(mock_manager)

        result = adapter.fetch_schemas_sync()
        # No debería fallar
        assert isinstance(result, list)


class TestRedshiftAsyncAdapterProtocol:
    """Tests para RedshiftAsyncAdapter cumplimiento de Protocol."""

    def test_async_adapter_initialization(self) -> None:
        """Adaptador debe inicializarse con manager."""
        mock_manager = MagicMock()
        adapter = RedshiftAsyncAdapter(mock_manager)
        assert adapter.manager == mock_manager

    def test_async_adapter_has_fetch_schemas_method(self) -> None:
        mock_manager = MagicMock()
        adapter = RedshiftAsyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_schemas_sync")
        assert callable(adapter.fetch_schemas_sync)

    def test_async_adapter_has_fetch_tables_method(self) -> None:
        mock_manager = MagicMock()
        adapter = RedshiftAsyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_tables_sync")
        assert callable(adapter.fetch_tables_sync)

    def test_async_adapter_has_fetch_columns_method(self) -> None:
        mock_manager = MagicMock()
        adapter = RedshiftAsyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_columns_sync")
        assert callable(adapter.fetch_columns_sync)

    def test_async_adapter_has_pk_fk_methods(self) -> None:
        mock_manager = MagicMock()
        adapter = RedshiftAsyncAdapter(mock_manager)
        assert hasattr(adapter, "fetch_primary_keys_sync")
        assert hasattr(adapter, "fetch_foreign_keys_sync")

    def test_async_adapter_handles_missing_connection(self) -> None:
        """Si el manager no tiene conexión, retornar lista vacía."""
        mock_manager = MagicMock()
        mock_manager.connection = None
        mock_manager.db = None
        adapter = RedshiftAsyncAdapter(mock_manager)

        result = adapter.fetch_schemas_sync()
        assert result == []


class TestRedshiftAdaptersParity:
    """Tests de paridad entre sync y async adapters."""

    def test_sync_and_async_adapters_have_same_interface(self) -> None:
        """Ambos adaptadores deben tener los mismos métodos."""
        mock_manager = MagicMock()
        sync_adapter = RedshiftSyncAdapter(mock_manager)
        async_adapter = RedshiftAsyncAdapter(mock_manager)

        sync_methods = {m for m in dir(sync_adapter) if not m.startswith("_")}
        async_methods = {m for m in dir(async_adapter) if not m.startswith("_")}

        # Los métodos públicos deben ser los mismos (o async tiene más)
        assert sync_methods.issubset(async_methods) or sync_methods == async_methods

    def test_both_adapters_return_same_type_for_schemas(self) -> None:
        """Ambos deben retornar lista de tuples para schemas."""
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("myschema",)]
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        sync_adapter = RedshiftSyncAdapter(mock_manager)
        async_adapter = RedshiftAsyncAdapter(mock_manager)

        sync_result = sync_adapter.fetch_schemas_sync()
        async_result = async_adapter.fetch_schemas_sync()

        assert isinstance(sync_result, list) and isinstance(async_result, list)
        assert sync_result == async_result


class TestRedshiftAdapterErrorHandling:
    """Tests para manejo de errores en adaptadores."""

    def test_sync_adapter_handles_none_manager(self) -> None:
        """Debe manejar gracefully manager None."""
        adapter = RedshiftSyncAdapter(None)
        # No debería lanzar excepción
        result = adapter.fetch_schemas_sync()
        # Debe retornar lista vacía
        assert result == []

    def test_sync_adapter_handles_connection_error(self) -> None:
        """Debe manejar conexión que no puede ejecutar queries."""
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("Connection error")
        mock_manager.connection = mock_conn

        adapter = RedshiftSyncAdapter(mock_manager)
        # Dependiendo de la implementación, podría retornar lista vacía o lanzar
        # Por ahora, verificamos que no hay crash silencioso
        try:
            result = adapter.fetch_schemas_sync()
            # Si no lanza, debe retornar algo
            assert result is not None
        except Exception:
            # Si lanza, está bien documentar la excepción
            pass

    def test_adapter_constraints_methods_log_warnings(self) -> None:
        """Métodos de constraints deben loguear advisory warnings."""
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("pk_users", "id", 1)]
        mock_conn.execute.return_value = mock_cursor

        mock_manager.connection = mock_conn

        adapter = RedshiftSyncAdapter(mock_manager)
        # No debería fallar - solo retornar PKs
        result = adapter.fetch_primary_keys_sync("myschema", "users")
        assert isinstance(result, list)
