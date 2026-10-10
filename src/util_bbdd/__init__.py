"""util_bbdd: operaciones con varios motores de base de datos.

Soporta MariaDB, MySQL, Oracle, PostgreSQL, SQLite, SQL Server y HSQLDB.

La raíz exporta solo los puntos de entrada y sus resultados (API 1.0). El resto vive en submódulos públicos estables:
``util_bbdd.exceptions``, ``.audit``, ``.metadata``, ``.connection``, ``.factory``, ``.analysis`` y ``.async_utils``.

Los puntos de entrada que dependen de pandas, openpyxl, python-docx o jinja2 (``BulkCrud``, ``SchemaComparator``,
``DumpOrchestrator``, ``MigrationPlanner``, ``DatabaseDocumentation``…) se cargan al usarlos por primera vez, de modo
que ``import util_bbdd`` solo carga los managers.

Los nombres que la raíz exportaba hasta 0.42 siguen disponibles con ``DeprecationWarning`` y se retiran en 1.0.0; la
guía de migración está en ``docs/guides/api_1_0_migration.md``.

Example:
    >>> from util_bbdd import SyncDatabaseManager
    >>> from util_bbdd.exceptions import QueryNotFoundError
"""

from __future__ import annotations

import warnings

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

# Nombres exportados por la raíz hasta 0.42 que salen de ella en 0.43 (DeprecationWarning) y se retiran en 1.0.0:
# símbolo → submódulo público que lo exporta desde ahora.
_DEPRECATED: dict[str, str] = {
    **dict.fromkeys(
        (
            "ConnectionError",
            "PoolConnectionError",
            "PoolExhaustedError",
            "PoolTimeoutError",
            "DriverError",
            "ValidationError",
            "InvalidDatabaseType",
            "DatabaseOperationError",
            "DatabaseConfigurationError",
            "QueryError",
            "QueryNotFoundError",
            "QueryValidationError",
            "QueryParameterError",
            "QueryTimeoutError",
            "QueryExecutionError",
            "ComparerError",
            "SchemaDiffValidationError",
            "MetadataIntrospectionError",
            "DiffReportGenerationError",
            "DumpError",
            "DumpConstraintError",
            "DumpReportError",
            "AuditError",
            "AuditConfigError",
            "AuditFileError",
            "AuditDataError",
            "AuditExportError",
            "AuditValidationError",
            "DocumentationError",
            "DocumentationConfigError",
            "DocumentationRenderError",
        ),
        "exceptions",
    ),
    **dict.fromkeys(("AuditEvent", "AuditSink", "JsonLinesAuditSink", "MemoryAuditSink", "NullAuditSink"), "audit"),
    **dict.fromkeys(("SyncMetadataProvider", "AsyncMetadataProvider"), "metadata"),
    **dict.fromkeys(("build_conn_params", "EngineReadinessAdvisor", "AdvisoryFinding"), "connection"),
    **dict.fromkeys(("ConnectionFactory", "PoolFactory"), "factory"),
    "maybe_await": "async_utils",
    "TableDumpResult": "dump",
    "MigrationWarning": "migrate",
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
    module_name = _DEPRECATED.get(name)
    if module_name is not None:
        warnings.warn(
            f"'util_bbdd.{name}' está obsoleto y se retirará en util_bbdd 1.0.0; "
            f"usa 'from util_bbdd.{module_name} import {name}'.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(import_module(f".{module_name}", __name__), name)
    if name in _SUBMODULES:
        return import_module(f".{name}", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
