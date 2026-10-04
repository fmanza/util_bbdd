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
from util_bbdd.managers._metadata_context import MetadataContextResolver


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


@pytest.mark.parametrize(
    ("user", "expected"),
    [("scott", "SCOTT"), ("Scott", "SCOTT"), ("SCOTT", "SCOTT"), ('"MixedCase"', "MixedCase")],
)
def test_oracle_context_is_the_user_as_oracle_stores_it(user: str, expected: str) -> None:
    """H-18: Oracle guarda en mayúsculas los nombres sin comillas; con ``user="bench"`` los metadatos salían vacíos."""
    assert (
        MetadataContextResolver.get_context_database(db_type="oracle", database="XE", conn_params={"user": user})
        == expected
    )


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
