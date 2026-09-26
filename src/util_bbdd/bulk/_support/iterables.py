"""Cierre de los iterables de chunks que produce un lector (``ParallelBulkLoader``, ``dump``)."""

from __future__ import annotations

from collections.abc import Generator, Iterable
from contextlib import contextmanager
from typing import Any


def close_if_closable(iterable: Iterable[Any]) -> None:
    """Llama a ``iterable.close()`` si lo tiene (generadores).

    A1/A2 (audit-code 2026-09-26): un ``for`` no cierra el generador de un lector cuando falla la escritura; su conexión
    de origen (con cursor de servidor y transacción abierta en PostgreSQL) y el hilo de ``_prefetch`` seguían ocupados
    hasta que el recolector los liberaba. Cerrarlo ejecuta los ``finally`` del generador (``join`` del hilo lector).
    """
    close = getattr(iterable, "close", None)
    if callable(close):
        close()


@contextmanager
def closing_iterable[T: Iterable[Any]](iterable: T) -> Generator[T, None, None]:
    """Entrega ``iterable`` y, al salir (también por excepción), lo cierra con :func:`close_if_closable`."""
    try:
        yield iterable
    finally:
        close_if_closable(iterable)


__all__: list[str] = ["close_if_closable", "closing_iterable"]
