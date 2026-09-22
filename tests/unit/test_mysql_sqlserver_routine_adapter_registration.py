"""Tests de regresión para el registro de mysql/sqlserver como RoutineAdapter [MDC-03].

Antes de este fix, mysql/__init__.py y sqlserver/__init__.py nunca llamaban
register_routine_adapter_sync/async pese a que se asumía que ya tenían la
capacidad implementada. La verificación reveló que MySQL ni siquiera tenía
fetch_routine_definition_sync/async (implementado aquí desde cero, vía
SHOW CREATE PROCEDURE/FUNCTION) ni fetch_routine_parameters_sync/async aceptaba
routine_type (requerido por el Protocol). SQL Server sí estaba listo (MSS-02,
Fase 3 de esta misma sesión) y solo necesitaba el registro.
"""

from __future__ import annotations

import asyncio

from unittest.mock import MagicMock

import util_bbdd.metadata.mysql  # noqa: F401  (dispara el auto-registro al importar)
import util_bbdd.metadata.sqlserver  # noqa: F401

from util_bbdd.metadata.adapters import get_global_adapter_registry
from util_bbdd.metadata.mysql.async_adapter import MysqlAsyncAdapter
from util_bbdd.metadata.mysql.sync_adapter import MysqlSyncAdapter
from util_bbdd.metadata.sqlserver.sync_adapter import SqlServerSyncAdapter


class TestGlobalRegistryRegistration:
    def test_mysql_registered_as_routine_adapter_sync(self) -> None:
        registry = get_global_adapter_registry()
        assert registry.get_routine_adapter_sync("mysql") is MysqlSyncAdapter

    def test_mysql_registered_as_routine_adapter_async(self) -> None:
        registry = get_global_adapter_registry()
        assert registry.get_routine_adapter_async("mysql") is MysqlAsyncAdapter

    def test_sqlserver_registered_as_routine_adapter_sync(self) -> None:
        registry = get_global_adapter_registry()
        assert registry.get_routine_adapter_sync("sqlserver") is SqlServerSyncAdapter

    def test_mssql_alias_registered_as_routine_adapter_sync(self) -> None:
        registry = get_global_adapter_registry()
        assert registry.get_routine_adapter_sync("mssql") is SqlServerSyncAdapter


class TestMysqlFetchRoutineDefinition:
    def _make_manager(self, ddl: str | None) -> MagicMock:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("sp_test", "sql_mode", ddl, "utf8", "coll", "coll") if ddl else None
        mock_conn.execute.return_value = mock_cursor
        mock_manager.connection = mock_conn
        return mock_manager

    def test_sync_returns_ddl_from_show_create(self) -> None:
        manager = self._make_manager("CREATE PROCEDURE sp_test() BEGIN SELECT 1; END")
        adapter = MysqlSyncAdapter(manager)

        ddl = adapter.fetch_routine_definition_sync("myschema", "sp_test", "PROCEDURE")

        assert ddl == "CREATE PROCEDURE sp_test() BEGIN SELECT 1; END"
        executed_sql = manager.connection.execute.call_args[0][0]
        assert "SHOW CREATE PROCEDURE" in executed_sql

    def test_sync_uses_function_keyword_for_functions(self) -> None:
        manager = self._make_manager("CREATE FUNCTION fn_test() RETURNS INT RETURN 1")
        adapter = MysqlSyncAdapter(manager)

        adapter.fetch_routine_definition_sync("myschema", "fn_test", "FUNCTION")

        executed_sql = manager.connection.execute.call_args[0][0]
        assert "SHOW CREATE FUNCTION" in executed_sql

    def test_sync_no_row_returns_empty_string(self) -> None:
        manager = self._make_manager(None)
        adapter = MysqlSyncAdapter(manager)

        assert adapter.fetch_routine_definition_sync("myschema", "does_not_exist", "PROCEDURE") == ""

    def test_async_returns_ddl_from_show_create(self) -> None:
        manager = self._make_manager("CREATE PROCEDURE sp_test() BEGIN SELECT 1; END")
        adapter = MysqlAsyncAdapter(manager)

        ddl = asyncio.run(adapter.fetch_routine_definition_async("myschema", "sp_test", "PROCEDURE"))

        assert ddl == "CREATE PROCEDURE sp_test() BEGIN SELECT 1; END"


class TestMysqlFetchRoutineParametersAcceptsRoutineType:
    def test_sync_accepts_positional_routine_type(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_manager.connection = mock_conn

        adapter = MysqlSyncAdapter(mock_manager)

        # No debe lanzar TypeError por exceso de argumentos posicionales.
        result = adapter.fetch_routine_parameters_sync("myschema", "sp_test", "PROCEDURE")
        assert result == []

    def test_async_accepts_positional_routine_type(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_manager.connection = mock_conn

        adapter = MysqlAsyncAdapter(mock_manager)

        result = asyncio.run(adapter.fetch_routine_parameters_async("myschema", "sp_test", "PROCEDURE"))
        assert result == []


class TestFetchRoutinesReturnsTuplesNotDataclasses:
    """El Protocol RoutineAdapterSync/Async declara list[tuple]; devolver la dataclass
    interna (MysqlRoutineDetail/SqlServerRoutineDetail) rompía la conformidad
    estructural con mypy en cuanto se añadían al chequeo estático (list es invariante)."""

    def test_mysql_sync_returns_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("sp_test", "PROCEDURE", None)]
        mock_conn.execute.return_value = mock_cursor
        mock_manager.connection = mock_conn

        adapter = MysqlSyncAdapter(mock_manager)
        result = adapter.fetch_routines_sync(schema="myschema")

        assert all(type(r) is tuple for r in result)

    def test_sqlserver_sync_returns_tuples(self) -> None:
        mock_manager = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("sp_test", "PROCEDURE", 123, 0)]
        mock_conn.execute.return_value = mock_cursor
        mock_manager.connection = mock_conn

        adapter = SqlServerSyncAdapter(mock_manager)
        result = adapter.fetch_routines_sync(schema="dbo")

        assert all(type(r) is tuple for r in result)
