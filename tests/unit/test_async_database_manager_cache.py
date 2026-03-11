"""Tests explícitos de caché para AsyncDatabaseManager (PR-A5)."""

from unittest.mock import AsyncMock

import pytest

from util_bbdd.managers import AsyncDatabaseManager
from util_bbdd.metadata import DatabaseMetadataCache, RelationshipMetadataCache


class TestAsyncDatabaseManagerCache:
    """Contrato de caché async: hit, invalidación y composición."""

    @pytest.mark.asyncio
    async def test_second_call_uses_cache_without_reexecuting_query(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query_many = AsyncMock(return_value=[("users",)])

        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"schema": "public"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        first = await manager.get_tables()
        second = await manager.get_tables()

        assert first == [("users",)]
        assert second == [("users",)]
        mock_executor.execute_query_many.assert_called_once_with(
            query_name="obtener_tablas",
            db_type="postgresql",
            params={"database": "public"},
        )

    @pytest.mark.asyncio
    async def test_clear_cache_global_invalidates_and_forces_refetch(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query_many = AsyncMock(side_effect=[[("users",)], [("orders",)]])

        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"schema": "public"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        first = await manager.get_tables()
        second = await manager.get_tables()
        manager.relationship_cache._is_pk_cache[("users", "id")] = True
        manager.clear_cache()
        third = await manager.get_tables()

        assert first == [("users",)]
        assert second == [("users",)]
        assert third == [("orders",)]
        assert mock_executor.execute_query_many.call_count == 2
        assert manager.relationship_cache.get_cache_stats()["total_entries"] == 0

    def test_clear_cache_selective_table_invalidates_only_target_table(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        manager.db_cache._columns_cache[("db", "users")] = [("id", "int")]
        manager.db_cache._columns_cache[("db", "orders")] = [("id", "int")]
        manager.relationship_cache._is_pk_cache[("users", "id")] = True
        manager.relationship_cache._is_pk_cache[("orders", "id")] = True

        manager.clear_cache(context_database="db", table="users")

        assert ("db", "users") not in manager.db_cache._columns_cache
        assert ("db", "orders") in manager.db_cache._columns_cache
        assert ("users", "id") not in manager.relationship_cache._is_pk_cache
        assert ("orders", "id") in manager.relationship_cache._is_pk_cache

    def test_relationship_cache_composition_uses_manager_db_cache(self):
        manager = AsyncDatabaseManager(
            db_type="sqlite",
            conn_params={"database": ":memory:"},
            use_pool=False,
        )

        assert isinstance(manager.db_cache, DatabaseMetadataCache)
        assert isinstance(manager.relationship_cache, RelationshipMetadataCache)
        assert manager.relationship_cache.db_cache is manager.db_cache
