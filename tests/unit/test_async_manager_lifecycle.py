"""Tests de ciclo de vida para AsyncDatabaseManager."""

from __future__ import annotations

import asyncio

import pytest

from util_bbdd import AsyncDatabaseManager
from util_bbdd.exceptions import DatabaseOperationError
from util_bbdd.managers._manager_lifecycle import close_async_resources

#: conn_params mínimos válidos por motor: desde v0.37.0 AsyncDatabaseManager los valida como el sync.
_MIN_PARAMS: dict[str, dict] = {
    "mariadb": {"host": "localhost", "user": "u", "password": "p", "database": "db"},
    "mysql": {"host": "localhost", "user": "u", "password": "p", "database": "db"},
    "postgresql": {"host": "localhost", "user": "u", "password": "p", "database": "db"},
    "sqlserver": {"host": "localhost", "user": "u", "password": "p", "database": "db"},
    "oracle": {"user": "u", "password": "p", "service_name": "XE"},
    "sqlite": {"database": ":memory:"},
    "hsqldb": {"user": "u", "jdbc_url": "jdbc:hsqldb:mem:x", "jdbc_jar": "x.jar"},
}


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False
        self.last_sql = None
        self.last_params = None

    async def execute(self, query: str, params=None):
        await asyncio.sleep(0)
        self.last_sql = query
        self.last_params = params

    async def fetchone(self):
        await asyncio.sleep(0)
        return ("one",)

    async def fetchall(self):
        await asyncio.sleep(0)
        return [("many",)]

    async def close(self) -> None:
        await asyncio.sleep(0)
        self.closed = True


class FakePool:
    def __init__(self) -> None:
        self.closed = False
        self.released = 0
        self.connection = FakeConnection()

    async def acquire(self):
        await asyncio.sleep(0)
        return self.connection

    async def release(self, connection) -> None:
        await asyncio.sleep(0)
        self.released += 1

    async def close(self, mode: str) -> None:
        await asyncio.sleep(0)
        self.closed = True


def test_async_manager_direct_lifecycle() -> None:
    db_type = "sqlite"
    created: dict[str, FakeConnection] = {}

    async def builder(_db_type: str, _conn_params: dict, **kwargs):
        await asyncio.sleep(0)
        conn = FakeConnection()
        created["conn"] = conn
        return conn

    async def _run() -> None:
        manager = AsyncDatabaseManager(
            db_type=db_type,
            conn_params=dict(_MIN_PARAMS[db_type]),
            use_pool=False,
            connection_factory=builder,
        )
        rows = await manager.execute_custom_many("SELECT 1")
        assert rows == [("many",)]
        await manager.close()
        assert created["conn"].closed is True

    asyncio.run(_run())


def test_async_manager_pool_lifecycle() -> None:
    db_type = "sqlite"
    created: dict[str, FakePool] = {}

    async def pool_builder(_db_type: str, _conn_params: dict, **kwargs):
        await asyncio.sleep(0)
        pool = FakePool()
        created["pool"] = pool
        return pool

    async def _run() -> None:
        manager = AsyncDatabaseManager(
            db_type=db_type,
            conn_params=dict(_MIN_PARAMS[db_type]),
            use_pool=True,
            pool_factory=pool_builder,
        )
        row = await manager.execute_custom_one("SELECT 1")
        assert row == ("one",)
        assert created["pool"].released == 1
        await manager.close()
        assert created["pool"].closed is True

    asyncio.run(_run())


def test_async_manager_rejects_unsupported_db_type_without_custom_builder() -> None:
    with pytest.raises(Exception) as exc_info:
        AsyncDatabaseManager(db_type="unsupported_db_type", conn_params={}, use_pool=False)

    assert "no soportado" in str(exc_info.value).lower()


class _FailingClosePool:
    """Pool cuyo close() falla con un error real (no timeout)."""

    def __init__(self) -> None:
        self.close_attempted = False

    async def close(self, mode: str) -> None:
        await asyncio.sleep(0)
        self.close_attempted = True
        raise RuntimeError("pool.close() boom")


class _FailingCloseConnection:
    """Conexión cuyo close() falla con un error real."""

    def __init__(self) -> None:
        self.close_attempted = False

    async def close(self) -> None:
        await asyncio.sleep(0)
        self.close_attempted = True
        raise RuntimeError("connection.close() boom")


class TestCloseAsyncResourcesErrorHandling:
    """MGR-01 (AUDIT_CODE 2026-09-22): close_async_resources no tenía try/except por
    recurso (a diferencia de la versión sync); un fallo real de pool.close() se
    propagaba crudo y la conexión directa ni se intentaba cerrar."""

    def test_pool_close_failure_still_raises_database_operation_error(self) -> None:
        pool = _FailingClosePool()

        async def _run() -> None:
            await close_async_resources(
                pool_connection=pool,
                connection=None,
                close_mode="immediate",
                db_type="postgresql",
            )

        with pytest.raises(DatabaseOperationError):
            asyncio.run(_run())

    def test_pool_close_failure_does_not_prevent_connection_close_attempt(self) -> None:
        pool = _FailingClosePool()
        connection = _FailingCloseConnection()

        async def _run() -> None:
            await close_async_resources(
                pool_connection=pool,
                connection=connection,
                close_mode="immediate",
                db_type="postgresql",
            )

        with pytest.raises(DatabaseOperationError) as exc_info:
            asyncio.run(_run())

        assert pool.close_attempted is True
        assert connection.close_attempted is True
        assert "pool.close() boom" in str(exc_info.value)
        assert "connection.close() boom" in str(exc_info.value)

    def test_connection_close_failure_alone_raises_database_operation_error(self) -> None:
        connection = _FailingCloseConnection()

        async def _run() -> None:
            await close_async_resources(
                pool_connection=None,
                connection=connection,
                close_mode="immediate",
                db_type="postgresql",
            )

        with pytest.raises(DatabaseOperationError):
            asyncio.run(_run())

    def test_no_failures_does_not_raise(self) -> None:
        async def _run() -> None:
            await close_async_resources(
                pool_connection=None,
                connection=None,
                close_mode="immediate",
                db_type="postgresql",
            )

        asyncio.run(_run())  # No debe lanzar


def test_async_database_manager_close_propagates_database_operation_error_on_pool_failure() -> None:
    """Extremo a extremo: AsyncDatabaseManager.close() también agrega y relanza."""
    pool = _FailingClosePool()

    async def _run() -> None:
        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params=dict(_MIN_PARAMS["postgresql"]),
            use_pool=True,
        )
        manager.pool_connection = pool
        manager._initialized = True
        await manager.close()

    with pytest.raises(DatabaseOperationError):
        asyncio.run(_run())
