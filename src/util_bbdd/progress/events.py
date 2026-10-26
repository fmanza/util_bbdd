"""Evento de progreso común a todas las operaciones largas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """Avance de una operación larga en un momento dado.

    Las operaciones emiten uno al empezar cada fase y uno por unidad de trabajo terminada (tabla, formato, lote,
    sentencia). ``current`` y ``total`` cuentan unidades de la fase, no de la operación entera; si la fase no sabe
    cuántas tiene, ``total`` es ``None``.

    Attributes:
        operation: Operación que avanza: ``"documentation"``, ``"graph"``, ``"compare"``, ``"migrate"``, ``"dump"`` o
            ``"bulk"``.
        phase: Fase dentro de la operación (p. ej. ``"metadata"``, ``"word"``, ``"tables"``).
        current: Unidades terminadas de la fase (``0`` al empezarla).
        total: Unidades de la fase, o ``None`` si no se conocen.
        message: Texto breve para mostrar (p. ej. el nombre de la tabla). Nunca lleva datos de conexión ni secretos.

    Example:
        >>> evento = ProgressEvent("dump", "tables", current=3, total=12, message="clientes")
        >>> evento.fraction
        0.25
    """

    operation: str
    phase: str
    current: int = 0
    total: int | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if self.current < 0:
            raise ValueError(f"current no puede ser negativo: {self.current}")
        if self.total is not None and self.total < 0:
            raise ValueError(f"total no puede ser negativo: {self.total}")

    @property
    def fraction(self) -> float | None:
        """Parte terminada de la fase, entre 0 y 1; ``None`` sin ``total`` y ``1.0`` con ``total == 0``."""
        if self.total is None:
            return None
        if self.total == 0:
            return 1.0
        return min(self.current / self.total, 1.0)
