"""Progreso y cancelación por tabla de los renderers de la documentación (util_bbdd_web G1, 4.1.0)."""

from __future__ import annotations

from typing import Any

from .....progress import ProgressReporter


class TableProgress:
    """Avance de un formato tabla a tabla: comprueba la cancelación antes de cada una y emite al terminarla.

    El ``ProgressReporter`` viaja en la sesión de la documentación (``data_provider.progress``); si el
    ``data_provider`` no lo trae (un renderer usado directamente, dobles de test), no hace nada.

    Example:
        >>> progress = TableProgress.of(data_provider, "word", total=len(tables))
        >>> for row in tables:
        ...     progress.before(row[0])
        ...     ...  # documentar la tabla
        ...     progress.done(row[0])
    """

    __slots__ = ("_current", "_phase", "_reporter", "_total")

    def __init__(self, reporter: ProgressReporter | None, phase: str, total: int) -> None:
        self._reporter = reporter
        self._phase = phase
        self._total = total
        self._current = 0

    @classmethod
    def of(cls, data_provider: Any, phase: str, total: int) -> TableProgress:
        """El progreso del formato ``phase`` sobre ``total`` tablas, con el reporter de ``data_provider`` si lo hay."""
        reporter: Any = getattr(data_provider, "progress", None)
        return cls(reporter if isinstance(reporter, ProgressReporter) else None, phase, total)

    def before(self, table_name: str) -> None:
        """Antes de documentar una tabla: lanza ``OperationCancelledError`` si se pidió la parada."""
        if self._reporter is not None:
            self._reporter.check(self._phase)

    def done(self, table_name: str) -> None:
        """Después de documentar una tabla: emite el avance del formato."""
        self._current += 1
        if self._reporter is not None:
            self._reporter.emit(self._phase, self._current, self._total, table_name)
