"""Tests de regresión para fetch_routine_definition_sync/async en PostgreSQL [MPG-01].

Antes de este fix, PostgreSQLSyncAdapter/PostgreSQLAsyncAdapter estaban
registrados como RoutineAdapter pero no implementaban fetch_routine_definition_*,
pese a que el helper `process_routine_result()` que construiría el DDL ya existía
sin invocarse.
"""

from __future__ import annotations

import asyncio
import logging

from unittest.mock import MagicMock

from util_bbdd.metadata.postgresql.async_adapter import PostgreSQLAsyncAdapter
from util_bbdd.metadata.postgresql.sync_adapter import PostgreSQLSyncAdapter

_ROUTINE_ROW = (
    "calculate_total",
    "FUNCTION",
    "app_user",
    "BEGIN\n  RETURN price * quantity;\nEND;",
    "numeric",
    False,  # is_aggregate
    False,  # is_window
    False,  # security_definer
)


class _MockSyncManager:
    logger = logging.getLogger(__name__)
    db_cache = MagicMock()

    def _get_cached_rows(self, *, cache_lookup, cache_store, fetch_rows, **_kwargs):
        return fetch_rows()

    def execute_custom_many(self, sql, params=None):
        return [_ROUTINE_ROW]


class _MockAsyncManager:
    logger = logging.getLogger(__name__)
    db_cache = MagicMock()

    async def _get_cached_rows_async(self, *, cache_lookup, cache_store, fetch_rows, **_kwargs):
        await asyncio.sleep(0)
        return await fetch_rows()

    async def execute_custom_many(self, sql, params=None):
        await asyncio.sleep(0)
        return [_ROUTINE_ROW]


def test_postgresql_sync_adapter_exposes_fetch_routine_definition_sync() -> None:
    assert hasattr(PostgreSQLSyncAdapter, "fetch_routine_definition_sync")


def test_postgresql_async_adapter_exposes_fetch_routine_definition_async() -> None:
    assert hasattr(PostgreSQLAsyncAdapter, "fetch_routine_definition_async")


def test_fetch_routine_definition_sync_builds_ddl_from_definition() -> None:
    adapter = PostgreSQLSyncAdapter(_MockSyncManager())

    ddl = adapter.fetch_routine_definition_sync("public", "calculate_total", "FUNCTION")

    assert "RETURN price * quantity" in ddl
    assert "Schema: public" in ddl


def test_fetch_routine_definition_sync_unknown_routine_returns_fallback_comment() -> None:
    adapter = PostgreSQLSyncAdapter(_MockSyncManager())

    ddl = adapter.fetch_routine_definition_sync("public", "does_not_exist", "FUNCTION")

    assert "unavailable" in ddl.lower()


def test_fetch_routine_definition_async_builds_ddl_from_definition() -> None:
    adapter = PostgreSQLAsyncAdapter(_MockAsyncManager())

    ddl = asyncio.run(adapter.fetch_routine_definition_async("public", "calculate_total", "FUNCTION"))

    assert "RETURN price * quantity" in ddl
    assert "Schema: public" in ddl


def test_fetch_routine_definition_async_unknown_routine_returns_fallback_comment() -> None:
    adapter = PostgreSQLAsyncAdapter(_MockAsyncManager())

    ddl = asyncio.run(adapter.fetch_routine_definition_async("public", "does_not_exist", "FUNCTION"))

    assert "unavailable" in ddl.lower()
