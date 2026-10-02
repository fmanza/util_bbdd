"""Registro de auditoría de una operación bulk: re-exportación de :mod:`util_bbdd.audit.legacy_csv`.

El código vive en ``util_bbdd.audit`` desde la sesión 2026-10-02c; este módulo se conserva para los imports existentes.
"""

from __future__ import annotations

from ...audit.legacy_csv import AUDIT_OPERATIONS, AuditRecord

__all__: list[str] = ["AUDIT_OPERATIONS", "AuditRecord"]
