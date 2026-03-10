"""Pruebas específicas de comportamiento de timeout en sync/async executors."""

from __future__ import annotations

import asyncio
import json
import tempfile
import time

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd.database_exceptions import QueryTimeoutError
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.query_registry import QueryRegistry


@pytest.fixture
def timeout_queries_file() -> Path:
    queries_data = {
        "mariadb": {
            "obtener_tablas": "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = {database}",
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(queries_data, f)
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink(missing_ok=True)


def test_sync_execute_query_timeout_behavior(timeout_queries_file: Path) -> None:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    def slow_execute(_sql: str, _params: dict[str, str]) -> None:
        time.sleep(0.05)

    mock_cursor.execute.side_effect = slow_execute
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor

    executor = SyncQueryExecutor(
        connection_provider=MagicMock(return_value=mock_conn),
        connection_releaser=MagicMock(),
        registry=QueryRegistry(timeout_queries_file),
    )

    with pytest.raises(QueryTimeoutError):
        executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test_db"}, timeout=0.01)


def test_sync_execute_custom_query_timeout_behavior(timeout_queries_file: Path) -> None:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    def slow_execute(_sql: str, _params: dict[str, str]) -> None:
        time.sleep(0.05)

    mock_cursor.execute.side_effect = slow_execute
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

    async def slow_execute(_sql: str, _params: dict[str, str] | None) -> None:
        await asyncio.sleep(0.05)

    mock_cursor.execute.side_effect = slow_execute
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

    async def slow_execute(_sql: str, _params: dict[str, str] | None) -> None:
        await asyncio.sleep(0.05)

    mock_cursor.execute.side_effect = slow_execute
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor

    executor = AsyncQueryExecutor(
        connection_provider=AsyncMock(return_value=mock_conn),
        connection_releaser=AsyncMock(),
        registry=QueryRegistry(timeout_queries_file),
    )

    with pytest.raises(QueryTimeoutError):
        await executor.execute_custom_many("SELECT 1", deadline_seconds=0.01)
