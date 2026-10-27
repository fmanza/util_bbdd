"""Progreso por lotes y cancelación cooperativa de una operación de ``BulkCrud`` (v4.5.0, G1 de util_bbdd_web).

Los ejecutores (``BatchStatementExecutor`` y ``DeleteBatchExecutor``) son el único punto por el que pasan los lotes de
INSERT, UPDATE y DELETE: comprueban la cancelación antes de enviar cada lote y anotan sus filas al terminarlo. Una carga
paralela comparte un :class:`BatchProgress` entre las ``BulkCrud`` de sus particiones, así que ``current`` suma las filas
de todos los hilos.
"""

from __future__ import annotations

import threading

from ...progress import ProgressReporter

#: Fase de los eventos de ``bulk``: una unidad es una fila enviada en un lote ya ejecutado.
ROWS_PHASE: str = "rows"


class BatchProgress:
    """Filas enviadas de una operación de ``BulkCrud`` y su ``ProgressReporter`` (seguro entre hilos).

    Args:
        reporter: Une ``on_progress`` y ``cancel_token`` (operación ``"bulk"``).
        table: Tabla destino (``ProgressEvent.message``).
        total: Filas de la operación (``len(df)``), o ``None`` si no se conocen (vías ``*_from_chunks``).
    """

    __slots__ = ("_lock", "_sent", "reporter", "table", "total")

    def __init__(self, reporter: ProgressReporter, table: str, total: int | None) -> None:
        self.reporter = reporter
        self.table = table
        self.total = total
        self._sent = 0
        self._lock = threading.Lock()

    def start(self) -> None:
        """Comprueba la cancelación y emite el evento inicial (``current=0``)."""
        self.check()
        self.reporter.emit(ROWS_PHASE, 0, self.total, self.table)

    def check(self) -> None:
        """``OperationCancelledError`` si se pidió la parada (punto seguro: antes de enviar un lote)."""
        self.reporter.check(ROWS_PHASE)

    def batch_done(self, rows: int) -> None:
        """Anota un lote ejecutado de ``rows`` filas y emite el acumulado (en orden también con varios hilos)."""
        with self._lock:
            self._sent += rows
            self.reporter.emit(ROWS_PHASE, self._sent, self.total, self.table)

    @property
    def sent(self) -> int:
        """Filas de los lotes ejecutados hasta ahora (confirmados o no)."""
        return self._sent


__all__: list[str] = ["ROWS_PHASE", "BatchProgress"]
