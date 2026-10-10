"""``AsyncQueryExecutor`` con conexiones de asyncpg (hotfix de 1.1.0).

asyncpg no es DB-API: ``Connection.cursor(query, ...)`` exige la consulta y no hay ``execute``/``fetchone`` en el
cursor. Hasta v1.0.0 el ejecutor async llamaba a ``conn.cursor()`` sin argumentos y toda consulta de
``AsyncDatabaseManager("postgresql")`` (``execute_custom_*`` y ``execute_query_*``) fallaba con
``DatabaseOperationError: Connection.cursor() missing 1 required positional argument: 'query'``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from util_bbdd.exceptions import DatabaseOperationError
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.query import QueryRegistry


class FakeRecord(tuple):
    """Como ``asyncpg.Record``: se convierte en tupla con ``tuple(record)``."""


class FakeAsyncpgConnection:
    """Imita la API de ``asyncpg.Connection`` que usa el ejecutor: ``fetch``/``fetchrow`` con ``$n``."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = [FakeRecord(row) for row in rows]
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []

    def cursor(self, query: str, *args: Any) -> Any:  # firma real: la consulta es obligatoria
        raise AssertionError("el ejecutor no debe usar cursores con asyncpg")

    async def fetch(self, query: str, *args: Any) -> list[FakeRecord]:
        self.calls.append(("fetch", query, args))
        return self.rows

    async def fetchrow(self, query: str, *args: Any) -> FakeRecord | None:
        self.calls.append(("fetchrow", query, args))
        return self.rows[0] if self.rows else None


FakeAsyncpgConnection.__module__ = "asyncpg.connection"


def _executor(conn: Any, registry: QueryRegistry | None = None) -> tuple[AsyncQueryExecutor, AsyncMock]:
    releaser = AsyncMock()
    executor = AsyncQueryExecutor(AsyncMock(return_value=conn), releaser, registry=registry)
    return executor, releaser


@pytest.mark.asyncio
async def test_custom_many_without_params_uses_fetch() -> None:
    conn = FakeAsyncpgConnection([(1,), (2,)])
    executor, releaser = _executor(conn)

    assert await executor.execute_custom_many("SELECT 1 AS x") == [(1,), (2,)]

    assert conn.calls == [("fetch", "SELECT 1 AS x", ())]
    releaser.assert_awaited_once_with(conn)


@pytest.mark.asyncio
async def test_custom_one_uses_fetchrow_and_returns_none_without_rows() -> None:
    executor, _ = _executor(FakeAsyncpgConnection([(7, "a")]))
    assert await executor.execute_custom_one("SELECT 7, 'a'") == (7, "a")

    empty = FakeAsyncpgConnection([])
    executor, _ = _executor(empty)
    assert await executor.execute_custom_one("SELECT 1 WHERE false") is None
    assert empty.calls[0][0] == "fetchrow"


@pytest.mark.asyncio
async def test_pyformat_params_become_dollar_positions_in_order_of_first_use() -> None:
    conn = FakeAsyncpgConnection([(1,)])
    executor, _ = _executor(conn)

    await executor.execute_custom_many(
        "SELECT %(a)s, %(b)s, %(a)s WHERE 'x' LIKE 'x%%'", {"b": "B", "a": "A", "unused": 0}
    )

    assert conn.calls == [("fetch", "SELECT $1, $2, $1 WHERE 'x' LIKE 'x%'", ("A", "B"))]


@pytest.mark.asyncio
async def test_named_params_become_dollar_positions_and_casts_are_kept() -> None:
    conn = FakeAsyncpgConnection([(1,)])
    executor, _ = _executor(conn)

    await executor.execute_custom_one("SELECT :id::int, '10:30' WHERE nombre = :nombre", {"id": "5", "nombre": "n"})

    assert conn.calls == [("fetchrow", "SELECT $1::int, '10:30' WHERE nombre = $2", ("5", "n"))]


@pytest.mark.asyncio
async def test_named_query_uses_the_same_path() -> None:
    registry = QueryRegistry()
    registry._queries.setdefault("postgresql", {})["usuario"] = "SELECT id FROM usuarios WHERE id = %(id)s"
    conn = FakeAsyncpgConnection([(3,)])
    executor, _ = _executor(conn, registry)

    assert await executor.execute_query_one("usuario", "postgresql", {"id": 3}) == (3,)
    assert conn.calls == [("fetchrow", "SELECT id FROM usuarios WHERE id = $1", (3,))]


@pytest.mark.asyncio
async def test_driver_errors_are_still_wrapped_and_the_connection_released() -> None:
    conn = FakeAsyncpgConnection([])
    conn.fetch = AsyncMock(side_effect=RuntimeError("relation does not exist"))  # type: ignore[method-assign]
    executor, releaser = _executor(conn)

    with pytest.raises(DatabaseOperationError, match="relation does not exist"):
        await executor.execute_custom_many("SELECT * FROM nada")
    releaser.assert_awaited_once_with(conn)


@pytest.mark.asyncio
async def test_other_drivers_keep_the_cursor_path() -> None:
    cursor = AsyncMock()
    cursor.fetchall.return_value = [(1,)]
    conn = AsyncMock()
    conn.cursor.return_value = cursor
    executor, _ = _executor(conn)

    assert await executor.execute_custom_many("SELECT 1") == [(1,)]
    cursor.execute.assert_awaited_once_with("SELECT 1")
