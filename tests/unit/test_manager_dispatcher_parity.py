"""Paridad estructural mínima entre helpers sync y async de managers."""

from __future__ import annotations

from util_bbdd.managers.async_mgr import AsyncDatabaseManager
from util_bbdd.managers.sync_mgr import SyncDatabaseManager

_SHARED_MANAGER_HELPERS = [
    "_get_mariadb_adapter",
    "_fetch_mariadb_routines_from_show_status",
    "_get_mariadb_routines_detail_rows",
    "_get_mariadb_routine_parameters_detail_rows",
    "_fetch_mariadb_columns_safe",
    "_fetch_mariadb_view_from_information_schema",
    "_fetch_mariadb_routine_from_information_schema",
    "_fetch_mariadb_routine_parameters_detailed",
    "_fetch_mariadb_routine_parameters_public_rows",
    "_build_mariadb_ddl_from_metadata",
    "_fetch_mariadb_routines",
    "_get_routines_fetcher",
    "_get_table_ddl_fetcher",
    "_get_view_ddl_fetcher",
    "_get_columns_fetcher",
    "_get_routine_parameters_fetcher",
    "_get_routine_ddl_fetcher",
    "_get_storage_inventory_handler",
]

_SHARED_CORE_HELPERS = [
    "_get_query_context_database",
    "_add_metadata_context_params",
    "_get_query_context_label",
    "_clear_all_caches",
    "_clear_table_cache",
    "_clear_routine_cache",
    "_clear_tuple_cache_by_context",
    "_clear_context_cache",
    "_cache_context_key",
    "_cache_table_key",
    "_cache_routine_key",
    "_execute_metadata_many",
    "_execute_metadata_one",
]


def _ordered_helpers(manager_type: type[object]) -> list[str]:
    return [name for name in manager_type.__dict__ if name in _SHARED_MANAGER_HELPERS]


def test_sync_and_async_managers_keep_shared_helper_names_in_same_order() -> None:
    sync_names = _ordered_helpers(SyncDatabaseManager)
    async_names = _ordered_helpers(AsyncDatabaseManager)

    assert sync_names == _SHARED_MANAGER_HELPERS
    assert async_names == _SHARED_MANAGER_HELPERS


def test_sync_and_async_managers_expose_same_core_helper_surface() -> None:
    for helper_name in _SHARED_CORE_HELPERS:
        assert hasattr(SyncDatabaseManager, helper_name)
        assert hasattr(AsyncDatabaseManager, helper_name)


def test_sync_exposes_explicit_aliases_for_async_only_helper_patterns() -> None:
    assert hasattr(SyncDatabaseManager, "_get_query_executor")
    assert hasattr(SyncDatabaseManager, "_get_cached_rows_sync")
    assert hasattr(SyncDatabaseManager, "_get_cached_text_sync")
    assert hasattr(AsyncDatabaseManager, "_get_query_executor")
    assert hasattr(AsyncDatabaseManager, "_get_cached_rows_async")
    assert hasattr(AsyncDatabaseManager, "_get_cached_text_async")
