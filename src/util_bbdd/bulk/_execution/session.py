"""Sesión compartida por los ejecutores de una ``BulkCrud`` y cadencia de commit (``commit_every_n_chunks``).

R14 (refactor de reutilización 2026-09-26): antes ``BulkCrud`` fijaba y reiniciaba a mano los atributos privados de
``BatchStatementExecutor`` y ``DeleteBatchExecutor`` (conexión activa, gancho de commit, contadores). Ahora los dos
ejecutores comparten un :class:`SessionScope` y cada uno lleva su :class:`CommitCadence`:

- El contador de lotes es de cada ejecutor. El del INSERT/UPDATE se arrastra entre llamadas dentro de una sesión; el
  del DELETE empieza en cada llamada.
- Las filas pendientes y confirmadas (:class:`RowLedger`) son de la sesión: un commit confirma la transacción entera,
  lo haga el ejecutor que lo haga (2a, 2026-09-27: el commit periódico del DELETE confirmaba filas de INSERT que no se
  contaban). Desde v0.18.0 las filas del DELETE también se cuentan (ver ``BulkCrud.rows_committed``).
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RowLedger:
    """Filas ejecutadas pendientes de commit y filas ya confirmadas (BLK-08)."""

    #: Filas confirmadas por commits desde que se creó el libro.
    committed: int = 0
    #: Filas ejecutadas desde el último commit.
    pending: int = 0

    def confirm(self) -> None:
        """Tras un commit: las filas pendientes pasan a confirmadas."""
        self.committed += self.pending
        self.pending = 0

    def discard(self) -> None:
        """Tras un rollback: se descartan las filas pendientes."""
        self.pending = 0


@dataclass
class CommitCadence:
    """Commit cada ``every`` lotes (``None`` = sin cadencia); las filas se anotan en ``ledger``.

    Args:
        every: Lotes entre commits periódicos, o ``None``.
        ledger: Libro de filas; por defecto uno propio. Los ejecutores de una ``BulkCrud`` usan el de su sesión.
        count_rows: Si ``False``, los lotes cuentan para la cadencia pero sus filas no se anotan.
    """

    every: int | None
    ledger: RowLedger = field(default_factory=RowLedger)
    count_rows: bool = True
    #: Lotes ejecutados desde el último commit.
    batches: int = field(default=0, init=False)

    @property
    def rows_committed(self) -> int:
        """Filas confirmadas del libro."""
        return self.ledger.committed

    @property
    def rows_pending(self) -> int:
        """Filas pendientes del libro."""
        return self.ledger.pending

    def restart(self) -> None:
        """Vuelve a contar lotes desde 0 (inicio de sesión o de una llamada fuera de sesión)."""
        self.batches = 0

    def on_batch(self, rows: int) -> bool:
        """Registra un lote de ``rows`` filas; ``True`` si toca un commit periódico. Sin cadencia no hace nada."""
        if self.every is None:
            return False
        if self.count_rows:
            self.ledger.pending += rows
        self.batches += 1
        return self.batches >= self.every

    def confirm(self) -> None:
        """Tras un commit: el contador de lotes vuelve a 0 y las filas pendientes del libro pasan a confirmadas."""
        self.batches = 0
        self.ledger.confirm()

    def discard_pending(self) -> None:
        """Tras un rollback: el contador de lotes vuelve a 0 y se descartan las filas pendientes del libro."""
        self.batches = 0
        self.ledger.discard()


@dataclass
class SessionScope:
    """Conexión de ``BulkCrud.bulk_session()``, su gancho de commit y el libro de filas, compartidos por los ejecutores."""

    #: Conexión de la sesión abierta; ``None`` fuera de sesión (cada ejecución abre su propia transacción).
    connection: Any | None = None
    #: Commit periódico dentro de la sesión (``BulkPersistenceManager.commit``: vuelca también la auditoría, M-1).
    commit_hook: Callable[[Any], None] | None = None
    #: Filas pendientes y confirmadas de todos los ejecutores que comparten la sesión.
    rows: RowLedger = field(default_factory=RowLedger)

    @property
    def active(self) -> bool:
        """``True`` si hay una sesión abierta."""
        return self.connection is not None

    @contextmanager
    def bind(self, connection: Any, commit_hook: Callable[[Any], None] | None = None) -> Generator[Any, None, None]:
        """Publica ``connection`` (y ``commit_hook``) para los ejecutores mientras dura el bloque, también si falla."""
        self.connection, self.commit_hook = connection, commit_hook
        try:
            yield connection
        finally:
            self.connection = self.commit_hook = None


__all__: list[str] = ["CommitCadence", "RowLedger", "SessionScope"]
