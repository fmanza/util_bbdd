"""Caché única de lecturas de catálogo por fuente, schema y tipo de objeto (ADR-003).

Clave: ``(fuente, schema, kind, tablas)``; ``tablas`` es ``None`` para el schema completo o el conjunto de tablas de
una lectura filtrada. Las entradas se agrupan por ``(fuente, schema)`` y se descartan por grupos con LRU
(``max_schemas``): un schema enorme no deja crecer la memoria sin límite.

Una sola carga a la vez por clave (*single-flight*): si varios hilos (``bulk``, ``dump``) o tareas ``asyncio`` piden lo
mismo, uno consulta el catálogo y el resto espera su resultado. Los valores son tuplas inmutables y se comparten.
"""

from __future__ import annotations

import asyncio
import threading

from collections import OrderedDict
from collections.abc import Awaitable, Callable, Collection
from typing import Any

from .model import Kind

CacheKey = tuple[str, str, Kind, frozenset[str] | None]
Value = tuple[Any, ...]


class SnapshotCache:
    """Caché LRU por schema con carga única por clave, válida en hilos y en ``asyncio``.

    Args:
        max_schemas: Nº máximo de pares ``(fuente, schema)`` en memoria; al superarlo se descarta el menos usado.

    Example:
        >>> cache = SnapshotCache(max_schemas=4)
        >>> cache.get_or_load(("pg", "ventas", Kind.TABLES, None), lambda: (TableMeta("t"),))
        (TableMeta(name='t', comment=None, collation=None),)
    """

    def __init__(self, max_schemas: int = 8) -> None:
        if max_schemas < 1:
            raise ValueError("max_schemas debe ser >= 1")
        self.max_schemas = max_schemas
        self._groups: OrderedDict[tuple[str, str], dict[CacheKey, Value]] = OrderedDict()
        self._lock = threading.RLock()
        self._key_locks: dict[CacheKey, threading.Lock] = {}
        self._async_key_locks: dict[CacheKey, asyncio.Lock] = {}
        self.hits = 0
        self.misses = 0

    # ── lectura y escritura ──────────────────────────────────────────────────
    def get(self, key: CacheKey) -> Value | None:
        with self._lock:
            group = self._groups.get((key[0], key[1]))
            if group is None or key not in group:
                return None
            self._groups.move_to_end((key[0], key[1]))
            self.hits += 1
            return group[key]

    def put(self, key: CacheKey, value: Value) -> None:
        with self._lock:
            group_key = (key[0], key[1])
            self._groups.setdefault(group_key, {})[key] = value
            self._groups.move_to_end(group_key)
            while len(self._groups) > self.max_schemas:
                self._groups.popitem(last=False)

    def get_or_load(self, key: CacheKey, loader: Callable[[], Value]) -> Value:
        """Valor de ``key``; si no está, lo carga una sola vez aunque lo pidan varios hilos a la vez."""
        cached = self.get(key)
        if cached is not None:
            return cached
        with self._lock:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:
            cached = self.get(key)
            if cached is not None:
                return cached
            with self._lock:
                self.misses += 1
            value = loader()
            self.put(key, value)
            return value

    async def aget_or_load(self, key: CacheKey, loader: Callable[[], Awaitable[Value]]) -> Value:
        """Variante async de :meth:`get_or_load` (una sola carga por clave entre tareas)."""
        cached = self.get(key)
        if cached is not None:
            return cached
        with self._lock:
            key_lock = self._async_key_locks.setdefault(key, asyncio.Lock())
        async with key_lock:
            cached = self.get(key)
            if cached is not None:
                return cached
            with self._lock:
                self.misses += 1
            value = await loader()
            self.put(key, value)
            return value

    # ── invalidación ─────────────────────────────────────────────────────────
    def invalidate(self, source: str, schema: str | None = None, kinds: Collection[Kind] | None = None) -> int:
        """Descarta lecturas de ``source`` (todas, de un schema o de unos tipos de objeto). Devuelve cuántas."""
        removed = 0
        kind_set = frozenset(kinds) if kinds is not None else None
        with self._lock:
            for group_key in [g for g in self._groups if g[0] == source and (schema is None or g[1] == schema)]:
                group = self._groups[group_key]
                if kind_set is None:
                    removed += len(group)
                    del self._groups[group_key]
                    continue
                for key in [k for k in group if k[2] in kind_set]:
                    del group[key]
                    removed += 1
                if not group:
                    del self._groups[group_key]
        return removed

    def clear(self) -> None:
        with self._lock:
            self._groups.clear()

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "schemas": len(self._groups),
                "entries": sum(len(g) for g in self._groups.values()),
                "hits": self.hits,
                "misses": self.misses,
            }


__all__: list[str] = ["CacheKey", "SnapshotCache"]
