"""Contratos de uso de binds en ejecutores sync/async."""

from __future__ import annotations

import json

from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.query.registry import QueryRegistry


def _build_registry(tmp_path) -> QueryRegistry:
    queries_file = tmp_path / "queries.json"
    queries_file.write_text(
        json.dumps(
            {
                "sqlite": {
                    "obtener_tablas": "SELECT '{database}' AS schema_name",
                },
            }
        ),
        encoding="utf-8",
    )
    return QueryRegistry(queries_file=queries_file)


def _build_registry_with_named_bind(tmp_path) -> QueryRegistry:
    queries_file = tmp_path / "queries_with_bind.json"
    queries_file.write_text(
        json.dumps(
            {
                "sqlite": {
                    "get_user_by_id": "SELECT :user_id AS user_id",
                },
            }
        ),
        encoding="utf-8",
    )
    return QueryRegistry(queries_file=queries_file)


def test_sync_resolved_query_executes_without_binds(tmp_path) -> None:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("db",)]
    mock_conn.cursor.return_value = mock_cursor

    executor = SyncQueryExecutor(
        connection_provider=MagicMock(return_value=mock_conn),
        connection_releaser=MagicMock(),
        registry=_build_registry(tmp_path),
    )

    result = executor.execute_query_many("obtener_tablas", "sqlite", {"database": "db"})

    assert result == [("db",)]
    assert mock_cursor.execute.call_args.args == ("SELECT 'db' AS schema_name",)


def test_sync_resolved_query_uses_binds_when_placeholders_remain(tmp_path) -> None:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [(7,)]
    mock_conn.cursor.return_value = mock_cursor

    executor = SyncQueryExecutor(
        connection_provider=MagicMock(return_value=mock_conn),
        connection_releaser=MagicMock(),
        registry=_build_registry_with_named_bind(tmp_path),
    )

    result = executor.execute_query_many("get_user_by_id", "sqlite", {"user_id": 7})

    assert result == [(7,)]
    assert mock_cursor.execute.call_args.args == ("SELECT :user_id AS user_id", {"user_id": 7})


def test_sync_custom_query_uses_binds_only_when_needed(tmp_path) -> None:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("ok",)]
    mock_conn.cursor.return_value = mock_cursor

    executor = SyncQueryExecutor(
        connection_provider=MagicMock(return_value=mock_conn),
        connection_releaser=MagicMock(),
        registry=_build_registry(tmp_path),
    )

    executor.execute_custom_many("SELECT 1")
    assert mock_cursor.execute.call_args.args == ("SELECT 1",)

    executor.execute_custom_many("SELECT :id", {"id": 7})
    assert mock_cursor.execute.call_args.args == ("SELECT :id", {"id": 7})


@pytest.mark.asyncio
async def test_async_resolved_query_executes_without_binds(tmp_path) -> None:
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = [("db",)]
    mock_conn.cursor.return_value = mock_cursor

    executor = AsyncQueryExecutor(
        connection_provider=AsyncMock(return_value=mock_conn),
        connection_releaser=AsyncMock(),
        registry=_build_registry(tmp_path),
    )

    result = await executor.execute_query_many("obtener_tablas", "sqlite", {"database": "db"})

    assert result == [("db",)]
    assert mock_cursor.execute.call_args.args == ("SELECT 'db' AS schema_name",)


@pytest.mark.asyncio
async def test_async_resolved_query_uses_binds_when_placeholders_remain(tmp_path) -> None:
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = [(7,)]
    mock_conn.cursor.return_value = mock_cursor

    executor = AsyncQueryExecutor(
        connection_provider=AsyncMock(return_value=mock_conn),
        connection_releaser=AsyncMock(),
        registry=_build_registry_with_named_bind(tmp_path),
    )

    result = await executor.execute_query_many("get_user_by_id", "sqlite", {"user_id": 7})

    assert result == [(7,)]
    assert mock_cursor.execute.call_args.args == ("SELECT :user_id AS user_id", {"user_id": 7})


@pytest.mark.asyncio
async def test_async_custom_query_uses_binds_only_when_needed(tmp_path) -> None:
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = [("ok",)]
    mock_conn.cursor.return_value = mock_cursor

    executor = AsyncQueryExecutor(
        connection_provider=AsyncMock(return_value=mock_conn),
        connection_releaser=AsyncMock(),
        registry=_build_registry(tmp_path),
    )

    await executor.execute_custom_many("SELECT 1")
    assert mock_cursor.execute.call_args.args == ("SELECT 1",)

    await executor.execute_custom_many("SELECT :id", {"id": 7})
    assert mock_cursor.execute.call_args.args == ("SELECT :id", {"id": 7})
