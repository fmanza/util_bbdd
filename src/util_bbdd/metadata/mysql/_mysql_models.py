"""Modelos de datos MySQL para datos complejos de routines.

Encapsula estructuras que no caben en tuple plana.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MysqlRoutineDetail:
    """Detalle de rutina MySQL (PROCEDURE o FUNCTION).

    Attributes:
        routine_name: Nombre de la rutina
        routine_type: 'PROCEDURE' o 'FUNCTION'
        created_datetime: Fecha de creación (UTC)
    """

    routine_name: str
    routine_type: str
    created_datetime: datetime | None = None

    def __repr__(self) -> str:
        dt_str = self.created_datetime.isoformat() if self.created_datetime else "None"
        return f"MysqlRoutineDetail({self.routine_name!r}, {self.routine_type!r}, {dt_str})"
