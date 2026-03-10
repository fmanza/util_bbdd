"""Tests unitarios para normalización de metadatos y helper async."""

from __future__ import annotations

import pytest

from util_bbdd.async_utils import maybe_await
from util_bbdd.metadata_normalization import normalize_column_rows, normalize_table_rows


def test_normalize_table_rows_extracts_name_and_raw() -> None:
    rows = [("users", "BASE TABLE"), ("orders", "BASE TABLE")]

    result = normalize_table_rows(rows)

    assert result == [
        {"name": "users", "raw": ("users", "BASE TABLE")},
        {"name": "orders", "raw": ("orders", "BASE TABLE")},
    ]


def test_normalize_column_rows_prefers_second_position_for_name() -> None:
    rows = [
        (0, "id", "INTEGER", 1, None, 1),
        (1, "name", "TEXT", 0, None, 0),
    ]

    result = normalize_column_rows(rows)

    assert result == [
        {"name": "id", "data_type": "INTEGER", "raw": (0, "id", "INTEGER", 1, None, 1)},
        {"name": "name", "data_type": "TEXT", "raw": (1, "name", "TEXT", 0, None, 0)},
    ]


@pytest.mark.asyncio
async def test_maybe_await_with_direct_value() -> None:
    result = await maybe_await(123)
    assert result == 123


@pytest.mark.asyncio
async def test_maybe_await_with_awaitable_value() -> None:
    async def _build_value() -> str:
        return "ok"

    result = await maybe_await(_build_value())
    assert result == "ok"
