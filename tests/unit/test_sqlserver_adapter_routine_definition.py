"""Tests de regresión para fetch_routine_definition_sync/async en SQL Server [MSS-02].

Antes de este fix, SqlServerSyncAdapter/SqlServerAsyncAdapter estaban
registrados como RoutineAdapter pero no implementaban fetch_routine_definition_*,
pese a que routines.py::fetch_routine_body_sync ya implementaba la consulta
completa a sys.sql_modules.
"""

from __future__ import annotations

import asyncio

from unittest.mock import MagicMock

from util_bbdd.metadata.sqlserver.async_adapter import SqlServerAsyncAdapter
from util_bbdd.metadata.sqlserver.sync_adapter import SqlServerSyncAdapter


def _make_mock_manager_with_body(body: str | None) -> MagicMock:
    mock_manager = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (body,) if body is not None else None
    mock_manager.connection.execute.return_value = mock_cursor
    return mock_manager


def test_sqlserver_sync_adapter_exposes_fetch_routine_definition_sync() -> None:
    assert hasattr(SqlServerSyncAdapter, "fetch_routine_definition_sync")


def test_sqlserver_async_adapter_exposes_fetch_routine_definition_async() -> None:
    assert hasattr(SqlServerAsyncAdapter, "fetch_routine_definition_async")


def test_fetch_routine_definition_sync_returns_ddl_from_sql_modules() -> None:
    manager = _make_mock_manager_with_body("CREATE PROCEDURE dbo.sp_test AS SELECT 1")
    adapter = SqlServerSyncAdapter(manager)

    ddl = adapter.fetch_routine_definition_sync("dbo", "sp_test", "PROCEDURE")

    assert ddl == "CREATE PROCEDURE dbo.sp_test AS SELECT 1"


def test_fetch_routine_definition_sync_no_connection_returns_empty_string() -> None:
    manager = MagicMock()
    manager.connection = None
    manager.db = None
    adapter = SqlServerSyncAdapter(manager)

    assert adapter.fetch_routine_definition_sync("dbo", "sp_test", "PROCEDURE") == ""


def test_fetch_routine_definition_sync_no_routine_name_returns_empty_string() -> None:
    manager = _make_mock_manager_with_body("CREATE PROCEDURE dbo.sp_test AS SELECT 1")
    adapter = SqlServerSyncAdapter(manager)

    assert adapter.fetch_routine_definition_sync("dbo", "", "PROCEDURE") == ""


def test_fetch_routine_definition_async_returns_ddl_from_sql_modules() -> None:
    manager = _make_mock_manager_with_body("CREATE FUNCTION dbo.fn_test() RETURNS INT AS BEGIN RETURN 1 END")
    adapter = SqlServerAsyncAdapter(manager)

    ddl = asyncio.run(adapter.fetch_routine_definition_async("dbo", "fn_test", "FUNCTION"))

    assert ddl == "CREATE FUNCTION dbo.fn_test() RETURNS INT AS BEGIN RETURN 1 END"


def test_fetch_routine_definition_async_no_connection_returns_empty_string() -> None:
    manager = MagicMock()
    manager.connection = None
    manager.db = None
    adapter = SqlServerAsyncAdapter(manager)

    result = asyncio.run(adapter.fetch_routine_definition_async("dbo", "sp_test", "PROCEDURE"))

    assert result == ""
