"""Tipos compartidos del sistema de verificación de condiciones de ejecución por motor."""

from __future__ import annotations

import logging
import threading

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Literal

#: Avisos ya emitidos por ``warn_once`` (estado de proceso, como ``EngineReadinessAdvisor.report_once``): la misma
#: configuración se repite en cada conexión de un pool o de un Engine y el aviso solo aporta la primera vez.
_WARNED: set[Hashable] = set()
_WARNED_LOCK = threading.Lock()


def warn_once(logger: logging.Logger, key: Hashable, message: str) -> None:
    """Emite ``message`` como WARNING la primera vez que aparece ``key`` en el proceso."""
    with _WARNED_LOCK:
        if key in _WARNED:
            return
        _WARNED.add(key)
    logger.warning(message)


def reset_warned() -> None:
    """Olvida los avisos emitidos (tests)."""
    with _WARNED_LOCK:
        _WARNED.clear()


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


__all__: list[str] = ["AdvisoryFinding", "fmt_bytes", "reset_warned", "warn_once"]
