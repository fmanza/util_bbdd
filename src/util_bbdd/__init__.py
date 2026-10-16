"""util_bbdd: operaciones con varios motores de base de datos.

Soporta MariaDB, MySQL, Oracle, PostgreSQL, SQLite, SQL Server y HSQLDB.

La raíz exporta solo los puntos de entrada y sus resultados (API 1.0). El resto vive en submódulos públicos estables:
``util_bbdd.exceptions``, ``.audit``, ``.metadata``, ``.connection``, ``.factory``, ``.analysis`` y ``.async_utils``.

Los puntos de entrada que dependen de pandas, openpyxl, python-docx o jinja2 (``BulkCrud``, ``SchemaComparator``,
``DumpOrchestrator``, ``MigrationPlanner``, ``DatabaseDocumentation``…) se cargan al usarlos por primera vez, de modo
que ``import util_bbdd`` solo carga los managers.

Los nombres que la raíz exportaba hasta 0.42 se retiraron en 1.0.0; la guía de migración
(``docs/guides/api_1_0_migration.md``) dice desde qué submódulo se importa cada uno.

Examples:
    >>> from util_bbdd import SyncDatabaseManager
    >>> from util_bbdd.exceptions import QueryNotFoundError
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .exceptions import DatabaseException
from .managers.async_mgr import AsyncDatabaseManager
from .managers.sync_mgr import SyncDatabaseManager

if TYPE_CHECKING:
    from .bulk import BulkCrud, ParallelBulkLoader
    from .comparar import SchemaComparator, SchemaDiff
    from .doc import DatabaseDocumentation
    from .dump import DumpConfig, DumpOrchestrator, DumpResult
    from .migrate import MigrationPlan, MigrationPlanner

__all__: list[str] = [
    # Conexión y consultas
    "SyncDatabaseManager",
    "AsyncDatabaseManager",
    # Carga masiva
    "BulkCrud",
    "ParallelBulkLoader",
    # Volcado
    "DumpOrchestrator",
    "DumpConfig",
    "DumpResult",
    # Migración DDL
    "MigrationPlanner",
    "MigrationPlan",
    # Comparación de esquemas
    "SchemaComparator",
    "SchemaDiff",
    # Documentación
    "DatabaseDocumentation",
    # Error base
    "DatabaseException",
]

# Puntos de entrada de carga perezosa: símbolo → submódulo que lo exporta.
_LAZY: dict[str, str] = {
    "BulkCrud": "bulk",
    "ParallelBulkLoader": "bulk",
    "DumpOrchestrator": "dump",
    "DumpConfig": "dump",
    "DumpResult": "dump",
    "MigrationPlanner": "migrate",
    "MigrationPlan": "migrate",
    "SchemaComparator": "comparar",
    "SchemaDiff": "comparar",
    "DatabaseDocumentation": "doc",
}

# Submódulos que ``util_bbdd.<nombre>`` resuelve sin importarlos antes (hasta 0.42 los cargaba ``import util_bbdd``).
_SUBMODULES: frozenset[str] = frozenset(
    {
        "analysis",
        "async_utils",
        "audit",
        "bulk",
        "comparar",
        "connection",
        "doc",
        "dump",
        "exceptions",
        "factory",
        "managers",
        "metadata",
        "migrate",
    }
)


def __getattr__(name: str) -> Any:
    module_name: str | None = _LAZY.get(name)
    if module_name is not None:
        value = getattr(import_module(f".{module_name}", __name__), name)
        globals()[name] = value
        return value
    if name in _SUBMODULES:
        return import_module(f".{name}", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
