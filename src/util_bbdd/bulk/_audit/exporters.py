"""Exportadores de la auditoría (Excel, JSON y HTML): re-exportación de :mod:`util_bbdd.audit.exporters`.

El código vive en ``util_bbdd.audit`` desde la sesión 2026-10-02c; este módulo se conserva para los imports existentes.
"""

from __future__ import annotations

from ...audit.exporters import AuditExporters

__all__: list[str] = ["AuditExporters"]
