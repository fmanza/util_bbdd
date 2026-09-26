"""Sesión compartida por los ejecutores de una ``BulkCrud`` y cadencia de commit (``commit_every_n_chunks``).

R14 (refactor de reutilización 2026-09-26): antes ``BulkCrud`` fijaba y reiniciaba a mano los atributos privados de
``BatchStatementExecutor`` y ``DeleteBatchExecutor`` (conexión activa, gancho de commit, contadores). Ahora los dos
ejecutores comparten un :class:`SessionScope` y cada uno lleva su :class:`CommitCadence`, con la misma semántica:

- El INSERT/UPDATE arrastra su contador de lotes entre llamadas dentro de una sesión y cuenta las filas confirmadas
  (``rows_committed``, BLK-08).
- El DELETE usa una cadencia nueva en cada llamada y sus filas no se cuentan (ver ``BulkCrud.unaudited_committed_rows``).
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommitCadence:
    """Commit cada ``every`` lotes (``None`` = sin cadencia) y filas confirmadas frente a pendientes."""

    every: int | None
    #: Filas confirmadas por commits (periódicos o finales) desde que se creó la cadencia.
    rows_committed: int = 0
    #: Filas ejecutadas desde el último commit.
    rows_pending: int = field(default=0, init=False)
    #: Lotes ejecutados desde el último commit.
    batches: int = field(default=0, init=False)

    def restart(self) -> None:
        """Vuelve a contar lotes desde 0 (inicio de sesión o de una llamada fuera de sesión)."""
        self.batches = 0

    def on_batch(self, rows: int) -> bool:
        """Registra un lote de ``rows`` filas; ``True`` si toca un commit periódico. Sin cadencia no hace nada."""
        if self.every is None:
            return False
        self.rows_pending += rows
        self.batches += 1
        return self.batches >= self.every

    def confirm(self) -> None:
        """Tras un commit: las filas pendientes pasan a confirmadas y el contador de lotes vuelve a 0."""
        self.batches = 0
        self.rows_committed += self.rows_pending
        self.rows_pending = 0

    def discard_pending(self) -> None:
        """Tras un rollback: se descartan las filas pendientes y el contador de lotes vuelve a 0."""
        self.batches = 0
        self.rows_pending = 0


@dataclass
class SessionScope:
    """Conexión de ``BulkCrud.bulk_session()`` y su gancho de commit, compartidos por los ejecutores de la instancia."""

    #: Conexión de la sesión abierta; ``None`` fuera de sesión (cada ejecución abre su propia transacción).
    connection: Any | None = None
    #: Commit periódico dentro de la sesión (``BulkPersistenceManager.commit``: vuelca también la auditoría, M-1).
    commit_hook: Callable[[Any], None] | None = None

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


__all__: list[str] = ["CommitCadence", "SessionScope"]
