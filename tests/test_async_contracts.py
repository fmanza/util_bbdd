"""Tests de contratos async base."""

from __future__ import annotations

import asyncio

import pytest

from util_bbdd.connection.async_protocols import AsyncConnectionProtocol, AsyncPoolProtocol
from util_bbdd.connection.connect_factory import ConnectFactory


class DummyAsyncConnection:
    async def execute(self, query: str, params=None):
        return None

    async def fetchone(self):
        return (1,)

    async def fetchall(self):
        return [(1,)]

    async def close(self) -> None:
        return None


class DummyAsyncPool:
    async def acquire(self):
        return DummyAsyncConnection()

    async def release(self, connection) -> None:
        return None

    async def aclose(self) -> None:
        return None


def test_runtime_protocol_checks() -> None:
    assert isinstance(DummyAsyncConnection(), AsyncConnectionProtocol)
    assert isinstance(DummyAsyncPool(), AsyncPoolProtocol)


def test_async_factory_without_registration_raises() -> None:
    unique_db_type = "missing_async_engine"

    async def _run() -> None:
        with pytest.raises(NotImplementedError):
            await ConnectFactory.create_async_connection(unique_db_type, {})

    asyncio.run(_run())
