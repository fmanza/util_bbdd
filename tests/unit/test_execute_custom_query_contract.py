"""Contrato de execute_custom_many/one en sync y async."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd.exceptions import DatabaseOperationError, QueryNotFoundError
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.managers import AsyncDatabaseManager, SyncDatabaseManager


def test_sync_executor_custom_many_and_one_delegate_to_execute_custom_internal() -> None:
    executor = SyncQueryExecutor(MagicMock(), MagicMock())
    executor._execute_custom = MagicMock(side_effect=[[("users",)], ("users",)])

    many_result = executor.execute_custom_many("SELECT * FROM users")
    one_result = executor.execute_custom_one("SELECT * FROM users")

    assert many_result == [("users",)]
    assert one_result == ("users",)
    assert executor._execute_custom.call_count == 2


@pytest.mark.asyncio
async def test_async_executor_custom_many_and_one_delegate_to_execute_custom_internal() -> None:
    executor = AsyncQueryExecutor(AsyncMock(), AsyncMock())
    executor._execute_custom = AsyncMock(side_effect=[[("users",)], ("users",)])

    many_result = await executor.execute_custom_many("SELECT * FROM users")
    one_result = await executor.execute_custom_one("SELECT * FROM users")

    assert many_result == [("users",)]
    assert one_result == ("users",)
    assert executor._execute_custom.await_count == 2


def test_database_manager_execute_custom_many_and_one_use_sync_executor() -> None:
    manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
    manager.logger = MagicMock()
    manager.db_type = "sqlite"
    manager.sync_query_executor = MagicMock()
    manager.sync_query_executor.execute_custom_many.return_value = [("a",)]
    manager.sync_query_executor.execute_custom_one.return_value = ("a",)

    many_result = SyncDatabaseManager.execute_custom_many(manager, "SELECT * FROM users")
    one_result = SyncDatabaseManager.execute_custom_one(manager, "SELECT * FROM users")

    assert many_result == [("a",)]
    assert one_result == ("a",)
    manager.sync_query_executor.execute_custom_many.assert_called_once_with(
        sql="SELECT * FROM users",
        params=None,
        timeout=None,
    )
    manager.sync_query_executor.execute_custom_one.assert_called_once_with(
        sql="SELECT * FROM users",
        params=None,
        timeout=None,
    )


def test_database_manager_execute_custom_many_propagates_query_error_and_timeout() -> None:
    manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
    manager.logger = MagicMock()
    manager.db_type = "sqlite"
    manager.sync_query_executor = MagicMock()
    manager.sync_query_executor.execute_custom_many.side_effect = QueryNotFoundError("custom missing")

    with pytest.raises(QueryNotFoundError):
        SyncDatabaseManager.execute_custom_many(manager, "SELECT * FROM users", timeout=2.0)

    manager.sync_query_executor.execute_custom_many.assert_called_once_with(
        sql="SELECT * FROM users",
        params=None,
        timeout=2.0,
    )


def test_database_manager_execute_custom_many_wraps_unexpected_errors_with_cause() -> None:
    manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
    manager.logger = MagicMock()
    manager.db_type = "sqlite"
    manager.sync_query_executor = MagicMock()
    manager.sync_query_executor.execute_custom_many.side_effect = RuntimeError("custom driver broke")

    with pytest.raises(DatabaseOperationError) as exc_info:
        SyncDatabaseManager.execute_custom_many(manager, "SELECT * FROM users")

    assert isinstance(exc_info.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_async_database_manager_execute_custom_many_and_one() -> None:
    manager = AsyncDatabaseManager(
        db_type="mariadb",
        conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
        use_pool=False,
    )
    manager._initialized = True
    manager.query_executor = AsyncMock()
    manager.query_executor.execute_custom_many = AsyncMock(return_value=[("a",)])
    manager.query_executor.execute_custom_one = AsyncMock(return_value=("a",))

    many_result = await manager.execute_custom_many("SELECT * FROM users")
    one_result = await manager.execute_custom_one("SELECT * FROM users")

    assert many_result == [("a",)]
    assert one_result == ("a",)
    manager.query_executor.execute_custom_many.assert_awaited_once_with(
        sql="SELECT * FROM users",
        params=None,
    )
    manager.query_executor.execute_custom_one.assert_awaited_once_with(
        sql="SELECT * FROM users",
        params=None,
    )


@pytest.mark.asyncio
async def test_async_database_manager_execute_custom_many_propagates_query_error() -> None:
    manager = AsyncDatabaseManager(
        db_type="mariadb",
        conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
        use_pool=False,
    )
    manager._initialized = True
    manager.query_executor = AsyncMock()
    manager.query_executor.execute_custom_many = AsyncMock(side_effect=QueryNotFoundError("custom missing"))

    with pytest.raises(QueryNotFoundError):
        await manager.execute_custom_many("SELECT * FROM users")

    manager.query_executor.execute_custom_many.assert_awaited_once_with(
        sql="SELECT * FROM users",
        params=None,
    )


@pytest.mark.asyncio
async def test_async_database_manager_execute_custom_many_wraps_unexpected_errors_with_cause() -> None:
    manager = AsyncDatabaseManager(
        db_type="mariadb",
        conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
        use_pool=False,
    )
    manager._initialized = True
    manager.query_executor = AsyncMock()
    manager.query_executor.execute_custom_many = AsyncMock(side_effect=RuntimeError("async custom driver broke"))

    with pytest.raises(DatabaseOperationError) as exc_info:
        await manager.execute_custom_many("SELECT * FROM users")

    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_legacy_execute_custom_query_api_removed() -> None:
    assert not hasattr(SyncDatabaseManager, "execute_custom_query")
    assert not hasattr(AsyncDatabaseManager, "execute_custom_query")
