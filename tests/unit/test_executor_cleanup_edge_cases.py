"""Edge cases for executor cleanup paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.query import QueryRegistry


def test_sync_custom_query_returns_result_when_cursor_close_fails() -> None:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("ok",)]
    mock_cursor.close.side_effect = RuntimeError("close failed")
    mock_conn.cursor.return_value = mock_cursor

    releaser = MagicMock()
    executor = SyncQueryExecutor(
        connection_provider=MagicMock(return_value=mock_conn),
        connection_releaser=releaser,
        registry=QueryRegistry(),
    )

    result = executor.execute_custom_many("SELECT 1")

    assert result == [("ok",)]
    mock_cursor.close.assert_called_once()
    releaser.assert_called_once_with(mock_conn)


@pytest.mark.asyncio
async def test_async_custom_query_returns_result_when_cursor_close_fails() -> None:
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = [("ok",)]
    mock_cursor.close.side_effect = RuntimeError("close failed")
    mock_conn.cursor.return_value = mock_cursor

    releaser = AsyncMock()
    executor = AsyncQueryExecutor(
        connection_provider=AsyncMock(return_value=mock_conn),
        connection_releaser=releaser,
        registry=QueryRegistry(),
    )

    result = await executor.execute_custom_many("SELECT 1")

    assert result == [("ok",)]
    mock_cursor.close.assert_awaited_once()
    releaser.assert_awaited_once_with(mock_conn)
