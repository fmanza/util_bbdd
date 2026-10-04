"""Tests unitarios para normalización de metadatos y helper async."""

from __future__ import annotations

import asyncio

import pytest

from util_bbdd.async_utils import maybe_await


@pytest.mark.asyncio
async def test_maybe_await_with_direct_value() -> None:
    result = await maybe_await(123)
    assert result == 123


@pytest.mark.asyncio
async def test_maybe_await_with_awaitable_value() -> None:
    async def _build_value() -> str:
        await asyncio.sleep(0)
        return "ok"

    result = await maybe_await(_build_value())
    assert result == "ok"
