"""Excepciones del subsistema de auditoría bulk.

Desde v0.18.0 viven en la jerarquía canónica (``util_bbdd._core.exceptions``) bajo ``DatabaseException``; este módulo
las re-exporta para que los imports existentes (``util_bbdd.bulk``, ``util_bbdd.bulk.audit``) sigan funcionando con las
mismas clases.
"""

from __future__ import annotations

from ..._core.exceptions import (
    AuditConfigError,
    AuditDataError,
    AuditError,
    AuditFileError,
    AuditValidationError,
)

__all__: list[str] = [
    "AuditConfigError",
    "AuditDataError",
    "AuditError",
    "AuditFileError",
    "AuditValidationError",
]
