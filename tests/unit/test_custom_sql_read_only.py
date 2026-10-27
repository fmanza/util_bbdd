"""U-T8 (G19 y G20 de util_bbdd_web): ``read_only`` y ``max_rows`` en ``execute_custom_*``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.exceptions import DatabaseOperationError
from util_bbdd.executors._read_only import READ_ONLY_EPILOGUE, READ_ONLY_PRELUDE
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor

pytestmark = pytest.mark.unit


@pytest.fixture
def manager(tmp_path: Path) -> Iterator[SyncDatabaseManager]:
    with SyncDatabaseManager("sqlite", {"database": str(tmp_path / "t.db")}) as manager:
        manager.execute_custom_many("CREATE TABLE t (id INTEGER)")
        manager.execute_custom_many("INSERT INTO t VALUES (1), (2), (3)")
        yield manager


def test_max_rows_cuts_the_result(manager: SyncDatabaseManager) -> None:
    assert manager.execute_custom_many("SELECT id FROM t ORDER BY id", max_rows=2) == [(1,), (2,)]
    assert len(manager.execute_custom_many("SELECT id FROM t", max_rows=10)) == 3


@pytest.mark.parametrize("max_rows", [0, -1, True, 2.0, "3"])
def test_invalid_max_rows(manager: SyncDatabaseManager, max_rows: Any) -> None:
    with pytest.raises(ValueError, match="max_rows"):
        manager.execute_custom_many("SELECT 1", max_rows=max_rows)


def test_read_only_reads_and_rejects_writes(manager: SyncDatabaseManager) -> None:
    assert manager.execute_custom_one("SELECT COUNT(*) FROM t", read_only=True) == (3,)
    with pytest.raises(DatabaseOperationError) as caught:
        manager.execute_custom_many("INSERT INTO t VALUES (9)", read_only=True)
    assert "readonly" in str(caught.value.__cause__).replace(" ", "").lower()

    manager.execute_custom_many("INSERT INTO t VALUES (4)")  # la sesión vuelve a escritura
    assert manager.execute_custom_one("SELECT COUNT(*) FROM t") == (4,)


@pytest.mark.asyncio
async def test_async_read_only_and_max_rows(tmp_path: Path) -> None:
    pytest.importorskip("aiosqlite")
    async with AsyncDatabaseManager("sqlite", {"database": str(tmp_path / "a.db")}) as manager:
        await manager.execute_custom_many("CREATE TABLE t (id INTEGER)")
        await manager.execute_custom_many("INSERT INTO t VALUES (1), (2), (3)")

        assert await manager.execute_custom_many("SELECT id FROM t ORDER BY id", max_rows=1) == [(1,)]
        assert await manager.execute_custom_one("SELECT COUNT(*) FROM t", read_only=True) == (3,)
        with pytest.raises(DatabaseOperationError):
            await manager.execute_custom_many("DELETE FROM t", read_only=True)
        assert await manager.execute_custom_one("SELECT COUNT(*) FROM t") == (3,)


class _Cursor:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def execute(self, sql: str, *args: Any) -> None:
        self.log.append(sql)

    def fetchall(self) -> list[tuple[int]]:
        return [(1,)]

    def fetchmany(self, size: int) -> list[tuple[int]]:
        self.log.append(f"fetchmany({size})")
        return [(1,)]

    def close(self) -> None:
        pass


class _Connection:
    def __init__(self) -> None:
        self.log: list[str] = []

    def cursor(self) -> _Cursor:
        return _Cursor(self.log)

    def rollback(self) -> None:
        self.log.append("<rollback>")


@pytest.mark.parametrize("db_type", sorted(READ_ONLY_PRELUDE))
def test_each_engine_wraps_the_query(db_type: str) -> None:
    conn = _Connection()
    executor = SyncQueryExecutor(lambda: conn, lambda _conn: None)

    executor.execute_custom_many("SELECT 1", read_only=True, max_rows=5, db_type=db_type)

    assert conn.log == [
        "<rollback>",
        *READ_ONLY_PRELUDE[db_type],
        "SELECT 1",
        "fetchmany(5)",
        "<rollback>",
        *READ_ONLY_EPILOGUE.get(db_type, ()),
    ]


def test_read_only_needs_a_known_engine() -> None:
    executor = SyncQueryExecutor(lambda: _Connection(), lambda _conn: None)
    with pytest.raises(ValueError, match="db_type"):
        executor.execute_custom_many("SELECT 1", read_only=True)


def test_without_options_nothing_changes() -> None:
    conn = _Connection()
    SyncQueryExecutor(lambda: conn, lambda _conn: None).execute_custom_many("SELECT 1")
    assert conn.log == ["SELECT 1"]
