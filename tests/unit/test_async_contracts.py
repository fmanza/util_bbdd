"""Tests de contratos async base."""

from __future__ import annotations

import asyncio

import pytest

from util_bbdd import maybe_await
from util_bbdd.connection.factory import ConnectionFactory
from util_bbdd.connection.protocols import AsyncConnectionProtocol, AsyncPoolProtocol


class DummyAsyncConnection:
    async def execute(self, query: str, params=None):
        await asyncio.sleep(0)
        return None

    async def fetchone(self):
        await asyncio.sleep(0)
        return (1,)

    async def fetchall(self):
        await asyncio.sleep(0)
        return [(1,)]

    async def close(self) -> None:
        await asyncio.sleep(0)
        self.closed = True


class DummyAsyncPool:
    async def acquire(self):
        await asyncio.sleep(0)
        return DummyAsyncConnection()

    async def release(self, connection) -> None:
        await asyncio.sleep(0)
        self.last_released = connection

    async def close(self, mode: str) -> None:
        await asyncio.sleep(0)
        self.close_mode = mode


def test_runtime_protocol_checks() -> None:
    assert isinstance(DummyAsyncConnection(), AsyncConnectionProtocol)
    assert isinstance(DummyAsyncPool(), AsyncPoolProtocol)


def test_async_factory_without_registration_raises() -> None:
    unique_db_type = "missing_async_engine"

    async def _run() -> None:
        with pytest.raises(NotImplementedError):
            await ConnectionFactory.create_async_connection(unique_db_type, {})

    asyncio.run(_run())


def test_maybe_await_resolves_plain_value() -> None:
    async def _run() -> int:
        return await maybe_await(7)

    assert asyncio.run(_run()) == 7


def test_maybe_await_resolves_awaitable() -> None:
    async def _value() -> str:
        await asyncio.sleep(0)
        return "ok"

    async def _run() -> str:
        return await maybe_await(_value())

    assert asyncio.run(_run()) == "ok"
