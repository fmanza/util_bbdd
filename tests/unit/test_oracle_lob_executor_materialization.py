"""Pruebas de materialización de LOB Oracle en ejecutores."""

from __future__ import annotations

import json

from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.query.registry import QueryRegistry


class _FakeOracleLob:
    def __init__(self, text: str, conn_state: dict[str, bool]) -> None:
        self._text = text
        self._conn_state = conn_state

    def read(self) -> str:
        if not self._conn_state.get("open", False):
            raise RuntimeError("DPY-1001: not connected to database")
        return self._text


def _build_oracle_registry(tmp_path) -> QueryRegistry:
    queries_file = tmp_path / "oracle_queries.json"
    queries_file.write_text(
        json.dumps(
            {
                "oracle": {
                    "create_table": "SELECT DBMS_METADATA.GET_DDL('TABLE', 'USERS', 'HR') AS DDL FROM DUAL",
                }
            }
        ),
        encoding="utf-8",
    )
    return QueryRegistry(queries_file=queries_file)


def test_sync_executor_materializes_oracle_lob_before_releasing_connection(tmp_path) -> None:
    conn_state = {"open": True}
    fake_lob = _FakeOracleLob("CREATE TABLE USERS (ID NUMBER)", conn_state)

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (fake_lob,)
    mock_conn.cursor.return_value = mock_cursor

    def _release(_conn) -> None:
        conn_state["open"] = False

    executor = SyncQueryExecutor(
        connection_provider=MagicMock(return_value=mock_conn),
        connection_releaser=_release,
        registry=_build_oracle_registry(tmp_path),
    )

    result = executor.execute_query_one("create_table", "oracle", {})

    assert result == ("CREATE TABLE USERS (ID NUMBER)",)
    assert conn_state["open"] is False


@pytest.mark.asyncio
async def test_async_executor_materializes_oracle_lob_before_releasing_connection(tmp_path) -> None:
    conn_state = {"open": True}
    fake_lob = _FakeOracleLob("CREATE TABLE USERS (ID NUMBER)", conn_state)

    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchone.return_value = (fake_lob,)
    mock_conn.cursor.return_value = mock_cursor

    async def _release(_conn) -> None:
        conn_state["open"] = False

    executor = AsyncQueryExecutor(
        connection_provider=AsyncMock(return_value=mock_conn),
        connection_releaser=_release,
        registry=_build_oracle_registry(tmp_path),
    )

    result = await executor.execute_query_one("create_table", "oracle", {})

    assert result == ("CREATE TABLE USERS (ID NUMBER)",)
    assert conn_state["open"] is False
