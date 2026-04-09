"""Modelos de datos Redshift para datos complejos de routines.

Encapsula estructuras que no caben en tuple plana.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RedshiftRoutineDetail:
    """Detalle de rutina Redshift (función UDF).

    Redshift tiene soporte limitado para procedimientos; principalmente UDFs.
    Redshift no soporta procedimientos almacenados como en PostgreSQL.

    Attributes:
        routine_name: Nombre de la rutina
        routine_type: 'FUNCTION' (principalmente)
        created_datetime: Fecha de creación (UTC, si aplica)
    """

    routine_name: str
    routine_type: str
    created_datetime: datetime | None = None

    def __repr__(self) -> str:
        dt_str = self.created_datetime.isoformat() if self.created_datetime else "None"
        return f"RedshiftRoutineDetail({self.routine_name!r}, {self.routine_type!r}, {dt_str})"
