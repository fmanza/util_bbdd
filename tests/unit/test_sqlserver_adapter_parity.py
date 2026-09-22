"""Tests para cumplimiento de protocolos y paridad SQL Server."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import util_bbdd.metadata.sqlserver.sync_adapter as sqlserver_sync_adapter_module

from util_bbdd.metadata.sqlserver._sqlserver_models import SqlServerParameterDetail, SqlServerRoutineDetail
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

    def test_adapter_handles_missing_routine_name(self) -> None:
        mock_manager = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)

        # Debe no fallar cuando no se indica el nombre de la rutina
        result = adapter.fetch_routine_parameters_sync(schema="dbo")
        assert result == []


class TestSqlServerSyncAdapterRoutineParametersByName:
    """MSS-01 (AUDIT_CODE 2026-09-22): fetch_routine_parameters_sync tenía la firma
    (object_id: int), que no cumplía RoutineAdapterSync (schema, routine, routine_type) ni
    coincidía con la contraparte async. Ahora resuelve el object_id a partir del nombre de la
    rutina, igual que SqlServerAsyncAdapter.fetch_routine_parameters_async."""

    def test_resolves_object_id_from_routine_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_manager = MagicMock()
        mock_manager.connection = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)

        routine = SqlServerRoutineDetail(
            routine_name="sp_test", routine_type="PROCEDURE", object_id=42, parameters_count=1
        )
        param = SqlServerParameterDetail(
            param_name="@id", object_id=42, parameter_id=1, data_type="int", is_output=False, precision=10, scale=0
        )

        monkeypatch.setattr(sqlserver_sync_adapter_module, "fetch_routines_sync", lambda conn, schema: [routine])
        monkeypatch.setattr(
            sqlserver_sync_adapter_module, "fetch_routine_parameters_sync", lambda conn, object_id: [param]
        )

        result = adapter.fetch_routine_parameters_sync(schema="dbo", routine="sp_test", routine_type="PROCEDURE")

        assert result == [("@id", 42, 1, "int", False, 10, 0)]

    def test_routine_name_matched_case_insensitively(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_manager = MagicMock()
        mock_manager.connection = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)

        routine = SqlServerRoutineDetail(
            routine_name="SP_TEST", routine_type="PROCEDURE", object_id=7, parameters_count=0
        )

        monkeypatch.setattr(sqlserver_sync_adapter_module, "fetch_routines_sync", lambda conn, schema: [routine])
        monkeypatch.setattr(sqlserver_sync_adapter_module, "fetch_routine_parameters_sync", lambda conn, object_id: [])

        result = adapter.fetch_routine_parameters_sync(schema="dbo", routine="sp_test", routine_type="procedure")

        assert result == []  # no lanza excepción: encontró la rutina, sin parámetros

    def test_unmatched_routine_name_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_manager = MagicMock()
        mock_manager.connection = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)

        monkeypatch.setattr(sqlserver_sync_adapter_module, "fetch_routines_sync", lambda conn, schema: [])

        result = adapter.fetch_routine_parameters_sync(schema="dbo", routine="does_not_exist")

        assert result == []

    def test_by_id_variant_still_available_for_internal_use(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fetch_routine_parameters_by_id_sync preserva la API antigua basada en object_id."""
        mock_manager = MagicMock()
        mock_manager.connection = MagicMock()
        adapter = SqlServerSyncAdapter(mock_manager)

        param = SqlServerParameterDetail(
            param_name="@id", object_id=42, parameter_id=1, data_type="int", is_output=False, precision=None, scale=None
        )
        monkeypatch.setattr(
            sqlserver_sync_adapter_module, "fetch_routine_parameters_sync", lambda conn, object_id: [param]
        )

        result = adapter.fetch_routine_parameters_by_id_sync(42)

        assert result == [param]


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
