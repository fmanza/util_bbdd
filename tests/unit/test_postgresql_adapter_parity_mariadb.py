from __future__ import annotations
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

    def test_fetch_methods_return_list_of_tuples(self) -> None:
        pg_sync_sig = inspect.signature(PostgreSQLSyncAdapter.fetch_tables_sync)
        mdb_sync_sig = inspect.signature(MariaDBSyncAdapter.fetch_tables_sync)
        assert "list" in str(pg_sync_sig.return_annotation).lower()
        assert "list" in str(mdb_sync_sig.return_annotation).lower()


class TestAdapterInstantiation:
    def test_postgresql_sync_adapter_instantiation(self) -> None:
        class MockManager:
            logger = logging.getLogger(__name__)
            db_cache = MagicMock()

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

            async def execute_custom_many(self, sql, params=None):
                return []

        manager = MockAsyncManager()
        adapter = PostgreSQLAsyncAdapter(manager)
        assert adapter is not None
        assert adapter.manager is manager

    def test_mariadb_sync_adapter_instantiation(self) -> None:
        class MockManager:
            logger = logging.getLogger(__name__)
            db_cache = MagicMock()

            def execute_custom_many(self, sql, params=None):
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
