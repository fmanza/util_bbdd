"""Petición de cancelación cooperativa, segura entre hilos."""

from __future__ import annotations

import threading

from .._core.exceptions import OperationCancelledError


class CancellationToken:
    """Petición de parada que una operación larga comprueba entre unidades de trabajo.

    La cancelación es **cooperativa**: ``cancel()`` no interrumpe nada; la operación lo comprueba en sus puntos seguros
    (entre tablas, formatos, lotes o sentencias), deja el destino en un estado coherente (por ejemplo, restaura las
    constraints que desactivó) y lanza :class:`~util_bbdd.exceptions.OperationCancelledError`.

    Un token cancelado sigue cancelado: para otra operación, crea otro.

    Example:
        >>> token = CancellationToken()
        >>> token.is_cancelled()
        False
        >>> token.cancel()
        >>> token.is_cancelled()
        True
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Pide la parada (idempotente; se puede llamar desde cualquier hilo)."""
        self._event.set()

    def is_cancelled(self) -> bool:
        """``True`` si alguien ha llamado a :meth:`cancel`."""
        return self._event.is_set()

    def raise_if_cancelled(self, operation: str, phase: str = "") -> None:
        """Lanza :class:`~util_bbdd.exceptions.OperationCancelledError` si se ha pedido la parada.

        Args:
            operation: Operación que comprueba (va en la excepción).
            phase: Fase en la que se detecta la cancelación (va en la excepción).

        Raises:
            OperationCancelledError: Si el token está cancelado.
        """
        if self._event.is_set():
            raise OperationCancelledError(
                f"Operación cancelada: {operation}", phase=phase, cancelled_operation=operation
            )

    def __repr__(self) -> str:
        return f"CancellationToken(cancelled={self.is_cancelled()})"
