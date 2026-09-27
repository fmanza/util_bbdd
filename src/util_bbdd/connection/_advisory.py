"""Tipos compartidos del sistema de verificación de condiciones de ejecución por motor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class AdvisoryFinding:
    """Un hallazgo del verificador de condiciones de ejecución de un motor de BD."""

    level: Literal["OK", "INFO", "WARNING", "CRITICAL"]
    param: str
    current: str
    recommendation: str


def fmt_bytes(size_bytes: int) -> str:
    """Convierte bytes a formato legible (GB, MB, KB, B)."""
    for unit, div in (("GB", 1_073_741_824), ("MB", 1_048_576), ("KB", 1024)):
        if size_bytes >= div:
            return f"{size_bytes / div:.1f} {unit}"
    return f"{size_bytes} B"


__all__: list[str] = ["AdvisoryFinding", "fmt_bytes"]
