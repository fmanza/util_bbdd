"""U-8.5 (G43 de util_bbdd_web): versión completa del servidor (Oracle ``VERSION_FULL``) y ``get_server_version_info``."""

from __future__ import annotations

import sqlite3

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.metadata import CatalogSource
from util_bbdd.metadata.catalog_registry import get_catalog_dialect, supported_catalog_engines
from util_bbdd.metadata.contracts import FullServerVersionCatalogDialect
from util_bbdd.metadata.oracle.catalog import Oracle11Catalog, OracleCatalog

pytestmark = pytest.mark.unit


class _Oracle:
    """``CatalogExecutor`` que hace de Oracle: ``VERSION`` siempre; ``VERSION_FULL`` solo si la versión la tiene."""

    def __init__(self, version: str, version_full: str | None) -> None:
        self.version = version
        self.version_full = version_full
        self.sql: list[str] = []

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        self.sql.append(sql)
        if "version_full" in sql:
            if self.version_full is None:
                raise AssertionError("ORA-00904: no se debe consultar VERSION_FULL en esta versión")
            return [(self.version_full,)]
        if "product_component_version" in sql:
            return [(self.version,)]
        return []


def test_oracle_23ai_gives_the_full_version() -> None:
    source = CatalogSource(get_catalog_dialect("oracle"), _Oracle("23.0.0.0.0", "23.26.3.0.0"), source_id="x")

    assert source.server_version() == "23.26.3.0.0"
    assert source.server_version_info() == (23, 26, 3, 0, 0)


@pytest.mark.parametrize("version", ["11.2.0.4.0", "12.2.0.1.0"])
def test_oracle_without_version_full_keeps_version(version: str) -> None:
    executor = _Oracle(version, None)
    source = CatalogSource(get_catalog_dialect("oracle"), executor, source_id="x")

    assert source.server_version() == version
    assert not any("version_full" in sql for sql in executor.sql)  # ninguna consulta que falle


def test_oracle_11g_still_selects_the_11g_catalog() -> None:
    """T8-1: ``_resolve_dialect`` sigue con ``server_version_sql`` (``VERSION``), que 11g sí tiene."""
    executor = _Oracle("11.2.0.4.0", None)
    source = CatalogSource(OracleCatalog(), executor, source_id="x")

    source.server_version()
    source._resolve_dialect()

    assert type(source.dialect) is Oracle11Catalog
    assert "version_full" not in OracleCatalog().server_version_sql().lower()


def test_empty_full_version_falls_back_to_version() -> None:
    source = CatalogSource(get_catalog_dialect("oracle"), _Oracle("19.0.0.0.0", ""), source_id="x")
    assert source.server_version() == "19.0.0.0.0"


def test_only_oracle_has_a_full_version() -> None:
    engines = {
        db for db in supported_catalog_engines() if isinstance(get_catalog_dialect(db), FullServerVersionCatalogDialect)
    }
    assert engines == {"oracle"}
    assert OracleCatalog().full_server_version_sql(None) is None
    assert OracleCatalog().full_server_version_sql((18, 3)) is not None


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("11.4.2-MariaDB-1:11.4.2+maria~ubu2204", (11, 4, 2)),
        ("16.4 (Debian 16.4-1.pgdg120+1)", (16, 4)),
        ("8.0.36", (8, 0, 36)),
        ("16.0.4135.4", (16, 0, 4135, 4)),
        ("2.7.4", (2, 7, 4)),
        (" 17 ", (17,)),
        ("", None),
        (None, None),
        ("PostgreSQL 16.4", None),
    ],
)
def test_version_info_parsing(version: str | None, expected: tuple[int, ...] | None) -> None:
    assert CatalogSource._version_info(version) == expected


def test_sqlite_manager_version_info(tmp_path: Path) -> None:
    with SyncDatabaseManager("sqlite", {"database": str(tmp_path / "a.db")}) as manager:
        assert manager.get_server_version_info() == sqlite3.sqlite_version_info


@pytest.mark.asyncio
async def test_sqlite_async_manager_version_info(tmp_path: Path) -> None:
    pytest.importorskip("aiosqlite")
    async with AsyncDatabaseManager("sqlite", {"database": str(tmp_path / "a.db")}) as manager:
        assert await manager.get_server_version_info() == sqlite3.sqlite_version_info
