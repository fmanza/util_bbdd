"""Analítica de la auditoría: re-exportación de :mod:`util_bbdd.audit.analytics`.

El código vive en ``util_bbdd.audit`` desde la sesión 2026-10-02c; este módulo se conserva para los imports existentes.
"""

from __future__ import annotations

from ...audit.analytics import AuditAnalyticsService

__all__: list[str] = ["AuditAnalyticsService"]
