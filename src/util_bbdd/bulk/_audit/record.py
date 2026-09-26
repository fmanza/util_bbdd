"""Registro de auditoría de una operación bulk, listo para escribirse en el CSV."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Operaciones que admite el CSV de auditoría.
AUDIT_OPERATIONS: tuple[str, ...] = ("INSERT", "UPDATE", "DELETE")


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """Una fila del CSV de auditoría.

    ``timestamp`` es el momento en que terminó la operación, no el de la escritura: dentro de ``BulkCrud.bulk_session``
    la fila se escribe al confirmarse la transacción, que puede ser bastante después.
    """

    tabla: str
    motor: str
    operacion: str
    rowcount: int
    elapsed: float
    genero_sql: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


__all__: list[str] = ["AUDIT_OPERATIONS", "AuditRecord"]
