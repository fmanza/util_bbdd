"""Validación de wrapping de errores con `raise ... from err`."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd.database_exceptions import DatabaseOperationError, QueryParameterError
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.query import QueryRegistry, QueryResolver


def test_sync_executor_wraps_custom_errors_with_cause() -> None:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = RuntimeError("driver explosion")
    mock_conn.cursor.return_value = mock_cursor

    executor = SyncQueryExecutor(
        connection_provider=MagicMock(return_value=mock_conn),
        connection_releaser=MagicMock(),
        registry=QueryRegistry(),
    )

    with pytest.raises(DatabaseOperationError) as exc_info:
        executor.execute_custom_many("SELECT 1")

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "driver explosion" in str(exc_info.value.__cause__)


@pytest.mark.asyncio
async def test_async_executor_wraps_custom_errors_with_cause() -> None:
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.execute.side_effect = RuntimeError("async driver explosion")
    mock_conn.cursor.return_value = mock_cursor

    executor = AsyncQueryExecutor(
        connection_provider=AsyncMock(return_value=mock_conn),
        connection_releaser=AsyncMock(),
        registry=QueryRegistry(),
    )

    with pytest.raises(DatabaseOperationError) as exc_info:
        await executor.execute_custom_many("SELECT 1")

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "async driver explosion" in str(exc_info.value.__cause__)


def test_query_resolver_wraps_unexpected_errors_with_cause() -> None:
    class BrokenRegistry(QueryRegistry):
        def __init__(self) -> None:
            self.logger = MagicMock()

        def get_query_definition(self, db_type: str, query_name: str) -> Any:
            raise RuntimeError("broken registry")

    resolver = QueryResolver(registry=BrokenRegistry())

    with pytest.raises(QueryParameterError) as exc_info:
        resolver.resolve("obtener_tablas", "mariadb", {"database": "db"})

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "broken registry" in str(exc_info.value.__cause__)
