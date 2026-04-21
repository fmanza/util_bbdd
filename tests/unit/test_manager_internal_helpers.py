"""Tests focalizados para helpers internos de managers."""

from __future__ import annotations

import asyncio

from unittest.mock import MagicMock

import pytest

from util_bbdd import DatabaseOperationError
from util_bbdd.managers._manager_lifecycle import (
    SyncConnectionLifecycleManager,
    init_async_resources,
)
from util_bbdd.managers._manager_metadata_runtime import (
    MetadataFetchRequest,
    get_metadata_fetch_strategy,
)
from util_bbdd.managers._manager_storage import (
    get_async_storage_inventory_strategy,
    get_sync_storage_inventory_strategy,
)
from util_bbdd.managers._metadata_cache import CacheManager
from util_bbdd.managers._metadata_context import CacheKeyFactory, MetadataContextResolver
from util_bbdd.managers._metadata_parser import CharsetCollationParser, DDLNormalizer
from util_bbdd.managers._metadata_request import MetadataRequestBuilder
from util_bbdd.metadata import DatabaseMetadataCache
from util_bbdd.metadata.cache import RelationshipMetadataCache


def test_get_query_context_database_uses_schema_defaults() -> None:
    assert (
        MetadataContextResolver.get_context_database(
            db_type="postgresql", database="demo", conn_params={"schema": "analytics"}
        )
        == "analytics"
    )
    assert (
        MetadataContextResolver.get_context_database(db_type="oracle", database="XE", conn_params={"user": "SCOTT"})
        == "SCOTT"
    )
    assert MetadataContextResolver.get_context_database(db_type="sqlserver", database="", conn_params={}) == "dbo"


def test_clear_context_cache_removes_only_matching_entries() -> None:
    db_cache = DatabaseMetadataCache()
    db_cache._tables_cache["public"] = [("users",)]
    db_cache._tables_cache["audit"] = [("events",)]
    db_cache._columns_cache[("public", "users")] = [("id",)]
    db_cache._columns_cache[("audit", "events")] = [("id",)]
    routine_key_a = CacheKeyFactory.routine_key("public", "proc_a", "procedure")
    routine_key_b = CacheKeyFactory.routine_key("audit", "proc_b", "procedure")
    db_cache._routine_ddl_cache[routine_key_a] = "DDL"
    db_cache._routine_ddl_cache[routine_key_b] = "DDL"

    CacheManager(
        db_cache=db_cache,
        relationship_cache=RelationshipMetadataCache(),
        logger=MagicMock(),
    ).clear_context(context="public")

    assert "public" not in db_cache._tables_cache
    assert "audit" in db_cache._tables_cache
    assert ("public", "users") not in db_cache._columns_cache
    assert ("audit", "events") in db_cache._columns_cache
    assert routine_key_a not in db_cache._routine_ddl_cache
    assert routine_key_b in db_cache._routine_ddl_cache


@pytest.mark.asyncio
async def test_init_async_resources_falls_back_to_direct_connection() -> None:
    async def _unsupported_pool() -> None:
        raise NotImplementedError

    async def _direct_connection() -> str:
        await asyncio.sleep(0)
        return "direct"

    use_pool, pool_connection, connection = await init_async_resources(
        use_pool=True,
        create_pool=_unsupported_pool,
        create_connection=_direct_connection,
    )

    assert use_pool is False
    assert pool_connection is None
    assert connection == "direct"


def test_storage_inventory_strategy_registry_returns_expected_strategy_types() -> None:
    sync_strategy = get_sync_storage_inventory_strategy("postgresql")
    async_strategy = get_async_storage_inventory_strategy("postgresql")

    assert sync_strategy is not None
    assert async_strategy is not None


def test_get_sync_connection_wraps_pool_errors() -> None:
    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = TimeoutError("pool timeout")

    with pytest.raises(DatabaseOperationError, match="Timeout obteniendo conexión del pool"):
        SyncConnectionLifecycleManager("postgresql", MagicMock()).get_connection(
            pool_connection=mock_pool,
            connection=None,
        )


def test_close_sync_resources_aggregates_errors() -> None:
    failing_cursor = MagicMock()
    failing_cursor.close.side_effect = RuntimeError("cursor boom")

    with pytest.raises(DatabaseOperationError, match="Errores cerrando recursos") as exc_info:
        SyncConnectionLifecycleManager("sqlite", MagicMock()).close_resources(
            pool_connection=None,
            cursor=failing_cursor,
            connection=None,
            timeout_seconds=1.0,
            force=False,
        )

    assert exc_info.value.__cause__ is not None
    assert "cursor boom" in str(exc_info.value.__cause__)


def test_normalize_ddl_result_prefers_create_text_and_reads_lob_values() -> None:
    class _FakeLob:
        def read(self) -> str:
            return "CREATE TABLE demo(id INT)"

    assert DDLNormalizer.normalize_result(("ignored", "fallback", _FakeLob())) == "CREATE TABLE demo(id INT)"
    assert DDLNormalizer.normalize_result((None, ("nested", "CREATE VIEW v AS SELECT 1"))) == "CREATE VIEW v AS SELECT 1"


def test_parse_charset_helpers_cover_multiple_motors() -> None:
    parser = CharsetCollationParser(MagicMock())
    assert parser.parse_db_charset("oracle", ("AL32UTF8", "AL16UTF16")) == {
        "charset": "AL32UTF8",
        "nchar_charset": "AL16UTF16",
    }
    assert parser.parse_db_charset("postgresql", ("UTF8", "es_ES", "es_ES")) == {
        "encoding": "UTF8",
        "collate": "es_ES",
        "ctype": "es_ES",
    }
    assert parser.parse_db_charset("sqlite", ("UTF-8",)) == {"encoding": "UTF-8"}


def test_parse_column_charset_and_support_rules_are_shared() -> None:
    parser = CharsetCollationParser(MagicMock())
    assert parser.parse_column_charset_collation("postgresql", ("name", "unused", "es_ES")) == (
        "name",
        None,
        "es_ES",
    )
    assert parser.parse_column_charset_collation("sqlite", ("name",)) == ("name", None, None)
    assert CharsetCollationParser._oracle_supports_columns_charset_collation(
        "Oracle Database 19c Release 19.0.0.0.0"
    ) is True
    assert CharsetCollationParser._oracle_supports_columns_charset_collation("Oracle Database 11g") is False
    assert parser.supports_charset_collation("sqlite") is False
    assert parser.supports_charset_collation("oracle", "Oracle Database 19c Release 19.0.0.0.0") is True


def test_generic_strategy_build_sync_text_fetcher_uses_query_request_and_normalizer() -> None:
    request = MetadataFetchRequest(
        query_name="create_table",
        params={"database": "demo", "tabla": "users"},
        error_message="boom",
        table_name="users",
        expect_one=True,
    )
    seen_request: list[MetadataFetchRequest] = []

    fetcher = get_metadata_fetch_strategy("postgresql").build_sync_text_fetcher(
        request=request,
        specialized_fetcher=lambda: "mariadb",
        execute_one=lambda req: seen_request.append(req) or ("ignored", "CREATE TABLE users(id INT)"),
        normalize_one=DDLNormalizer.normalize_result,
    )

    assert fetcher() == "CREATE TABLE users(id INT)"
    assert seen_request == [request]


@pytest.mark.asyncio
async def test_mariadb_strategy_build_async_rows_fetcher_uses_specialized_branch() -> None:
    request = MetadataFetchRequest(
        query_name="columnas_tabla",
        params={"database": "demo", "tabla": "users"},
        error_message="boom",
        table_name="users",
    )

    fetcher = get_metadata_fetch_strategy("mariadb").build_async_rows_fetcher(
        request=request,
        specialized_fetcher=lambda: asyncio.sleep(0, result=[("id",)]),
        execute_many=lambda _req: asyncio.sleep(0, result=[]),
    )

    assert await fetcher() == [("id",)]


@pytest.mark.asyncio
async def test_generic_strategy_build_async_text_fetcher_normalizes_result() -> None:
    request = MetadataFetchRequest(
        query_name="create_view",
        params={"database": "demo", "tabla": "v_users"},
        error_message="boom",
        table_name="v_users",
        expect_one=True,
    )

    fetcher = get_metadata_fetch_strategy("postgresql").build_async_text_fetcher(
        request=request,
        specialized_fetcher=lambda: asyncio.sleep(0, result="CREATE VIEW v_users AS SELECT 1"),
        execute_one=lambda _req: asyncio.sleep(0, result=(None, "CREATE VIEW v_users AS SELECT 1")),
        normalize_one=DDLNormalizer.normalize_result,
    )

    assert await fetcher() == "CREATE VIEW v_users AS SELECT 1"


def test_build_routine_ddl_fetch_request_adds_context_params() -> None:
    request = MetadataRequestBuilder.routine_ddl(
        "analytics",
        "sp_demo",
        "PROCEDURE",
        lambda params, context: {**params, "database": context},
    )

    assert request == MetadataFetchRequest(
        query_name="create_rutina",
        params={
            "rutina": "sp_demo",
            "tipo_rutina": "PROCEDURE",
            "database": "analytics",
        },
        error_message="Error obteniendo DDL de rutina",
        table_name="sp_demo",
        expect_one=True,
    )
