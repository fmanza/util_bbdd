"""Contrato de execute_query_many/one en sync y async."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd.database_exceptions import DatabaseOperationError, QueryNotFoundError
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.managers import AsyncDatabaseManager, SyncDatabaseManager


def test_sync_executor_many_and_one_delegate_to_execute_resolved() -> None:
    executor = SyncQueryExecutor(MagicMock(), MagicMock())
    executor._execute_resolved = MagicMock(side_effect=[[("users",)], ("users",)])

    many_result = executor.execute_query_many("obtener_tablas", "mariadb", {"database": "db"})
    one_result = executor.execute_query_one("obtener_tablas", "mariadb", {"database": "db"})

    assert many_result == [("users",)]
    assert one_result == ("users",)
    assert executor._execute_resolved.call_count == 2


@pytest.mark.asyncio
async def test_async_executor_many_and_one_delegate_to_execute_resolved() -> None:
    executor = AsyncQueryExecutor(AsyncMock(), AsyncMock())
    executor._execute_resolved = AsyncMock(side_effect=[[("users",)], ("users",)])

    many_result = await executor.execute_query_many("obtener_tablas", "mariadb", {"database": "db"})
    one_result = await executor.execute_query_one("obtener_tablas", "mariadb", {"database": "db"})

    assert many_result == [("users",)]
    assert one_result == ("users",)
    assert executor._execute_resolved.await_count == 2


def test_database_manager_execute_query_many_and_one_use_sync_executor() -> None:
    manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
    manager.logger = MagicMock()
    manager.db_type = "sqlite"
    manager.sync_query_executor = MagicMock()
    manager.sync_query_executor.execute_query_many.return_value = [("a",)]
    manager.sync_query_executor.execute_query_one.return_value = ("a",)

    many_result = SyncDatabaseManager.execute_query_many(manager, "q_tables", table="users")
    one_result = SyncDatabaseManager.execute_query_one(manager, "q_table", table="users")

    assert many_result == [("a",)]
    assert one_result == ("a",)
    manager.sync_query_executor.execute_query_many.assert_called_once_with(
        query_name="q_tables",
        db_type="sqlite",
        params={"table": "users"},
        timeout=None,
    )
    manager.sync_query_executor.execute_query_one.assert_called_once_with(
        query_name="q_table",
        db_type="sqlite",
        params={"table": "users"},
        timeout=None,
    )


def test_database_manager_execute_query_many_propagates_query_error_and_timeout() -> None:
    manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
    manager.logger = MagicMock()
    manager.db_type = "sqlite"
    manager.sync_query_executor = MagicMock()
    manager.sync_query_executor.execute_query_many.side_effect = QueryNotFoundError("query missing")

    with pytest.raises(QueryNotFoundError):
        SyncDatabaseManager.execute_query_many(manager, "q_tables", timeout=1.5, table="users")

    manager.sync_query_executor.execute_query_many.assert_called_once_with(
        query_name="q_tables",
        db_type="sqlite",
        params={"table": "users"},
        timeout=1.5,
    )


def test_database_manager_execute_query_many_wraps_unexpected_errors_with_cause() -> None:
    manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
    manager.logger = MagicMock()
    manager.db_type = "sqlite"
    manager.sync_query_executor = MagicMock()
    manager.sync_query_executor.execute_query_many.side_effect = RuntimeError("driver broke")

    with pytest.raises(DatabaseOperationError) as exc_info:
        SyncDatabaseManager.execute_query_many(manager, "q_tables", table="users")

    assert isinstance(exc_info.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_async_database_manager_execute_query_many_and_one() -> None:
    manager = AsyncDatabaseManager(db_type="mariadb", conn_params={"database": "db"}, use_pool=False)
    manager._initialized = True
    manager.query_executor = AsyncMock()
    manager.query_executor.execute_query_many = AsyncMock(return_value=[("a",)])
    manager.query_executor.execute_query_one = AsyncMock(return_value=("a",))

    many_result = await manager.execute_query_many("q_tables", database="db")
    one_result = await manager.execute_query_one("q_table", database="db")

    assert many_result == [("a",)]
    assert one_result == ("a",)
    manager.query_executor.execute_query_many.assert_awaited_once_with(
        query_name="q_tables",
        db_type="mariadb",
        params={"database": "db"},
    )
    manager.query_executor.execute_query_one.assert_awaited_once_with(
        query_name="q_table",
        db_type="mariadb",
        params={"database": "db"},
    )


@pytest.mark.asyncio
async def test_async_database_manager_execute_query_many_propagates_query_error() -> None:
    manager = AsyncDatabaseManager(db_type="mariadb", conn_params={"database": "db"}, use_pool=False)
    manager._initialized = True
    manager.query_executor = AsyncMock()
    manager.query_executor.execute_query_many = AsyncMock(side_effect=QueryNotFoundError("query missing"))

    with pytest.raises(QueryNotFoundError):
        await manager.execute_query_many("q_tables", database="db")

    manager.query_executor.execute_query_many.assert_awaited_once_with(
        query_name="q_tables",
        db_type="mariadb",
        params={"database": "db"},
    )


@pytest.mark.asyncio
async def test_async_database_manager_execute_query_many_wraps_unexpected_errors_with_cause() -> None:
    manager = AsyncDatabaseManager(db_type="mariadb", conn_params={"database": "db"}, use_pool=False)
    manager._initialized = True
    manager.query_executor = AsyncMock()
    manager.query_executor.execute_query_many = AsyncMock(side_effect=RuntimeError("async driver broke"))

    with pytest.raises(DatabaseOperationError) as exc_info:
        await manager.execute_query_many("q_tables", database="db")

    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_legacy_execute_query_api_removed() -> None:
    assert not hasattr(SyncDatabaseManager, "execute_query")
    assert not hasattr(AsyncDatabaseManager, "execute_query")
