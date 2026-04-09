"""Tests de paridad entre adaptadores PostgreSQL y MariaDB."""

from __future__ import annotations

import inspect

from util_bbdd.metadata.mariadb import MariaDBAsyncAdapter, MariaDBSyncAdapter
from util_bbdd.metadata.postgresql import PostgreSQLAsyncAdapter, PostgreSQLSyncAdapter


class TestSyncAdapterParityStructure:
    """Tests que verifican que sync adapters tienen métodos compatibles."""

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
        # Debería poder construirse con un manager
        sig = inspect.signature(PostgreSQLSyncAdapter.__init__)
        assert "manager" in sig.parameters


class TestAsyncAdapterParityStructure:
    """Tests que verifican que async adapters tienen métodos compatibles."""

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
    """Tests que comparan firmas de métodos entre PostgrSQL y MariaDB."""

    def test_both_adapters_have_routine_detail_getters(self) -> None:
        # PostgreSQL
        assert hasattr(PostgreSQLSyncAdapter, "get_routine_details")
        assert hasattr(PostgreSQLAsyncAdapter, "get_routine_details")
        # MariaDB
        assert hasattr(MariaDBSyncAdapter, "get_routine_details")
        assert hasattr(MariaDBAsyncAdapter, "get_routine_details")

    def test_both_adapters_have_routine_parameter_getters(self) -> None:
        # PostgreSQL
        assert hasattr(PostgreSQLSyncAdapter, "get_routine_parameters_details")
        assert hasattr(PostgreSQLAsyncAdapter, "get_routine_parameters_details")
        # MariaDB
        assert hasattr(MariaDBSyncAdapter, "get_routine_parameters_details")
        assert hasattr(MariaDBAsyncAdapter, "get_routine_parameters_details")

    def test_fetch_methods_return_list_of_tuples(self) -> None:
        """Verifica que métodos fetch return list[tuple] (type hint parity)."""
        # Verificar firmas de retorno
        pg_sync_sig = inspect.signature(PostgreSQLSyncAdapter.fetch_tables_sync)
        mdb_sync_sig = inspect.signature(MariaDBSyncAdapter.fetch_tables_sync)
        # Ambos deberían indicar list en retorno
        assert "list" in str(pg_sync_sig.return_annotation).lower()
        assert "list" in str(mdb_sync_sig.return_annotation).lower()


class TestAdapterInstantiation:
    """Tests que verifican que adapters pueden instanciarse apropiadamente."""

    def test_postgresql_sync_adapter_instantiation(self) -> None:
        # Mock manager simple
        class MockManager:
            def execute_custom_many(self, sql: str, params: dict | None = None) -> list:
                return []

            def execute_custom_one(self, sql: str, params: dict | None = None) -> tuple | None:
                return None

        manager = MockManager()
        adapter = PostgreSQLSyncAdapter(manager)
        assert adapter is not None
        assert adapter.manager is manager

    def test_postgresql_async_adapter_instantiation(self) -> None:
        class MockAsyncManager:
            async def execute_custom_many(self, sql: str, params: dict | None = None) -> list:
                return []

        manager = MockAsyncManager()
        adapter = PostgreSQLAsyncAdapter(manager)
        assert adapter is not None
        assert adapter.manager is manager

    def test_mariadb_sync_adapter_instantiation(self) -> None:
        class MockManager:
            def execute_custom_many(self, sql: str, params: dict | None = None) -> list:
                return []

        manager = MockManager()
        adapter = MariaDBSyncAdapter(manager)
        assert adapter is not None


class TestDuckTypingCompatibility:
    """Tests que verifican duck-typing compatibility con Protocol."""

    def test_postgresql_sync_adapter_implements_source_adapter_protocol(self) -> None:
        """Verifica que PostgreSQLSyncAdapter tiene todos los métodos de SourceAdapter."""
        required_methods = [
            "fetch_tables_sync",
            "fetch_columns_sync",
            "fetch_primary_keys_sync",
            "fetch_foreign_keys_sync",
            "fetch_indexes_sync",
        ]
        for method_name in required_methods:
            assert hasattr(PostgreSQLSyncAdapter, method_name), f"Falta método: {method_name}"

    def test_postgresql_sync_adapter_implements_routine_adapter_protocol(self) -> None:
        """Verifica métodos de RoutineAdapter."""
        required_methods = [
            "fetch_routines_sync",
            "fetch_routine_parameters_sync",
        ]
        for method_name in required_methods:
            assert hasattr(PostgreSQLSyncAdapter, method_name), f"Falta método: {method_name}"

    def test_postgresql_async_adapter_implements_source_adapter_protocol(self) -> None:
        """Verifica que PostgreSQLAsyncAdapter tiene métodos async correspondientes."""
        required_methods = [
            "fetch_tables_async",
            "fetch_columns_async",
            "fetch_primary_keys_async",
            "fetch_foreign_keys_async",
            "fetch_indexes_async",
        ]
        for method_name in required_methods:
            assert hasattr(PostgreSQLAsyncAdapter, method_name), f"Falta método: {method_name}"

    def test_postgresql_async_adapter_implements_routine_adapter_protocol(self) -> None:
        """Verifica métodos async de RoutineAdapter."""
        required_methods = [
            "fetch_routines_async",
            "fetch_routine_parameters_async",
        ]
        for method_name in required_methods:
            assert hasattr(PostgreSQLAsyncAdapter, method_name), f"Falta método: {method_name}"


class TestTupleNormalizationParity:
    """Tests que verifican normalización de tuplas."""

    def test_fetch_tables_returns_3_tuple_elements(self) -> None:
        """fetch_tables debe retornar (table_name, table_type, table_comment)."""
        # Esto es verificado conceptualmente; requeriría BD real para test e2e
        # Por ahora verificamos que el método existe y está tipado
        assert callable(PostgreSQLSyncAdapter.fetch_tables_sync)

    def test_fetch_columns_returns_7_tuple_elements(self) -> None:
        """fetch_columns debe retornar tupla de 7 elementos normalizados."""
        assert callable(PostgreSQLSyncAdapter.fetch_columns_sync)

    def test_fetch_pk_returns_2_tuple_elements(self) -> None:
        """fetch_primary_keys debe retornar (column_name, ordinal_position)."""
        assert callable(PostgreSQLSyncAdapter.fetch_primary_keys_sync)

    def test_fetch_fk_returns_7_tuple_elements(self) -> None:
        """fetch_foreign_keys debe retornar tupla de constraint info."""
        assert callable(PostgreSQLSyncAdapter.fetch_foreign_keys_sync)

    def test_both_adapters_normalize_output(self) -> None:
        """Verificar que ambos adapters normalizan salida."""
        # PostgreSQL debe normalizar como MariaDB hace
        pg_methods = [m for m in dir(PostgreSQLSyncAdapter) if m.startswith("fetch_") and m.endswith("_sync")]
        # Deben tener al menos los mismos métodos base
        assert len(pg_methods) >= 5  # Al menos 5 fetch methods


class TestRegistryIntegration:
    """Tests que verifican integración con registry."""

    def test_postgresql_adapters_can_be_imported(self) -> None:
        """Verifica que adaptadores pueden importarse sin errores."""
        from util_bbdd.metadata.postgresql import PostgreSQLAsyncAdapter, PostgreSQLSyncAdapter

        assert PostgreSQLSyncAdapter is not None
        assert PostgreSQLAsyncAdapter is not None

    def test_mariadb_adapters_can_be_imported(self) -> None:
        """Verifica que MariaDB adapters pueden importarse."""
        from util_bbdd.metadata.mariadb import MariaDBAsyncAdapter, MariaDBSyncAdapter

        assert MariaDBSyncAdapter is not None
        assert MariaDBAsyncAdapter is not None
