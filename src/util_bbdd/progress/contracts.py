"""Contrato de quien recibe los eventos de progreso."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .events import ProgressEvent


@runtime_checkable
class ProgressCallback(Protocol):
    """Receptor de eventos de progreso (``on_progress`` de las operaciones largas).

    Cualquier ``callable`` de un argumento lo cumple (``list.append``, una función, un método).

    Contrato:

    - Se llama en el hilo que hace el trabajo; con operaciones paralelas, desde varios hilos (debe ser seguro).
    - Debe volver rápido: la operación espera a que termine.
    - Si lanza una excepción, la operación la registra en el log una vez, deja de llamarlo y **sigue**: el progreso
      nunca hace fallar una operación. Para parar, usa :class:`~util_bbdd.progress.CancellationToken`.
    """

    def __call__(self, event: ProgressEvent, /) -> None:
        """Recibe un evento.

        Args:
            event: Avance de la operación.
        """
