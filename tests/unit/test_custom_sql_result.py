"""U-8.4 (G42 de util_bbdd_web): ``execute_custom_result`` con columnas y plazo en el servidor (PostgreSQL)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.exceptions import DatabaseOperationError, QueryTimeoutError
from util_bbdd.executors._read_only import READ_ONLY_PRELUDE, is_server_timeout, server_timeout_statements
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.results import CustomQueryResult

pytestmark = pytest.mark.unit


@pytest.fixture
def manager(tmp_path: Path) -> Iterator[SyncDatabaseManager]:
    with SyncDatabaseManager("sqlite", {"database": str(tmp_path / "t.db")}) as manager:
        manager.execute_custom_many("CREATE TABLE t (id INTEGER, nombre TEXT)")
        manager.execute_custom_many("INSERT INTO t VALUES (1, 'a'), (2, 'b'), (3, 'c')")
        yield manager


def test_columns_and_rows(manager: SyncDatabaseManager) -> None:
    result = manager.execute_custom_result("SELECT id, nombre FROM t ORDER BY id")

    assert result == CustomQueryResult(columns=("id", "nombre"), rows=[(1, "a"), (2, "b"), (3, "c")])


def test_columns_without_rows(manager: SyncDatabaseManager) -> None:
    result = manager.execute_custom_result("SELECT id, nombre AS n FROM t WHERE id > 99")

    assert result.columns == ("id", "n")
    assert result.rows == []


def test_repeated_column_names_are_kept(manager: SyncDatabaseManager) -> None:
    assert manager.execute_custom_result("SELECT 1 AS a, 2 AS a").columns == ("a", "a")


def test_max_rows_cuts_the_result(manager: SyncDatabaseManager) -> None:
    result = manager.execute_custom_result("SELECT id FROM t ORDER BY id", max_rows=2)

    assert result.rows == [(1,), (2,)]
    assert result.columns == ("id",)


@pytest.mark.parametrize("max_rows", [0, True, "3"])
def test_invalid_max_rows(manager: SyncDatabaseManager, max_rows: Any) -> None:
    with pytest.raises(ValueError, match="max_rows"):
        manager.execute_custom_result("SELECT 1", max_rows=max_rows)


def test_read_only_blocks_a_delete(manager: SyncDatabaseManager) -> None:
    with pytest.raises(DatabaseOperationError):
        manager.execute_custom_result("DELETE FROM t", read_only=True)

    assert manager.execute_custom_one("SELECT COUNT(*) FROM t") == (3,)


def test_statement_without_result_set_has_no_columns(manager: SyncDatabaseManager) -> None:
    result = manager.execute_custom_result("UPDATE t SET nombre = 'x' WHERE id = 1")

    assert result == CustomQueryResult()
    assert manager.execute_custom_one("SELECT nombre FROM t WHERE id = 1") == ("x",)


def test_result_is_immutable() -> None:
    result = CustomQueryResult(columns=("a",), rows=[(1,)])
    with pytest.raises(AttributeError):
        result.columns = ()  # type: ignore[misc]


@pytest.mark.asyncio
async def test_async_columns_rows_and_read_only(tmp_path: Path) -> None:
    pytest.importorskip("aiosqlite")
    async with AsyncDatabaseManager("sqlite", {"database": str(tmp_path / "a.db")}) as manager:
        await manager.execute_custom_many("CREATE TABLE t (id INTEGER, nombre TEXT)")
        await manager.execute_custom_many("INSERT INTO t VALUES (1, 'a'), (2, 'b')")

        result = await manager.execute_custom_result("SELECT id, nombre FROM t ORDER BY id", max_rows=1)
        assert result == CustomQueryResult(columns=("id", "nombre"), rows=[(1, "a")])
        empty = await manager.execute_custom_result("SELECT 1 AS a, 2 AS a FROM t WHERE id > 99", read_only=True)
        assert empty == CustomQueryResult(columns=("a", "a"), rows=[])
        with pytest.raises(DatabaseOperationError):
            await manager.execute_custom_result("DELETE FROM t", read_only=True)
        assert await manager.execute_custom_one("SELECT COUNT(*) FROM t") == (2,)


# ----------------------------------------------------------------- plazo en el servidor (D8-4), con dobles


class _Cursor:
    description = (("x", None, None, None, None, None, None),)

    def __init__(self, conn: _Connection) -> None:
        self.conn = conn

    def execute(self, sql: str, *args: Any) -> None:
        self.conn.log.append(sql)
        if self.conn.fail_with is not None and not sql.startswith(("SET", "START", "BEGIN", "PRAGMA")):
            raise self.conn.fail_with

    def fetchall(self) -> list[tuple[int]]:
        return [(1,)]

    def fetchmany(self, size: int) -> list[tuple[int]]:
        return [(1,)]

    def close(self) -> None:
        pass


class _Connection:
    def __init__(self, fail_with: Exception | None = None) -> None:
        self.log: list[str] = []
        self.fail_with = fail_with

    def cursor(self) -> _Cursor:
        return _Cursor(self)

    def rollback(self) -> None:
        self.log.append("<rollback>")


class _QueryCanceled(Exception):
    """Como ``psycopg.errors.QueryCanceled``: SQLSTATE 57014."""

    sqlstate = "57014"


def test_postgresql_read_only_sets_the_server_timeout() -> None:
    conn = _Connection()
    result = SyncQueryExecutor(lambda: conn, lambda _conn: None).execute_custom_result(
        "SELECT 1", timeout=2.5, read_only=True, db_type="postgresql"
    )

    assert result == CustomQueryResult(columns=("x",), rows=[(1,)])
    assert conn.log == [
        "<rollback>",
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = 2500",
        "SELECT 1",
        "<rollback>",
    ]


@pytest.mark.parametrize(
    ("db_type", "read_only", "timeout"),
    [("postgresql", False, 5.0), ("postgresql", True, None), ("mysql", True, 5.0), ("oracle", True, 5.0)],
)
def test_no_server_timeout_otherwise(db_type: str, read_only: bool, timeout: float | None) -> None:
    conn = _Connection()
    SyncQueryExecutor(lambda: conn, lambda _conn: None).execute_custom_result(
        "SELECT 1", timeout=timeout, read_only=read_only, db_type=db_type
    )

    assert not any("statement_timeout" in sql for sql in conn.log)
    if read_only:
        assert conn.log[1 : 1 + len(READ_ONLY_PRELUDE[db_type])] == list(READ_ONLY_PRELUDE[db_type])


def test_execute_custom_many_keeps_the_client_side_timeout_only() -> None:
    conn = _Connection()
    SyncQueryExecutor(lambda: conn, lambda _conn: None).execute_custom_many(
        "SELECT 1", timeout=5.0, read_only=True, db_type="postgresql"
    )

    assert not any("statement_timeout" in sql for sql in conn.log)


def test_server_cancellation_raises_query_timeout_error() -> None:
    conn = _Connection(fail_with=_QueryCanceled("canceling statement due to statement timeout"))
    with pytest.raises(QueryTimeoutError) as caught:
        SyncQueryExecutor(lambda: conn, lambda _conn: None).execute_custom_result(
            "SELECT pg_sleep(10)", timeout=5.0, read_only=True, db_type="postgresql"
        )

    assert isinstance(caught.value.__cause__, _QueryCanceled)
    assert conn.log[-1] == "<rollback>"


@pytest.mark.parametrize(
    ("timeout", "expected"),
    [(0.0001, ("SET LOCAL statement_timeout = 1",)), (1, ("SET LOCAL statement_timeout = 1000",))],
)
def test_server_timeout_statements(timeout: float, expected: tuple[str, ...]) -> None:
    assert server_timeout_statements("PostgreSQL ", timeout) == expected
    assert server_timeout_statements("sqlserver", timeout) == ()


@pytest.mark.parametrize("timeout", [float("inf"), float("nan")])
def test_non_finite_timeout_sets_no_server_limit(timeout: float) -> None:
    assert server_timeout_statements("postgresql", timeout) == ()


def test_is_server_timeout_follows_the_cause_chain() -> None:
    class _Wrapper(Exception):
        def __init__(self, orig: BaseException) -> None:
            super().__init__("wrapped")
            self.orig = orig

    class _Psycopg2Error(Exception):
        pgcode = "57014"

    assert is_server_timeout(_Wrapper(_Psycopg2Error()))
    try:
        raise RuntimeError("fuera") from _QueryCanceled()
    except RuntimeError as err:
        assert is_server_timeout(err)
    assert not is_server_timeout(ValueError("otro"))
