"""Caché única de lecturas de catálogo por fuente, schema y tipo de objeto (ADR-003).

Clave: ``(fuente, schema, kind, tablas)``; ``tablas`` es ``None`` para el schema completo o el conjunto de tablas de
una lectura filtrada. Las entradas se agrupan por ``(fuente, schema)`` y se descartan por grupos con LRU
(``max_schemas``): un schema enorme no deja crecer la memoria sin límite.

Una sola carga a la vez por clave (*single-flight*): si varios hilos (``bulk``, ``dump``) o tareas ``asyncio`` piden lo
mismo, uno consulta el catálogo y el resto espera su resultado. Los valores son tuplas inmutables y se comparten.

Una invalidación cambia la *época* de la fuente: lo que cargaba una lectura empezada antes se devuelve a quien lo pidió
pero no se guarda (leyó el catálogo anterior al DDL que motivó la invalidación).
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

    Examples:
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
        #: Época por fuente (y global para ``clear``): sube con cada invalidación
        self._epochs: dict[str, int] = {}
        self._clears = 0
        self.hits = 0
        self.misses = 0

    # ── lectura y escritura ──────────────────────────────────────────────────
    def get(self, key: CacheKey) -> Value | None:
        """Valor de ``key`` (lo marca como recién usado) o ``None`` si no está; cuenta el acierto."""
        with self._lock:
            group = self._groups.get((key[0], key[1]))
            if group is None or key not in group:
                return None
            self._groups.move_to_end((key[0], key[1]))
            self.hits += 1
            return group[key]

    def put(self, key: CacheKey, value: Value) -> None:
        """Guarda ``value``; si se supera ``max_schemas``, descarta el schema menos usado."""
        with self._lock:
            group_key = (key[0], key[1])
            self._groups.setdefault(group_key, {})[key] = value
            self._groups.move_to_end(group_key)
            while len(self._groups) > self.max_schemas:
                self._groups.popitem(last=False)

    def _epoch(self, source: str) -> tuple[int, int]:
        return self._clears, self._epochs.get(source, 0)

    def _start_load(self, key: CacheKey) -> tuple[int, int]:
        """Cuenta el fallo y devuelve la época en que empieza la carga (bajo ``_lock``)."""
        with self._lock:
            self.misses += 1
            return self._epoch(key[0])

    def _finish_load(self, key: CacheKey, value: Value, epoch: tuple[int, int], locks: dict[CacheKey, Any]) -> None:
        """Guarda ``value`` si nadie invalidó la fuente durante la carga y libera el lock de la clave."""
        with self._lock:
            if self._epoch(key[0]) == epoch:
                self.put(key, value)
            locks.pop(key, None)  # quien ya lo tenga lo sigue usando; los siguientes leen la caché o crean otro

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
            epoch = self._start_load(key)
            try:
                value = loader()
            except BaseException:
                with self._lock:
                    self._key_locks.pop(key, None)
                raise
            self._finish_load(key, value, epoch, self._key_locks)
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
            epoch = self._start_load(key)
            try:
                value = await loader()
            except BaseException:
                with self._lock:
                    self._async_key_locks.pop(key, None)
                raise
            self._finish_load(key, value, epoch, self._async_key_locks)
            return value

    # ── invalidación ─────────────────────────────────────────────────────────
    def invalidate(self, source: str, schema: str | None = None, kinds: Collection[Kind] | None = None) -> int:
        """Descarta lecturas de ``source`` (todas, de un schema o de unos tipos de objeto). Devuelve cuántas."""
        removed = 0
        kind_set = frozenset(kinds) if kinds is not None else None
        with self._lock:
            self._epochs[source] = self._epochs.get(source, 0) + 1
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
        """Vacía la caché; las cargas en curso no guardan su resultado."""
        with self._lock:
            self._groups.clear()
            self._clears += 1

    def stats(self) -> dict[str, int]:
        """Contadores: ``schemas`` y ``entries`` en memoria, ``hits`` y ``misses`` acumulados."""
        with self._lock:
            return {
                "schemas": len(self._groups),
                "entries": sum(len(g) for g in self._groups.values()),
                "hits": self.hits,
                "misses": self.misses,
            }


__all__: list[str] = ["CacheKey", "SnapshotCache"]
