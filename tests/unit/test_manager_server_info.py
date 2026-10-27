"""U-T6 (G13 y G17 de util_bbdd_web): ``ping()``, ``get_server_version()`` y ``get_schema_names()``."""

from __future__ import annotations

import sqlite3

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.exceptions import MetadataError
from util_bbdd.metadata import CatalogSource
from util_bbdd.metadata.catalog_registry import get_catalog_dialect, supported_catalog_engines
from util_bbdd.metadata.contracts import ServerInfoCatalogDialect

pytestmark = pytest.mark.unit


class _Recorder:
    """``CatalogExecutor`` de prueba: devuelve filas fijas y anota el SQL."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.sql: list[str] = []

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        self.sql.append(sql)
        return self.rows


@pytest.mark.parametrize("db_type", supported_catalog_engines())
def test_every_builtin_dialect_has_server_info(db_type: str) -> None:
    dialect = get_catalog_dialect(db_type)
    assert isinstance(dialect, ServerInfoCatalogDialect)
    assert dialect.server_version_sql().strip() and dialect.schema_names_sql().strip()
    assert "%" not in dialect.schema_names_sql()  # sin '%': pyformat lo tomaría por un parámetro


def test_sqlite_manager(tmp_path: Path) -> None:
    with SyncDatabaseManager("sqlite", {"database": str(tmp_path / "a.db")}) as manager:
        assert 0 <= manager.ping() < 5
        assert manager.get_server_version() == sqlite3.sqlite_version
        assert manager.get_schema_names() == ["main"]


@pytest.mark.asyncio
async def test_sqlite_async_manager(tmp_path: Path) -> None:
    pytest.importorskip("aiosqlite")
    async with AsyncDatabaseManager("sqlite", {"database": str(tmp_path / "a.db")}) as manager:
        assert 0 <= await manager.ping() < 5
        assert await manager.get_server_version() == sqlite3.sqlite_version
        assert await manager.get_schema_names() == ["main"]


def test_server_info_is_read_every_time() -> None:
    executor = _Recorder([("19.0.0.0.0",)])
    source = CatalogSource(get_catalog_dialect("oracle"), executor, source_id="x")

    assert source.server_version() == "19.0.0.0.0"
    source.server_version()
    assert len(executor.sql) == 2  # sin caché


def test_oracle_schema_names_keep_the_catalog_case() -> None:
    executor = _Recorder([("SYS",), ("BENCH",), ("BENCH",), (None,)])
    source = CatalogSource(get_catalog_dialect("oracle"), executor, source_id="x")

    assert source.schema_names() == ["BENCH", "SYS"]
    assert "all_users" in executor.sql[0]


def test_empty_version_is_none() -> None:
    source = CatalogSource(get_catalog_dialect("postgresql"), _Recorder([]), source_id="x")
    assert source.server_version() is None


def test_dialect_without_the_protocol_raises() -> None:
    class Minimal:
        name = "minimo"
        sqlalchemy_names = frozenset()

        def current_schema_sql(self) -> str:
            return "SELECT 'x'"

        def normalize_name(self, name: str) -> str:
            return name

        def query(self, kind: Any, *, filtered: bool = False) -> None:
            return None

        def parse(self, kind: Any, rows: Any, schema: str) -> tuple[Any, ...]:
            return ()

    source = CatalogSource(Minimal(), _Recorder([("x",)]), source_id="x")  # type: ignore[arg-type]
    source.ping()  # solo necesita current_schema_sql
    with pytest.raises(MetadataError, match="schema_names_sql"):
        source.schema_names()
