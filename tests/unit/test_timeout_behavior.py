"""Pruebas específicas de comportamiento de timeout en sync/async executors."""

from __future__ import annotations

import asyncio
import json

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd.exceptions import QueryTimeoutError
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.query import QueryRegistry


@pytest.fixture(scope="module")
def timeout_queries_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    queries_data = {
        "mariadb": {
            "obtener_tablas": "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = {database}",
        }
    }
    temp_path = tmp_path_factory.mktemp("timeout_behavior") / "timeout_queries.json"
    temp_path.write_text(json.dumps(queries_data), encoding="utf-8")
    return temp_path


def test_sync_execute_query_timeout_behavior(timeout_queries_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    def execute_noop(*_args, **_kwargs) -> None:
        return None

    ticks = iter([100.0, 100.0, 100.0, 100.02])
    monkeypatch.setattr(
        "util_bbdd.executors.sync_query_executor.time.monotonic",
        lambda: next(ticks, 100.02),
    )
    mock_cursor.execute.side_effect = execute_noop
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor

    executor = SyncQueryExecutor(
        connection_provider=MagicMock(return_value=mock_conn),
        connection_releaser=MagicMock(),
        registry=QueryRegistry(timeout_queries_file),
    )

    with pytest.raises(QueryTimeoutError):
        executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test_db"}, timeout=0.01)


def test_sync_execute_custom_query_timeout_behavior(
    timeout_queries_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    def execute_noop(*_args, **_kwargs) -> None:
        return None

    ticks = iter([200.0, 200.0, 200.02])
    monkeypatch.setattr(
        "util_bbdd.executors.sync_query_executor.time.monotonic",
        lambda: next(ticks, 200.02),
    )
    mock_cursor.execute.side_effect = execute_noop
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor

    executor = SyncQueryExecutor(
        connection_provider=MagicMock(return_value=mock_conn),
        connection_releaser=MagicMock(),
        registry=QueryRegistry(timeout_queries_file),
    )

    with pytest.raises(QueryTimeoutError):
        executor.execute_custom_many("SELECT 1", timeout=0.01)


@pytest.mark.asyncio
async def test_async_execute_query_timeout_behavior(timeout_queries_file: Path) -> None:
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    blocker = asyncio.Event()

    async def blocking_execute(*_args, **_kwargs) -> None:
        await blocker.wait()

    mock_cursor.execute.side_effect = blocking_execute
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor

    executor = AsyncQueryExecutor(
        connection_provider=AsyncMock(return_value=mock_conn),
        connection_releaser=AsyncMock(),
        registry=QueryRegistry(timeout_queries_file),
    )

    with pytest.raises(QueryTimeoutError):
        await executor.execute_query_many(
            "obtener_tablas",
            "mariadb",
            {"database": "test_db"},
            deadline_seconds=0.01,
        )


@pytest.mark.asyncio
async def test_async_execute_custom_query_timeout_behavior(timeout_queries_file: Path) -> None:
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    blocker = asyncio.Event()

    async def blocking_execute(*_args, **_kwargs) -> None:
        await blocker.wait()

    mock_cursor.execute.side_effect = blocking_execute
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor

    executor = AsyncQueryExecutor(
        connection_provider=AsyncMock(return_value=mock_conn),
        connection_releaser=AsyncMock(),
        registry=QueryRegistry(timeout_queries_file),
    )

    with pytest.raises(QueryTimeoutError):
        await executor.execute_custom_many("SELECT 1", deadline_seconds=0.01)
