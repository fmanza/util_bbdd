"""Contadores de auditoría: re-exportación de :mod:`util_bbdd.audit.counters`.

El código vive en ``util_bbdd.audit`` desde la sesión 2026-10-02c; este módulo se conserva para los imports existentes.
"""

from __future__ import annotations

from ...audit.counters import AuditCounters, SupportsAuditCounters

__all__: list[str] = ["AuditCounters", "SupportsAuditCounters"]
