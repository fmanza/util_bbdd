"""Tests de integración MDC-01: MetadataManager/AsyncMetadataManager conectados a producción.

A diferencia del resto de la suite (que mockea el executor), estos tests ejecutan contra
`sqlite3`/`aiosqlite` reales vía `SyncDatabaseManager.get_metadata_manager()` /
`AsyncDatabaseManager.get_metadata_manager()`, para probar que el subsistema
Builder+Cache+Normalizer queda realmente conectado a la ruta de producción (antes,
`DDLBuilder`/`MetadataManager` no tenían ningún consumidor real, ver
`.ai/sessions/2026-09-22-audit-completo-remediacion/02_PLAN_p1_p2.md` Fase 2).
"""

from __future__ import annotations

import asyncio

import pytest

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.metadata import AsyncMetadataManager, MetadataManager


@pytest.fixture
def sync_manager():
    manager = SyncDatabaseManager(
        db_type="sqlite",
        conn_params={"database": ":memory:"},
        use_pool=False,
    )
    manager.execute_custom_many('CREATE TABLE "users" (id INTEGER PRIMARY KEY, name TEXT NOT NULL)')
    try:
        yield manager
    finally:
        manager.close()


class TestSyncMetadataManagerWiring:
    def test_get_metadata_manager_returns_metadata_manager(self, sync_manager) -> None:
        mm = sync_manager.get_metadata_manager()

        assert isinstance(mm, MetadataManager)

    def test_get_metadata_manager_is_cached_singleton(self, sync_manager) -> None:
        first = sync_manager.get_metadata_manager()
        second = sync_manager.get_metadata_manager()

        assert first is second

    def test_get_metadata_manager_shares_db_cache_with_manager(self, sync_manager) -> None:
        mm = sync_manager.get_metadata_manager()

        assert mm.db_cache is sync_manager.db_cache
        assert mm.relationship_cache is sync_manager.relationship_cache

    def test_get_tables_hits_real_connection(self, sync_manager) -> None:
        mm = sync_manager.get_metadata_manager()

        tables = mm.get_tables()

        assert any(row[0] == "users" for row in tables)

    def test_get_columns_hits_real_connection(self, sync_manager) -> None:
        mm = sync_manager.get_metadata_manager()

        columns = mm.get_columns("users")
        col_names = [row[0] for row in columns]

        assert "id" in col_names
        assert "name" in col_names

    def test_get_ddl_builds_valid_create_table_from_real_metadata(self, sync_manager) -> None:
        mm = sync_manager.get_metadata_manager()

        ddl = mm.get_ddl("users")

        assert ddl.startswith("CREATE TABLE")
        assert "id" in ddl
        assert "name" in ddl

    def test_get_ddl_roundtrips_against_real_connection(self, sync_manager) -> None:
        """El DDL construido por DDLBuilder debe ser ejecutable de verdad (no solo bien formado)."""
        mm = sync_manager.get_metadata_manager()
        ddl = mm.get_ddl("users").replace("`users`", "`users_copy`", 1)

        sync_manager.execute_custom_many(ddl)

        tables = mm.get_tables(use_cache=False)
        assert any(row[0] == "users_copy" for row in tables)


class TestAsyncMetadataManagerWiring:
    def test_get_metadata_manager_returns_async_metadata_manager(self) -> None:
        async def _run() -> None:
            async with AsyncDatabaseManager(
                db_type="sqlite",
                conn_params={"database": ":memory:"},
                use_pool=False,
            ) as manager:
                await manager.execute_custom_many('CREATE TABLE "products" (id INTEGER PRIMARY KEY, sku TEXT NOT NULL)')

                amm = manager.get_metadata_manager()
                assert isinstance(amm, AsyncMetadataManager)

                second = manager.get_metadata_manager()
                assert amm is second

                tables = await amm.get_tables()
                assert any(row[0] == "products" for row in tables)

                columns = await amm.get_columns("products")
                col_names = [row[0] for row in columns]
                assert "id" in col_names
                assert "sku" in col_names

                ddl = await amm.get_ddl("products")
                assert ddl.startswith("CREATE TABLE")
                assert "sku" in ddl

                assert amm.db_cache is manager.db_cache

        asyncio.run(_run())
