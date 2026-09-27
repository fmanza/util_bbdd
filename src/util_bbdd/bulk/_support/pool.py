"""Capacidad del pool de conexiones de un engine: regla única de ``ParallelBulkLoader`` y ``dump``."""

from __future__ import annotations

from typing import Any


def pool_capacity(engine: Any) -> int | None:
    """Conexiones que el pool de ``engine`` puede entregar a la vez: ``pool_size + max_overflow``.

    Devuelve ``None`` (sin recorte) si no se puede determinar: pool sin ``size()`` (``NullPool``, ``StaticPool``, mocks),
    ``size()`` que no es un entero, o ``max_overflow`` negativo (ilimitado). Un ``max_overflow`` que no sea entero, o que
    falte (es un atributo privado de ``QueuePool``), cuenta como 0.
    """
    pool = getattr(engine, "pool", None)
    size_fn = getattr(pool, "size", None)
    if not callable(size_fn):
        return None
    try:
        size = size_fn()
    except Exception:  # noqa: BLE001 — un pool que no sabe su tamaño: sin recorte
        return None
    if not isinstance(size, int) or isinstance(size, bool):
        return None
    overflow = getattr(pool, "_max_overflow", 0)
    if not isinstance(overflow, int) or isinstance(overflow, bool):
        overflow = 0
    if overflow < 0:
        return None
    return size + overflow


__all__: list[str] = ["pool_capacity"]
