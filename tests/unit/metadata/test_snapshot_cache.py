"""``SnapshotCache``: LRU por schema, invalidación y una sola carga por clave (hilos y asyncio)."""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from util_bbdd.metadata.model import Kind, TableMeta
from util_bbdd.metadata.snapshot_cache import SnapshotCache


def _key(schema: str, kind: Kind = Kind.TABLES, source: str = "pg") -> tuple:
    return (source, schema, kind, None)


def test_get_or_load_caches_the_value() -> None:
    cache = SnapshotCache()
    calls: list[int] = []
    value = (TableMeta("t"),)
    assert cache.get_or_load(_key("s"), lambda: calls.append(1) or value) is value
    assert cache.get_or_load(_key("s"), lambda: calls.append(1) or value) is value
    assert calls == [1]
    assert cache.stats() == {"schemas": 1, "entries": 1, "hits": 1, "misses": 1}


def test_lru_evicts_whole_schemas() -> None:
    cache = SnapshotCache(max_schemas=2)
    cache.put(_key("a"), ())
    cache.put(_key("a", Kind.COLUMNS), ())
    cache.put(_key("b"), ())
    cache.get(_key("a"))  # «a» pasa a ser el más reciente
    cache.put(_key("c"), ())
    assert cache.get(_key("b")) is None
    assert cache.get(_key("a", Kind.COLUMNS)) == ()
    assert cache.get(_key("c")) == ()


def test_invalidate_by_schema_and_kind() -> None:
    cache = SnapshotCache()
    for schema in ("a", "b"):
        for kind in (Kind.TABLES, Kind.COLUMNS):
            cache.put(_key(schema, kind), ())
    cache.put(_key("a", source="other"), ())
    assert cache.invalidate("pg", "a", [Kind.COLUMNS]) == 1
    assert cache.get(_key("a", Kind.COLUMNS)) is None
    assert cache.get(_key("a")) == ()
    assert cache.invalidate("pg") == 3
    assert cache.get(_key("a", source="other")) == ()


def test_single_flight_across_threads() -> None:
    cache = SnapshotCache()
    calls: list[int] = []
    barrier = threading.Barrier(8)

    def loader() -> tuple:
        calls.append(1)
        time.sleep(0.05)
        return (TableMeta("t"),)

    results: list[tuple] = []

    def worker() -> None:
        barrier.wait()
        results.append(cache.get_or_load(_key("s"), loader))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls == [1]
    assert len(results) == 8 and all(r is results[0] for r in results)


def test_single_flight_across_tasks() -> None:
    cache = SnapshotCache()
    calls: list[int] = []

    async def loader() -> tuple:
        calls.append(1)
        await asyncio.sleep(0.02)
        return (TableMeta("t"),)

    async def main() -> list[tuple]:
        return await asyncio.gather(*(cache.aget_or_load(_key("s"), loader) for _ in range(8)))

    results = asyncio.run(main())
    assert calls == [1]
    assert all(r is results[0] for r in results)


def test_load_started_before_an_invalidation_is_not_cached() -> None:
    """Una lectura del catálogo anterior al DDL que motivó la invalidación no debe quedar en la caché (F1)."""
    cache = SnapshotCache()
    loading, invalidated = threading.Event(), threading.Event()

    def slow_loader() -> tuple:
        loading.set()
        invalidated.wait(5)
        return (TableMeta("antes_del_ddl"),)

    result: list[tuple] = []
    worker = threading.Thread(target=lambda: result.append(cache.get_or_load(_key("s"), slow_loader)))
    worker.start()
    loading.wait(5)
    cache.invalidate("pg", "s")
    invalidated.set()
    worker.join()

    assert result == [(TableMeta("antes_del_ddl"),)]  # quien la pidió la recibe…
    assert cache.get(_key("s")) is None  # …pero no se guarda
    assert cache.get_or_load(_key("s"), lambda: (TableMeta("despues"),)) == (TableMeta("despues"),)


def test_task_load_started_before_clear_is_not_cached() -> None:
    cache = SnapshotCache()

    async def main() -> None:
        started = asyncio.Event()

        async def loader() -> tuple:
            started.set()
            await asyncio.sleep(0.02)
            return (TableMeta("antes"),)

        task = asyncio.create_task(cache.aget_or_load(_key("s"), loader))
        await started.wait()
        cache.clear()
        assert await task == (TableMeta("antes"),)

    asyncio.run(main())
    assert cache.get(_key("s")) is None


def test_key_locks_are_released_after_loading() -> None:
    """Sin esto, cada lectura filtrada distinta dejaba su lock para siempre (F6)."""
    cache = SnapshotCache()
    for i in range(20):
        cache.get_or_load(("pg", "s", Kind.COLUMNS, frozenset({f"t{i}"})), lambda: ())
    with pytest.raises(RuntimeError):
        cache.get_or_load(_key("s"), _fail)
    asyncio.run(cache.aget_or_load(_key("a"), _async_empty))
    assert cache._key_locks == {} and cache._async_key_locks == {}  # noqa: SLF001


def _fail() -> tuple:
    raise RuntimeError("catálogo caído")


async def _async_empty() -> tuple:
    return ()


def test_max_schemas_must_be_positive() -> None:
    with pytest.raises(ValueError):
        SnapshotCache(max_schemas=0)
