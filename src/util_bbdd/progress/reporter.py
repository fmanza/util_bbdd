"""Ayudante que usan las operaciones largas para emitir progreso y comprobar la cancelación."""

from __future__ import annotations

import logging
import threading

from .cancellation import CancellationToken
from .contracts import ProgressCallback
from .events import ProgressEvent


class ProgressReporter:
    """Une el ``on_progress`` y el ``cancel_token`` opcionales de una operación.

    Sin callback ni token no hace nada, así que las operaciones lo usan siempre sin comprobar ``None``. Aplica el
    contrato de :class:`~util_bbdd.progress.ProgressCallback`: si el callback falla, se registra una vez con
    ``exc_info`` y deja de llamarse; la operación sigue.

    Args:
        operation: Nombre de la operación (``ProgressEvent.operation``).
        on_progress: Receptor de eventos, o ``None``.
        cancel_token: Token de cancelación, o ``None``.
        logger: Logger donde registrar el fallo del callback (por defecto, el de este módulo).

    Example:
        >>> eventos: list[ProgressEvent] = []
        >>> reporter = ProgressReporter("dump", eventos.append)
        >>> reporter.emit("tables", 1, 4, "clientes")
        >>> eventos[0].message
        'clientes'
        >>> reporter.check("tables")  # sin token: no hace nada
    """

    __slots__ = ("_callback", "_lock", "_logger", "cancel_token", "operation")

    def __init__(
        self,
        operation: str,
        on_progress: ProgressCallback | None = None,
        cancel_token: CancellationToken | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.operation = operation
        self.cancel_token = cancel_token
        self._callback = on_progress
        self._logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        """``True`` mientras haya un callback al que llamar."""
        return self._callback is not None

    def emit(self, phase: str, current: int = 0, total: int | None = None, message: str = "") -> None:
        """Envía un :class:`ProgressEvent` al callback, si lo hay.

        Args:
            phase: Fase de la operación.
            current: Unidades terminadas de la fase.
            total: Unidades de la fase, o ``None`` si no se conocen.
            message: Texto breve para mostrar.
        """
        callback = self._callback
        if callback is None:
            return
        try:
            callback(ProgressEvent(self.operation, phase, current, total, message))
        except Exception:
            with self._lock:
                if self._callback is None:
                    return
                self._callback = None
            self._logger.warning(
                f"on_progress de {self.operation} ha fallado; no se le enviarán más eventos", exc_info=True
            )

    def check(self, phase: str = "") -> None:
        """Lanza ``OperationCancelledError`` si el token está cancelado (sin token, no hace nada).

        Args:
            phase: Fase en la que se comprueba (va en la excepción).

        Raises:
            OperationCancelledError: Si se ha pedido la parada.
        """
        if self.cancel_token is not None:
            self.cancel_token.raise_if_cancelled(self.operation, phase)

    def is_cancelled(self) -> bool:
        """``True`` si hay token y está cancelado (para operaciones que limpian antes de lanzar)."""
        return self.cancel_token is not None and self.cancel_token.is_cancelled()
