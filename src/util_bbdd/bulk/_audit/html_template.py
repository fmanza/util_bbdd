"""Plantilla HTML del informe de auditoría: re-exportación de :mod:`util_bbdd.audit.html_template`.

El código vive en ``util_bbdd.audit`` desde la sesión 2026-10-02c; este módulo se conserva para los imports existentes.
"""

from __future__ import annotations

from ...audit.html_template import AUDIT_HTML_TEMPLATE

__all__: list[str] = ["AUDIT_HTML_TEMPLATE"]
