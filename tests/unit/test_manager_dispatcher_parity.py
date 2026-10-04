"""Paridad estructural mínima entre helpers sync y async de managers."""

from __future__ import annotations

from util_bbdd.managers.async_mgr import AsyncDatabaseManager
from util_bbdd.managers.sync_mgr import SyncDatabaseManager

_SHARED_CORE_HELPERS = [
    "_get_query_context_database",
    "_get_query_context_label",
    "_clear_all_caches",
    "_clear_table_cache",
    "_clear_routine_cache",
    "_clear_context_cache",
    "_cache_context_key",
    "_execute_metadata_many",
    "_get_query_executor",
]

# Lecturas de metadatos (E2 de ADR-003): la misma fachada sobre el snapshot en ambos managers
_CATALOG_READS = [
    "get_schema_metadata",
    "get_tables",
    "get_columns",
    "get_ddl",
    "get_columns_charset_collation",
    "get_storage_rows",
    "get_storage_inventory",
]


def test_sync_and_async_managers_expose_same_core_helper_surface() -> None:
    for helper_name in _SHARED_CORE_HELPERS:
        assert hasattr(SyncDatabaseManager, helper_name)
        assert hasattr(AsyncDatabaseManager, helper_name)


def test_sync_and_async_managers_expose_same_catalog_reads() -> None:
    for name in _CATALOG_READS:
        assert hasattr(SyncDatabaseManager, name)
        assert hasattr(AsyncDatabaseManager, name)
