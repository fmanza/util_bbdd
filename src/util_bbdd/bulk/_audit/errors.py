"""Excepciones compartidas para el subsistema de auditoría bulk."""

from __future__ import annotations


class AuditError(Exception):
    """Excepción base para auditoría."""


class AuditConfigError(AuditError, ValueError):
    """Error en configuración de auditoría.

    Hereda también de ``ValueError`` (H8, audit-code 2026-09-25): ``AuditCsvRepository.validar_ruta`` lanzaba
    ``ValueError`` y quien lo capturaba así sigue funcionando.
    """


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
