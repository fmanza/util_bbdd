"""Tests para selección async en factorías."""

from __future__ import annotations

import asyncio

from util_bbdd.connection.connect_factory import ConnectFactory
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
        return FakeConnection({"conn_params": conn_params, "kwargs": kwargs})

    ConnectFactory.register_async_connection(db_type, builder)

    async def _run() -> None:
        conn = await ConnectFactory.create_async_connection(db_type, {"k": "v"}, foo="bar")
        assert isinstance(conn, FakeConnection)
        assert conn.payload["conn_params"] == {"k": "v"}
        assert conn.payload["kwargs"]["foo"] == "bar"

    asyncio.run(_run())


def test_pool_factory_selects_registered_async_builder() -> None:
    db_type = "test_async_pool_factory"

    async def builder(conn_params, **kwargs):
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
        try:
            await ConnectFactory.create_async_connection("hsqldb", {})
            assert False, "Se esperaba NotImplementedError para hsqldb async"
        except NotImplementedError as err:
            assert "hsqldb" in str(err).lower()
            assert "no soportada" in str(err).lower()

    asyncio.run(_run())


def test_pool_factory_hsqldb_async_is_explicitly_not_supported() -> None:
    async def _run() -> None:
        try:
            await PoolFactory.create_async_pool("hsqldb", {})
            assert False, "Se esperaba NotImplementedError para hsqldb async"
        except NotImplementedError as err:
            assert "hsqldb" in str(err).lower()
            assert "no soportado" in str(err).lower()

    asyncio.run(_run())
