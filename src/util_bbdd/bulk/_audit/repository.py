"""Persistencia CSV y caché de la auditoría: re-exportación de :mod:`util_bbdd.audit.legacy_csv` y del lock por ruta.

El código vive en ``util_bbdd.audit`` desde la sesión 2026-10-02c; este módulo se conserva para los imports existentes.
``_get_file_lock`` es **el mismo** :func:`util_bbdd.audit.locks.path_lock` (un único registro de locks en el proceso).
"""

from __future__ import annotations

from ...audit.legacy_csv import AuditCsvRepository
from ...audit.locks import path_lock as _get_file_lock

__all__: list[str] = ["AuditCsvRepository", "_get_file_lock"]
