"""Consumo anticipado de un iterador en un hilo con una cola acotada (solape de preparación o lectura con escritura).

Movido desde ``dump/_source_reader.py`` (Q3 del performance-audit de dump 2026-09-25) para que lo use también ``bulk``
(``BulkCrud(prefetch_blocks=True)``, S-4 de 2026-10-01) sin que ``bulk`` dependa de ``dump``; ``dump`` lo importa de aquí.
"""

from __future__ import annotations

import queue
import threading

from collections.abc import Iterator
from typing import Any

#: Elementos en cola por defecto: el que se consume, uno preparado y uno en preparación.
PREFETCH_DEPTH: int = 2

_DONE = object()


def _enqueue(buffer: queue.Queue[Any], item: Any, stop: threading.Event) -> bool:
    """Intenta encolar ``item`` hasta que se aborta o se vacía el buffer."""
    while not stop.is_set():
        try:
            buffer.put(item, timeout=0.1)
            return True
        except queue.Full:
            continue
    return False


def prefetch[T](items: Iterator[T], depth: int = PREFETCH_DEPTH, *, thread_name: str = "bulk-prefetch") -> Iterator[T]:
    """Consume ``items`` en un hilo con una cola de ``depth`` elementos y los entrega en el mismo orden.

    - Una excepción del productor se relanza en quien consume, tras entregar los elementos anteriores.
    - Si quien consume deja de iterar (fallo al escribir), el ``finally`` avisa al productor y **espera a que termine**.
      Quien consume debe cerrar el generador (``closing_iterable``) para que eso ocurra en ese momento y no en el GC.
    """
    buffer: queue.Queue[Any] = queue.Queue(maxsize=depth)
    stop = threading.Event()
    errors: list[BaseException] = []

    def _producer() -> None:
        try:
            for item in items:
                if not _enqueue(buffer, item, stop):
                    return
        except Exception as exc:  # se relanza en el hilo que consume; no capturamos SystemExit/KeyboardInterrupt
            errors.append(exc)
        finally:
            _enqueue(buffer, _DONE, stop)

    thread = threading.Thread(target=_producer, name=thread_name, daemon=True)
    thread.start()
    try:
        while True:
            item = buffer.get()
            if item is _DONE:
                if errors:
                    raise errors[0]
                return
            yield item
    finally:
        stop.set()
        thread.join()


__all__: list[str] = ["PREFETCH_DEPTH", "prefetch"]
