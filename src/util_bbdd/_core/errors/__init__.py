"""Registro centralizado de códigos de error de motor y políticas de retry.

Refactor de v0.30.1: documentación y futura centralización de manejo de errores motor-específicos.

Esta es una estructura de documentación sin lógica ejecutable; los códigos se usan en:
- ``bulk/_execution/``: Detecta errores y decide retry/isolate/raise
- ``connection/``: Normalizadores de error por motor
- ``migrate/``: Validación de pasos de migración
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__: list[str] = ["ErrorCodeRegistry", "MotorErrorCodeEntry"]


@dataclass(frozen=True)
class MotorErrorCodeEntry:
    """Entrada de código de error de motor.

    Attributes:
        code: Código numérico o string de error (ej. 1205 para MySQL, 40001 para PostgreSQL).
        motor: Motor de base de datos (mysql, mariadb, postgresql, oracle, sqlserver, sqlite, hsqldb).
        description: Descripción del error.
        retry_policy: Política de reintentos (retry_once, no_retry, connection_reset).
        severity: Severidad (transient, permanent, unknown).
        category: Categoría (lock, constraint, data_type, syntax, permission, other).
    """

    code: str | int
    motor: Literal["mysql", "mariadb", "postgresql", "oracle", "sqlserver", "sqlite", "hsqldb"]
    description: str
    retry_policy: Literal["retry_once", "no_retry", "connection_reset"]
    severity: Literal["transient", "permanent", "unknown"]
    category: Literal["lock", "constraint", "data_type", "syntax", "permission", "other"]


# Registro de códigos de error conocidos por motor
# Esta es una base de datos de referencia para documentación y futuras optimizaciones.
# La lógica de manejo de errores actual está en bulk/_execution/ y connection/<motor>/.
# En v0.31.0+, los manejadores de error consultarán este registro centralizado.

_ERROR_CODE_REGISTRY: dict[str, dict[str | int, MotorErrorCodeEntry]] = {
    "mysql": {
        1205: MotorErrorCodeEntry(
            code=1205,
            motor="mysql",
            description="Lock wait timeout exceeded; try restarting transaction",
            retry_policy="retry_once",
            severity="transient",
            category="lock",
        ),
        1206: MotorErrorCodeEntry(
            code=1206,
            motor="mysql",
            description="The total number of locks exceeds the lock table size",
            retry_policy="no_retry",
            severity="permanent",
            category="other",
        ),
        1451: MotorErrorCodeEntry(
            code=1451,
            motor="mysql",
            description="Cannot delete or update a parent row: a foreign key constraint fails",
            retry_policy="no_retry",
            severity="permanent",
            category="constraint",
        ),
        1452: MotorErrorCodeEntry(
            code=1452,
            motor="mysql",
            description="Cannot add or update a child row: a foreign key constraint fails",
            retry_policy="no_retry",
            severity="permanent",
            category="constraint",
        ),
    },
    "postgresql": {
        "40001": MotorErrorCodeEntry(
            code="40001",
            motor="postgresql",
            description="Serialization failure / Conflict with concurrent update",
            retry_policy="retry_once",
            severity="transient",
            category="lock",
        ),
        "40P01": MotorErrorCodeEntry(
            code="40P01",
            motor="postgresql",
            description="Deadlock detected",
            retry_policy="retry_once",
            severity="transient",
            category="lock",
        ),
        "23505": MotorErrorCodeEntry(
            code="23505",
            motor="postgresql",
            description="Unique violation",
            retry_policy="no_retry",
            severity="permanent",
            category="constraint",
        ),
        "23503": MotorErrorCodeEntry(
            code="23503",
            motor="postgresql",
            description="Foreign key violation",
            retry_policy="no_retry",
            severity="permanent",
            category="constraint",
        ),
    },
    "oracle": {
        "ORA-00001": MotorErrorCodeEntry(
            code="ORA-00001",
            motor="oracle",
            description="Unique constraint violated",
            retry_policy="no_retry",
            severity="permanent",
            category="constraint",
        ),
        "ORA-02292": MotorErrorCodeEntry(
            code="ORA-02292",
            motor="oracle",
            description="Integrity constraint violated - child record found",
            retry_policy="no_retry",
            severity="permanent",
            category="constraint",
        ),
        "ORA-04020": MotorErrorCodeEntry(
            code="ORA-04020",
            motor="oracle",
            description="Deadlock detected while waiting for resource",
            retry_policy="retry_once",
            severity="transient",
            category="lock",
        ),
    },
    "sqlserver": {
        1205: MotorErrorCodeEntry(
            code=1205,
            motor="sqlserver",
            description="Deadlock victim",
            retry_policy="retry_once",
            severity="transient",
            category="lock",
        ),
        2627: MotorErrorCodeEntry(
            code=2627,
            motor="sqlserver",
            description="Unique constraint violated",
            retry_policy="no_retry",
            severity="permanent",
            category="constraint",
        ),
        547: MotorErrorCodeEntry(
            code=547,
            motor="sqlserver",
            description="Foreign key constraint violation",
            retry_policy="no_retry",
            severity="permanent",
            category="constraint",
        ),
    },
    "sqlite": {
        19: MotorErrorCodeEntry(
            code=19,
            motor="sqlite",
            description="UNIQUE constraint failed",
            retry_policy="no_retry",
            severity="permanent",
            category="constraint",
        ),
        787: MotorErrorCodeEntry(
            code=787,
            motor="sqlite",
            description="FOREIGN KEY constraint failed",
            retry_policy="no_retry",
            severity="permanent",
            category="constraint",
        ),
    },
}


class ErrorCodeRegistry:
    """Registro centralizado de códigos de error de motor.

    Uso (futuro, en v0.31.0+):

    .. code-block:: python

        registry = ErrorCodeRegistry()
        entry = registry.lookup("mysql", 1205)
        if entry and entry.retry_policy == "retry_once":
            # Reintentar la operación
            retry_operation()
    """

    def __init__(self) -> None:
        """Inicializa el registro con códigos conocidos."""
        self._registry = _ERROR_CODE_REGISTRY

    def lookup(self, motor: str, code: str | int) -> MotorErrorCodeEntry | None:
        """Busca un código de error por motor.

        Args:
            motor: Nombre del motor (mysql, postgresql, oracle, sqlserver, sqlite, mariadb, hsqldb).
            code: Código de error numérico o string.

        Returns:
            Entrada de error si se encuentra, None si no.
        """
        motor_entries = self._registry.get(motor, {})
        return motor_entries.get(code)

    def get_all(self, motor: str) -> dict[str | int, MotorErrorCodeEntry]:
        """Obtiene todos los códigos conocidos de un motor.

        Args:
            motor: Nombre del motor.

        Returns:
            Diccionario de todos los códigos de error registrados para ese motor.
        """
        return self._registry.get(motor, {})

    def is_transient(self, motor: str, code: str | int) -> bool:
        """Determina si un error es transitorio (retry-able).

        Args:
            motor: Nombre del motor.
            code: Código de error.

        Returns:
            True si el error es transitorio, False si es permanente o desconocido.
        """
        entry = self.lookup(motor, code)
        return entry is not None and entry.severity == "transient"
