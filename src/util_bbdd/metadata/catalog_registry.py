"""Registro de ``CatalogDialect`` por motor (ADR-003).

Resuelve el dialecto de catálogo por ``db_type`` de la librería (``postgresql``, ``sqlserver``…) o por nombre de
dialecto de SQLAlchemy (``mssql``…). Los módulos se importan al pedirlos, no al importar este: añadir un motor es una
entrada en ``_BUILTIN`` (o :func:`register_catalog_dialect`) y su ``metadata/<motor>/catalog.py``; ningún consumidor
cambia.
"""

from __future__ import annotations

import importlib
import threading

from .._core.exceptions import MetadataError
from .contracts import CatalogDialect

# db_type → ("módulo:Clase", nombres de dialecto de SQLAlchemy)
_BUILTIN: dict[str, tuple[str, frozenset[str]]] = {
    "postgresql": ("util_bbdd.metadata.postgresql.catalog:PostgreSQLCatalog", frozenset({"postgresql"})),
    "oracle": ("util_bbdd.metadata.oracle.catalog:OracleCatalog", frozenset({"oracle"})),
}

_lock = threading.Lock()
_instances: dict[str, CatalogDialect] = {}
_extra: dict[str, CatalogDialect] = {}


class CatalogDialectNotFoundError(MetadataError):
    """No hay ``CatalogDialect`` para el motor pedido."""


def _canonical(name: str) -> str | None:
    key = name.strip().lower()
    if key in _extra or key in _BUILTIN:
        return key
    for db_type, dialect in _extra.items():
        if key in dialect.sqlalchemy_names:
            return db_type
    for db_type, (_, sqlalchemy_names) in _BUILTIN.items():
        if key in sqlalchemy_names:
            return db_type
    return None


def get_catalog_dialect(name: str) -> CatalogDialect:
    """``CatalogDialect`` de un ``db_type`` o de un nombre de dialecto de SQLAlchemy.

    Raises:
        CatalogDialectNotFoundError: Si el motor no tiene dialecto de catálogo.
    """
    db_type = _canonical(name)
    if db_type is None:
        raise CatalogDialectNotFoundError(
            f"Sin dialecto de catálogo para '{name}' (motores: {', '.join(supported_catalog_engines())})"
        )
    with _lock:
        if db_type in _extra:
            return _extra[db_type]
        if db_type not in _instances:
            module_name, class_name = _BUILTIN[db_type][0].split(":")
            _instances[db_type] = getattr(importlib.import_module(module_name), class_name)()
        return _instances[db_type]


def register_catalog_dialect(dialect: CatalogDialect) -> None:
    """Registra (o sustituye) el dialecto de catálogo de ``dialect.name``."""
    with _lock:
        _extra[dialect.name.strip().lower()] = dialect


def supported_catalog_engines() -> list[str]:
    return sorted(set(_BUILTIN) | set(_extra))


__all__: list[str] = [
    "CatalogDialectNotFoundError",
    "get_catalog_dialect",
    "register_catalog_dialect",
    "supported_catalog_engines",
]
