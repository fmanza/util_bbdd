"""``CatalogSource`` / ``AsyncCatalogSource`` con un dialecto y un ejecutor falsos (sin base de datos)."""

from __future__ import annotations

import asyncio

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from util_bbdd.metadata.contracts import (
    AsyncCatalogExecutor,
    AsyncMetadataSource,
    CatalogDialect,
    CatalogExecutor,
    CatalogQuery,
    MetadataSource,
)
from util_bbdd.metadata.model import ColumnMeta, Kind, KindNotLoadedError, TableMeta
from util_bbdd.metadata.snapshot_cache import SnapshotCache
from util_bbdd.metadata.source import FILTER_MAX_TABLES, AsyncCatalogSource, CatalogSource

TABLES = ["Clientes", "pedidos", "lineas"]


class FakeDialect:
    """Tablas y columnas por schema; COLUMNS filtrable, CHECKS no soportado, ROUTINES sin filtro."""

    name = "fake"
    sqlalchemy_names = frozenset({"fake"})

    def current_schema_sql(self) -> str:
        return "CURRENT"

    def query(self, kind: Kind, *, filtered: bool = False) -> CatalogQuery | None:
        if kind == Kind.CHECKS:
            return None
        if kind == Kind.TABLES:
            return CatalogQuery("TABLES" + (" IN (:tables)" if filtered else ""), filterable=True)
        if kind == Kind.COLUMNS:
            return CatalogQuery("COLUMNS" + (" IN (:tables)" if filtered else ""), filterable=True)
        if kind == Kind.INDEXES:
            return CatalogQuery("INDEXES", filterable=False)
        return CatalogQuery(kind.value.upper())

    def parse(self, kind: Kind, rows: Sequence[Sequence[Any]], schema: str) -> tuple[Any, ...]:
        if kind == Kind.TABLES:
            return tuple(TableMeta(str(r[0])) for r in rows)
        if kind == Kind.COLUMNS:
            return tuple(
                ColumnMeta(table=str(r[0]), name="id", ordinal=1, data_type="int", base_type="int", nullable=False)
                for r in rows
            )
        return ()


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _rows(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        self.calls.append((sql, dict(params)))
        if sql == "CURRENT":
            return [("public",)]
        names = params.get("tables", TABLES)
        return [(t,) for t in names] if sql.startswith(("TABLES", "COLUMNS")) else []

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        return self._rows(sql, params)


class AsyncFakeExecutor(FakeExecutor):
    async def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:  # type: ignore[override]
        await asyncio.sleep(0)
        return self._rows(sql, params)


def _source() -> tuple[CatalogSource, FakeExecutor]:
    executor = FakeExecutor()
    return CatalogSource(FakeDialect(), executor, source_id="fake://db"), executor


def test_protocols_are_satisfied() -> None:
    source, executor = _source()
    assert isinstance(FakeDialect(), CatalogDialect)
    assert isinstance(executor, CatalogExecutor)
    assert isinstance(AsyncFakeExecutor(), AsyncCatalogExecutor)
    assert isinstance(source, MetadataSource)
    assert isinstance(AsyncCatalogSource(FakeDialect(), AsyncFakeExecutor(), source_id="x"), AsyncMetadataSource)


def test_one_query_per_kind_and_cache_hits() -> None:
    source, executor = _source()
    snap = source.snapshot("s", kinds={Kind.TABLES, Kind.COLUMNS})
    assert [c[0] for c in executor.calls] == ["COLUMNS", "TABLES"]
    assert [t.name for t in snap.tables()] == TABLES
    source.snapshot("s", kinds={Kind.TABLES, Kind.COLUMNS})
    assert len(executor.calls) == 2


def test_default_schema_is_asked_once() -> None:
    source, executor = _source()
    source.snapshot(kinds={Kind.TABLES})
    source.snapshot(kinds={Kind.TABLES})
    assert [c[0] for c in executor.calls].count("CURRENT") == 1
    assert source.snapshot(kinds={Kind.TABLES}).schema == "public"


def test_unloaded_kind_is_an_explicit_error() -> None:
    source, _ = _source()
    snap = source.snapshot("s", kinds={Kind.TABLES})
    with pytest.raises(KindNotLoadedError):
        snap.columns("pedidos")


def test_unsupported_kind_is_loaded_empty_without_query() -> None:
    source, executor = _source()
    snap = source.snapshot("s", kinds={Kind.CHECKS})
    assert snap.checks("pedidos") == ()
    assert executor.calls == []


def test_table_lookup_is_case_insensitive_when_unambiguous() -> None:
    source, _ = _source()
    snap = source.snapshot("s", kinds={Kind.COLUMNS})
    assert snap.columns("clientes") == snap.columns("Clientes") != ()
    assert snap.columns("otra") == ()


def test_filtered_read_uses_in_list() -> None:
    source, executor = _source()
    snap = source.snapshot("s", kinds={Kind.COLUMNS}, tables=["pedidos"])
    assert executor.calls == [("COLUMNS IN (:tables)", {"schema": "s", "tables": ["pedidos"]})]
    assert [c.table for c in snap.columns("pedidos")] == ["pedidos"]
    assert snap.tables_filter == frozenset({"pedidos"})


def test_filtered_read_is_served_from_full_cache() -> None:
    source, executor = _source()
    source.snapshot("s", kinds={Kind.COLUMNS})
    snap = source.snapshot("s", kinds={Kind.COLUMNS}, tables=["lineas"])
    assert len(executor.calls) == 1
    assert [c.table for c in snap.data[Kind.COLUMNS]] == ["lineas"]


def test_non_filterable_kind_is_filtered_in_python() -> None:
    source, executor = _source()
    source.snapshot("s", kinds={Kind.INDEXES}, tables=["pedidos"])
    assert executor.calls == [("INDEXES", {"schema": "s"})]


def test_too_many_tables_reads_the_whole_schema() -> None:
    source, executor = _source()
    snap = source.snapshot("s", kinds={Kind.TABLES}, tables=[f"t{i}" for i in range(FILTER_MAX_TABLES + 1)])
    assert executor.calls == [("TABLES", {"schema": "s"})]
    assert snap.tables_filter is None


def test_invalidate_forces_a_new_read() -> None:
    source, executor = _source()
    source.snapshot("s", kinds={Kind.TABLES})
    source.invalidate("s", kinds={Kind.TABLES})
    source.snapshot("s", kinds={Kind.TABLES})
    assert [c[0] for c in executor.calls] == ["TABLES", "TABLES"]


def test_sources_can_share_a_cache_without_mixing_databases() -> None:
    cache = SnapshotCache()
    a = CatalogSource(FakeDialect(), FakeExecutor(), source_id="a", cache=cache)
    b_executor = FakeExecutor()
    b = CatalogSource(FakeDialect(), b_executor, source_id="b", cache=cache)
    a.snapshot("s", kinds={Kind.TABLES})
    b.snapshot("s", kinds={Kind.TABLES})
    assert len(b_executor.calls) == 1


def test_async_source_matches_sync() -> None:
    executor = AsyncFakeExecutor()
    source = AsyncCatalogSource(FakeDialect(), executor, source_id="fake://db")

    async def main() -> Any:
        first = await source.snapshot(kinds={Kind.TABLES, Kind.COLUMNS})
        await source.snapshot(kinds={Kind.TABLES, Kind.COLUMNS}, tables=["pedidos"])
        return first

    snap = asyncio.run(main())
    assert [t.name for t in snap.tables()] == TABLES
    assert [c[0] for c in executor.calls] == ["CURRENT", "COLUMNS", "TABLES"]
