"""Tests focalizados para helpers internos de managers."""

from __future__ import annotations

import asyncio

from unittest.mock import MagicMock

import pytest

from util_bbdd.database_exceptions import DatabaseOperationError
from util_bbdd.managers._manager_lifecycle import (
    close_sync_resources,
    get_sync_connection,
    init_async_resources,
)
from util_bbdd.managers._manager_metadata import (
    cache_routine_key,
    clear_context_cache,
    get_query_context_database,
)
from util_bbdd.managers._manager_metadata_runtime import (
    MetadataFetchRequest,
    build_async_rows_fetcher,
    build_async_text_fetcher,
    build_routine_ddl_fetch_request,
    build_sync_text_fetcher,
    normalize_ddl_result,
    oracle_supports_columns_charset_collation,
    parse_charset_collation_result,
    parse_column_charset_collation_row,
    supports_columns_charset_collation,
)
from util_bbdd.managers._manager_storage import get_storage_inventory_handler
from util_bbdd.metadata import DatabaseMetadataCache


def test_get_query_context_database_uses_schema_defaults() -> None:
    assert (
        get_query_context_database(db_type="postgresql", database="demo", conn_params={"schema": "analytics"})
        == "analytics"
    )
    assert get_query_context_database(db_type="oracle", database="XE", conn_params={"user": "SCOTT"}) == "SCOTT"
    assert get_query_context_database(db_type="sqlserver", database="", conn_params={}) == "dbo"


def test_clear_context_cache_removes_only_matching_entries() -> None:
    db_cache = DatabaseMetadataCache()
    db_cache._tables_cache["public"] = [("users",)]
    db_cache._tables_cache["audit"] = [("events",)]
    db_cache._columns_cache[("public", "users")] = [("id",)]
    db_cache._columns_cache[("audit", "events")] = [("id",)]
    db_cache._routine_ddl_cache[cache_routine_key("public", "proc_a", "procedure")] = "DDL"
    db_cache._routine_ddl_cache[cache_routine_key("audit", "proc_b", "procedure")] = "DDL"

    clear_context_cache(db_cache=db_cache, logger=MagicMock(), context="public")

    assert "public" not in db_cache._tables_cache
    assert "audit" in db_cache._tables_cache
    assert ("public", "users") not in db_cache._columns_cache
    assert ("audit", "events") in db_cache._columns_cache
    assert cache_routine_key("public", "proc_a", "procedure") not in db_cache._routine_ddl_cache
    assert cache_routine_key("audit", "proc_b", "procedure") in db_cache._routine_ddl_cache


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


def test_get_storage_inventory_handler_returns_selected_handler() -> None:
    def handler(context: str, tablespace: str | None) -> dict[str, str | None]:
        return {"context": context, "tablespace": tablespace}

    assert get_storage_inventory_handler("postgresql", {"postgresql": handler}) is handler
    assert get_storage_inventory_handler("sqlite", {"postgresql": handler}) is None


def test_get_sync_connection_wraps_pool_errors() -> None:
    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = TimeoutError("pool timeout")

    with pytest.raises(DatabaseOperationError, match="Timeout obteniendo conexión del pool"):
        get_sync_connection(
            pool_connection=mock_pool,
            connection=None,
            db_type="postgresql",
            logger=MagicMock(),
        )


def test_close_sync_resources_aggregates_errors() -> None:
    failing_cursor = MagicMock()
    failing_cursor.close.side_effect = RuntimeError("cursor boom")

    with pytest.raises(DatabaseOperationError, match="Errores cerrando recursos") as exc_info:
        close_sync_resources(
            pool_connection=None,
            cursor=failing_cursor,
            connection=None,
            logger=MagicMock(),
            db_type="sqlite",
            timeout_seconds=1.0,
            force=False,
        )

    assert exc_info.value.__cause__ is not None
    assert "cursor boom" in str(exc_info.value.__cause__)


def test_normalize_ddl_result_prefers_create_text_and_reads_lob_values() -> None:
    class _FakeLob:
        def read(self) -> str:
            return "CREATE TABLE demo(id INT)"

    assert normalize_ddl_result(("ignored", "fallback", _FakeLob())) == "CREATE TABLE demo(id INT)"
    assert normalize_ddl_result((None, ("nested", "CREATE VIEW v AS SELECT 1"))) == "CREATE VIEW v AS SELECT 1"


def test_parse_charset_helpers_cover_multiple_motors() -> None:
    assert parse_charset_collation_result("oracle", ("AL32UTF8", "AL16UTF16")) == {
        "charset": "AL32UTF8",
        "nchar_charset": "AL16UTF16",
    }
    assert parse_charset_collation_result("postgresql", ("UTF8", "es_ES", "es_ES")) == {
        "encoding": "UTF8",
        "collate": "es_ES",
        "ctype": "es_ES",
    }
    assert parse_charset_collation_result("sqlite", ("UTF-8",)) == {"encoding": "UTF-8"}


def test_parse_column_charset_and_support_rules_are_shared() -> None:
    assert parse_column_charset_collation_row("postgresql", ("name", "unused", "es_ES")) == (
        "name",
        None,
        "es_ES",
    )
    assert parse_column_charset_collation_row("sqlite", ("name",)) == ("name", None, None)
    assert oracle_supports_columns_charset_collation("Oracle Database 19c Release 19.0.0.0.0") is True
    assert oracle_supports_columns_charset_collation("Oracle Database 11g") is False
    assert supports_columns_charset_collation("sqlite") is False
    assert supports_columns_charset_collation("oracle", True) is True


def test_build_sync_text_fetcher_uses_query_request_and_normalizer() -> None:
    request = MetadataFetchRequest(
        query_name="create_table",
        params={"database": "demo", "tabla": "users"},
        error_message="boom",
        table_name="users",
        expect_one=True,
    )
    seen_request: list[MetadataFetchRequest] = []

    fetcher = build_sync_text_fetcher(
        db_type="postgresql",
        mariadb_fetcher=lambda: "mariadb",
        request=request,
        execute_one=lambda req: seen_request.append(req) or ("ignored", "CREATE TABLE users(id INT)"),
        normalize_one=normalize_ddl_result,
    )

    assert fetcher() == "CREATE TABLE users(id INT)"
    assert seen_request == [request]


@pytest.mark.asyncio
async def test_build_async_rows_fetcher_prefers_mariadb_branch() -> None:
    request = MetadataFetchRequest(
        query_name="columnas_tabla",
        params={"database": "demo", "tabla": "users"},
        error_message="boom",
        table_name="users",
    )

    fetcher = build_async_rows_fetcher(
        db_type="mariadb",
        mariadb_fetcher=lambda: asyncio.sleep(0, result=[("id",)]),
        request=request,
        execute_many=lambda _req: asyncio.sleep(0, result=[]),
    )

    assert await fetcher() == [("id",)]


@pytest.mark.asyncio
async def test_build_async_text_fetcher_normalizes_result() -> None:
    request = MetadataFetchRequest(
        query_name="create_view",
        params={"database": "demo", "tabla": "v_users"},
        error_message="boom",
        table_name="v_users",
        expect_one=True,
    )

    fetcher = build_async_text_fetcher(
        db_type="postgresql",
        mariadb_fetcher=lambda: asyncio.sleep(0, result="CREATE VIEW v_users AS SELECT 1"),
        request=request,
        execute_one=lambda _req: asyncio.sleep(0, result=(None, "CREATE VIEW v_users AS SELECT 1")),
        normalize_one=normalize_ddl_result,
    )

    assert await fetcher() == "CREATE VIEW v_users AS SELECT 1"


def test_build_routine_ddl_fetch_request_adds_context_params() -> None:
    request = build_routine_ddl_fetch_request(
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
