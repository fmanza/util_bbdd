"""Tipos compartidos del sistema de verificación de condiciones de ejecución por motor."""

from __future__ import annotations

import logging
import threading

from collections.abc import Hashable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

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


@dataclass(frozen=True, slots=True)
class EngineReadinessReport:
    """Resultado de :meth:`EngineReadinessAdvisor.assess`: los hallazgos y en qué condiciones se obtuvieron.

    Distingue «sin hallazgos» de «no auditado»: un motor sin checks tiene ``supported=False`` y una verificación sin
    conexión, ``dynamic=False`` con el motivo en ``error``.

    Attributes:
        db_type: Motor verificado, tal como se pidió.
        findings: Hallazgos ordenados por severidad descendente.
        checked_at: Momento de la verificación (UTC, con zona horaria).
        dynamic: True si hubo conexión y se intentaron los checks dinámicos (variables del servidor).
        supported: False si el motor no tiene checks (``findings`` vacío).
        error: Por qué no hubo checks dinámicos; solo el tipo de la excepción, nunca su mensaje (puede llevar la URL).

    Example:
        >>> report = EngineReadinessAdvisor().assess("postgresql", {"pool_size": 2})
        >>> report.dynamic, report.supported
        (False, True)
    """

    db_type: str
    findings: tuple[AdvisoryFinding, ...]
    checked_at: datetime
    dynamic: bool
    supported: bool
    error: str | None = None


class ReadinessValidator(Protocol):
    """Checks de un motor para ``EngineReadinessAdvisor`` (Strategy; T-06, 2026-10-16).

    Lo cumplen ``PostgreSQLVariableValidator``, ``SQLServerVariableValidator``, ``OracleVariableValidator``,
    ``SQLiteVariableValidator`` y el interno ``MySQLReadinessValidator``. El advisor crea una instancia por verificación,
    llama a :meth:`check_static` y, con conexión, a :meth:`check_dynamic`.
    """

    def check_static(self, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Hallazgos a partir de ``conn_params`` (sin conexión)."""
        ...

    def check_dynamic(self, connection: Any, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Hallazgos a partir de los parámetros del servidor leídos con ``connection``."""
        ...


def fmt_bytes(size_bytes: int) -> str:
    """Convierte bytes a formato legible (GB, MB, KB, B)."""
    for unit, div in (("GB", 1_073_741_824), ("MB", 1_048_576), ("KB", 1024)):
        if size_bytes >= div:
            return f"{size_bytes / div:.1f} {unit}"
    return f"{size_bytes} B"


__all__: list[str] = [
    "AdvisoryFinding",
    "EngineReadinessReport",
    "ReadinessValidator",
    "fmt_bytes",
    "reset_warned",
    "warn_once",
]
