from __future__ import annotations

import asyncio
import inspect
import logging

from unittest.mock import MagicMock

from util_bbdd.metadata.mariadb import MariaDBAsyncAdapter, MariaDBSyncAdapter
from util_bbdd.metadata.postgresql import PostgreSQLAsyncAdapter, PostgreSQLSyncAdapter


class TestSyncAdapterParityStructure:
    def test_postgresql_sync_adapter_has_fetch_tables_method(self) -> None:
        assert hasattr(PostgreSQLSyncAdapter, "fetch_tables_sync")

    def test_postgresql_sync_adapter_has_fetch_columns_method(self) -> None:
        assert hasattr(PostgreSQLSyncAdapter, "fetch_columns_sync")

    def test_postgresql_sync_adapter_has_fetch_pk_method(self) -> None:
        assert hasattr(PostgreSQLSyncAdapter, "fetch_primary_keys_sync")

    def test_postgresql_sync_adapter_has_fetch_fk_method(self) -> None:
        assert hasattr(PostgreSQLSyncAdapter, "fetch_foreign_keys_sync")

    def test_postgresql_sync_adapter_has_fetch_indexes_method(self) -> None:
        assert hasattr(PostgreSQLSyncAdapter, "fetch_indexes_sync")

    def test_postgresql_sync_adapter_has_fetch_routines_method(self) -> None:
        assert hasattr(PostgreSQLSyncAdapter, "fetch_routines_sync")

    def test_postgresql_sync_adapter_has_fetch_routine_parameters_method(self) -> None:
        assert hasattr(PostgreSQLSyncAdapter, "fetch_routine_parameters_sync")

    def test_postgresql_sync_adapter_constructor_takes_manager(self) -> None:
        sig = inspect.signature(PostgreSQLSyncAdapter.__init__)
        assert "manager" in sig.parameters


class TestAsyncAdapterParityStructure:
    def test_postgresql_async_adapter_has_fetch_tables_method(self) -> None:
        assert hasattr(PostgreSQLAsyncAdapter, "fetch_tables_async")

    def test_postgresql_async_adapter_has_fetch_columns_method(self) -> None:
        assert hasattr(PostgreSQLAsyncAdapter, "fetch_columns_async")

    def test_postgresql_async_adapter_has_fetch_pk_method(self) -> None:
        assert hasattr(PostgreSQLAsyncAdapter, "fetch_primary_keys_async")

    def test_postgresql_async_adapter_has_fetch_fk_method(self) -> None:
        assert hasattr(PostgreSQLAsyncAdapter, "fetch_foreign_keys_async")

    def test_postgresql_async_adapter_has_fetch_indexes_method(self) -> None:
        assert hasattr(PostgreSQLAsyncAdapter, "fetch_indexes_async")

    def test_postgresql_async_adapter_has_fetch_routines_method(self) -> None:
        assert hasattr(PostgreSQLAsyncAdapter, "fetch_routines_async")

    def test_postgresql_async_adapter_has_fetch_routine_parameters_method(self) -> None:
        assert hasattr(PostgreSQLAsyncAdapter, "fetch_routine_parameters_async")

    def test_postgresql_async_adapter_has_get_routine_details_method(self) -> None:
        assert hasattr(PostgreSQLAsyncAdapter, "get_routine_details")

    def test_postgresql_async_adapter_constructor_takes_manager(self) -> None:
        sig = inspect.signature(PostgreSQLAsyncAdapter.__init__)
        assert "manager" in sig.parameters


class TestMethodSignaturesParity:
    def test_both_adapters_have_routine_detail_getters(self) -> None:
        assert hasattr(PostgreSQLSyncAdapter, "get_routine_details")
        assert hasattr(PostgreSQLAsyncAdapter, "get_routine_details")
        assert hasattr(MariaDBSyncAdapter, "get_routine_details")
        assert hasattr(MariaDBAsyncAdapter, "get_routine_details")

    def test_both_adapters_have_routine_parameter_getters(self) -> None:
        assert hasattr(PostgreSQLSyncAdapter, "get_routine_parameters_details")
        assert hasattr(PostgreSQLAsyncAdapter, "get_routine_parameters_details")
        assert hasattr(MariaDBSyncAdapter, "get_routine_parameters_details")
        assert hasattr(MariaDBAsyncAdapter, "get_routine_parameters_details")


class TestAdapterInstantiation:
    def test_postgresql_sync_adapter_instantiation(self) -> None:
        class MockManager:
            logger = logging.getLogger(__name__)
            db_cache = MagicMock()

            def _cache_context_key(self, context: str) -> str:
                return f"cache_{context}"

            def _get_query_context_label(self) -> str:
                return "test_query"

            def _get_query_context_database(self) -> str:
                return "test_db"

            def _get_cached_rows(
                self,
                *,
                cache_lookup,
                cache_store,
                fetch_rows,
                cache_hit_message,
                success_message,
                fetch_debug_message=None,
            ):
                return fetch_rows()

            def _execute_metadata_many(self, query_name: str, *, params, error_message: str):
                return []

            def execute_custom_many(self, sql, params=None):
                return []

            def execute_custom_one(self, sql, params=None):
                return None

        manager = MockManager()
        adapter = PostgreSQLSyncAdapter(manager)
        assert adapter is not None
        assert adapter.manager is manager

    def test_postgresql_async_adapter_instantiation(self) -> None:
        class MockAsyncManager:
            logger = logging.getLogger(__name__)
            db_cache = MagicMock()

            def _cache_context_key(self, context: str) -> str:
                return f"cache_{context}"

            def _get_query_context_label(self) -> str:
                return "test_query"

            def _get_query_context_database(self) -> str:
                return "test_db"

            async def _get_cached_rows_async(
                self,
                *,
                cache_lookup,
                cache_store,
                fetch_rows,
                cache_hit_message: str | None,
                success_message: str | None,
                fetch_debug_message: str | None = None,
            ) -> list:
                await asyncio.sleep(0)
                result = fetch_rows() if callable(fetch_rows) else []
                return result if isinstance(result, list) else []

            async def _execute_metadata_many(self, query_name: str, *, params, error_message: str):
                await asyncio.sleep(0)
                return []

            async def execute_custom_many(self, sql, params=None):
                return []

            async def execute_custom_one(self, sql, params=None):
                await asyncio.sleep(0)
                return None

        manager = MockAsyncManager()
        adapter = PostgreSQLAsyncAdapter(manager)
        assert adapter is not None
        assert adapter.manager is manager

    def test_mariadb_sync_adapter_instantiation(self) -> None:
        class MockManager:
            logger = logging.getLogger(__name__)
            db_cache = MagicMock()

            def _cache_context_key(self, context: str) -> str:
                return f"cache_{context}"

            def _get_query_context_label(self) -> str:
                return "test_query"

            def _get_query_context_database(self) -> str:
                return "test_db"

            def _get_cached_rows(
                self,
                *,
                cache_lookup,
                cache_store,
                fetch_rows,
                cache_hit_message,
                success_message,
                fetch_debug_message=None,
            ):
                return fetch_rows()

            def _execute_metadata_many(self, query_name: str, *, params, error_message: str):
                return []

            def execute_custom_many(self, sql, params=None):
                return []

            def execute_custom_one(self, sql):
                return None

            def get_tables(self):
                return []

            def get_columns(self, tabla: str):
                return []

            def get_primary_keys(self, tabla: str):
                return []

            def get_foreign_keys(self, tabla: str):
                return []

            def get_indices(self, tabla: str):
                return []

            def execute_query_many(self, query_name: str, **kwargs):
                return []

        manager = MockManager()
        adapter = MariaDBSyncAdapter(manager)
        assert adapter is not None


class TestDuckTypingCompatibility:
    def test_postgresql_sync_adapter_implements_source_adapter_protocol(self) -> None:
        for m in [
            "fetch_tables_sync",
            "fetch_columns_sync",
            "fetch_primary_keys_sync",
            "fetch_foreign_keys_sync",
            "fetch_indexes_sync",
        ]:
            assert hasattr(PostgreSQLSyncAdapter, m)
