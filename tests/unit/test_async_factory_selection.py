"""Tests para selección async en factorías."""

from __future__ import annotations

import asyncio

import pytest

from util_bbdd.connection.factory import ConnectionFactory
from util_bbdd.factory.pool_factory import PoolFactory


class FakeConnection:
    def __init__(self, payload):
        self.payload = payload


class FakePool:
    def __init__(self, payload):
        self.payload = payload


def test_connect_factory_selects_registered_async_builder() -> None:
    db_type = "test_async_connection_factory"

    async def builder(conn_params, **kwargs):
        await asyncio.sleep(0)
        return FakeConnection({"conn_params": conn_params, "kwargs": kwargs})

    ConnectionFactory.register_async_connection(db_type, builder)

    async def _run() -> None:
        conn = await ConnectionFactory.create_async_connection(db_type, {"k": "v"}, foo="bar")
        assert isinstance(conn, FakeConnection)
        assert conn.payload["conn_params"] == {"k": "v"}
        assert conn.payload["kwargs"]["foo"] == "bar"

    asyncio.run(_run())


def test_pool_factory_selects_registered_async_builder() -> None:
    db_type = "test_async_pool_factory"

    async def builder(conn_params, **kwargs):
        await asyncio.sleep(0)
        return FakePool({"conn_params": conn_params, "kwargs": kwargs})

    PoolFactory.register_async_pool(db_type, builder)

    async def _run() -> None:
        pool = await PoolFactory.create_async_pool(db_type, {"pool_size": 3}, timeout=10)
        assert isinstance(pool, FakePool)
        assert pool.payload["conn_params"] == {"pool_size": 3}
        assert pool.payload["kwargs"]["timeout"] == 10

    asyncio.run(_run())


def test_connect_factory_hsqldb_async_is_explicitly_not_supported() -> None:
    async def _run() -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            await ConnectionFactory.create_async_connection("hsqldb", {})
        err_msg = str(exc_info.value).lower()
        assert "hsqldb" in err_msg
        assert "no soportada" in err_msg

    asyncio.run(_run())


def test_pool_factory_hsqldb_async_is_explicitly_not_supported() -> None:
    async def _run() -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            await PoolFactory.create_async_pool("hsqldb", {})
        err_msg = str(exc_info.value).lower()
        assert "hsqldb" in err_msg
        assert "no soportado" in err_msg

    asyncio.run(_run())
