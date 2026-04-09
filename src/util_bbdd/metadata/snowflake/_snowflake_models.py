"""Modelos de datos Snowflake para datos complejos de routines y object.

Encapsula estructuras que no caben en tuple plana.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SnowflakeRoutineDetail:
    """Detalle de rutina Snowflake (función UDF o stored procedure).

    Snowflake tiene soporte para:
    - Functions (UDFs) en SQL o JavaScript
    - Stored Procedures (PROCEDURE)
    - External functions (conectan servicios externos)

    Attributes:
        routine_name: Nombre de la rutina
        routine_type: 'FUNCTION' o 'PROCEDURE'
        created_datetime: Fecha de creación (UTC, si aplica)
        language: Lenguaje (SQL, JAVASCRIPT, JAVA, PYTHON, etc.)
    """

    routine_name: str
    routine_type: str
    created_datetime: datetime | None = None
    language: str = "SQL"

    def __repr__(self) -> str:
        dt_str = self.created_datetime.isoformat() if self.created_datetime else "None"
        return f"SnowflakeRoutineDetail({self.routine_name!r}, {self.routine_type!r}, {dt_str}, {self.language!r})"
