"""Excepciones compartidas para el subsistema de auditoría bulk."""

from __future__ import annotations


class AuditError(Exception):
    """Excepción base para auditoría."""


class AuditConfigError(AuditError):
    """Error en configuración de auditoría."""


class AuditFileError(AuditError):
    """Error en archivo de auditoría."""


class AuditDataError(AuditError):
    """Error en datos de auditoría."""


class AuditValidationError(AuditError):
    """Error en validación de parámetros."""


__all__: list[str] = [
    "AuditConfigError",
    "AuditDataError",
    "AuditError",
    "AuditFileError",
    "AuditValidationError",
]
