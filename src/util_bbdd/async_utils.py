"""Utilidades async compartidas."""

from __future__ import annotations

import inspect

from collections.abc import Awaitable
from typing import TypeVar, overload

T = TypeVar("T")


@overload
async def maybe_await(value: Awaitable[T]) -> T: ...


@overload
async def maybe_await(value: T) -> T: ...


async def maybe_await(value: T | Awaitable[T]) -> T:
    """Resuelve valores awaitables o directos con una única API."""
    if inspect.isawaitable(value):
        return await value
    return value
