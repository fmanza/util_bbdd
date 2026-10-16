"""Cierre y recorte de los iterables de chunks que produce un lector (``ParallelBulkLoader``, ``dump``)."""

from __future__ import annotations

from collections.abc import Generator, Iterable, Iterator
from contextlib import contextmanager
from typing import Any

import pandas as pd


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


def skip_rows(chunks: Iterable[pd.DataFrame], rows: int) -> Iterator[pd.DataFrame]:
    """Los chunks de ``chunks`` sin sus primeras ``rows`` filas (reanudación de una partición, B-11).

    Cierra ``chunks`` al terminar, también si quien consume deja de iterar (el lector puede tener una conexión abierta).
    v3.0.0: antes era ``_skip_rows`` en ``parallel_loader.py``.
    """
    try:
        for chunk in chunks:
            if rows >= len(chunk):
                rows -= len(chunk)
                continue
            if rows:
                chunk = chunk.iloc[rows:]
                rows = 0
            yield chunk
    finally:
        close_if_closable(chunks)


__all__: list[str] = ["close_if_closable", "closing_iterable", "skip_rows"]
