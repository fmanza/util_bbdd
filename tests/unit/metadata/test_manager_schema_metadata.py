"""``get_schema_metadata()`` de los managers (C1, ADR-003) con SQLite real, sin servidor."""

from __future__ import annotations

import asyncio
import importlib.util
import sqlite3

from contextlib import closing
from pathlib import Path

import pytest

from sqlalchemy.pool import QueuePool

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd._core.exceptions import MetadataError
from util_bbdd.managers._catalog_executor import driver_paramstyle
from util_bbdd.metadata import Kind, KindNotLoadedError


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "c1.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE p (id INTEGER PRIMARY KEY, code TEXT UNIQUE);"
        "CREATE TABLE c (id INTEGER PRIMARY KEY, p_id INTEGER REFERENCES p(id));"
        "CREATE INDEX ix_c_p ON c (p_id);"
    )
    conn.close()
    return path


def test_sync_manager_reads_the_whole_schema(db: Path) -> None:
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as mgr:
        snapshot = mgr.get_schema_metadata()
        assert snapshot.schema == "main"
        assert [t.name for t in snapshot.tables()] == ["c", "p"]
        assert snapshot.foreign_keys("c")[0].ref_table == "p"
        assert [i.name for i in snapshot.indexes("c")] == ["ix_c_p"]


def test_sync_manager_caches_and_clear_cache_invalidates(db: Path) -> None:
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as mgr:
        first = mgr.get_schema_metadata(kinds={Kind.TABLES})
        assert mgr.get_schema_metadata(kinds={Kind.TABLES}).data[Kind.TABLES] is first.data[Kind.TABLES]
        mgr.execute_custom_many("CREATE TABLE z (id INTEGER)")  # DDL propio: la caché aún no lo ve
        assert [t.name for t in mgr.get_schema_metadata(kinds={Kind.TABLES}).tables()] == ["c", "p"]
        mgr.clear_cache()
        assert [t.name for t in mgr.get_schema_metadata(kinds={Kind.TABLES}).tables()] == ["c", "p", "z"]


def test_selective_clear_cache_invalidates_the_schema(db: Path) -> None:
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as mgr:
        first = mgr.get_schema_metadata(kinds={Kind.COLUMNS})
        mgr.clear_cache(table="c")
        assert mgr.get_schema_metadata(kinds={Kind.COLUMNS}).data[Kind.COLUMNS] is not first.data[Kind.COLUMNS]


def test_filtered_and_partial_snapshots(db: Path) -> None:
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as mgr:
        snapshot = mgr.get_schema_metadata(kinds={Kind.COLUMNS}, tables=["p"])
        assert {c.table for c in snapshot.data[Kind.COLUMNS]} == {"p"}
        with pytest.raises(KindNotLoadedError):
            snapshot.tables()


@pytest.mark.skipif(importlib.util.find_spec("aiosqlite") is None, reason="aiosqlite no instalado")
def test_async_manager_matches_sync(db: Path) -> None:
    async def read() -> list[str]:
        manager = AsyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False)
        try:
            snapshot = await manager.get_schema_metadata()
            return [t.name for t in snapshot.tables()] + [fk.ref_table for fk in snapshot.foreign_keys("c")]
        finally:
            await manager.close()

    assert asyncio.run(read()) == ["c", "p", "p"]


def test_driver_paramstyle_by_connection_module() -> None:
    with closing(sqlite3.connect(":memory:")) as conn:
        assert driver_paramstyle(conn) == "qmark"

    class Fake:
        pass

    Fake.__module__ = "asyncpg.connection"
    assert driver_paramstyle(Fake()) == "dollar"
    Fake.__module__ = "desconocido.driver"
    with pytest.raises(MetadataError):
        driver_paramstyle(Fake())


def test_driver_paramstyle_unwraps_sqlalchemy_pool_connections() -> None:
    """MySQL con pool entrega un ``_ConnectionFairy`` de SQLAlchemy: cuenta el estilo del driver que envuelve."""
    pool = QueuePool(lambda: sqlite3.connect(":memory:"))
    connection = pool.connect()
    try:
        assert type(connection).__module__.startswith("sqlalchemy")
        assert driver_paramstyle(connection) == "qmark"
    finally:
        connection.close()
        pool.dispose()
