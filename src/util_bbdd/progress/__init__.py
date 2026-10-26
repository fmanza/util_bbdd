"""Módulo progress: contrato común de progreso y cancelación cooperativa de las operaciones largas.

Capa 2 (Regla #6): solo importa de ``_core``. Lo usan ``doc``, ``analysis``, ``comparar``, ``migrate``, ``dump`` y
``bulk`` para avisar de su avance (``on_progress``) y para parar entre unidades de trabajo (``cancel_token``).

- events.py - ``ProgressEvent``: qué operación, en qué fase y cuánto lleva
- contracts.py - ``ProgressCallback``: quién recibe los eventos
- cancellation.py - ``CancellationToken``: petición de parada, segura entre hilos
- reporter.py - ``ProgressReporter``: lo que usan las operaciones por dentro (emitir y comprobar la cancelación)

Example:
    >>> from util_bbdd.progress import CancellationToken, ProgressEvent
    >>> eventos: list[ProgressEvent] = []
    >>> token = CancellationToken()
    >>> # DatabaseDocumentation(..., on_progress=eventos.append, cancel_token=token).generate()
    >>> token.cancel()  # desde otro hilo: la operación para en la siguiente unidad de trabajo
    >>> token.is_cancelled()
    True
"""

from .cancellation import CancellationToken
from .contracts import ProgressCallback
from .events import ProgressEvent
from .reporter import ProgressReporter

__all__: list[str] = [
    "CancellationToken",
    "ProgressCallback",
    "ProgressEvent",
    "ProgressReporter",
]
