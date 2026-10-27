"""Capabilities funcionales por motor."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

DB_ASYNC_CAPABILITIES: dict[str, bool] = {
    "mariadb": True,
    "mysql": True,
    "oracle": True,
    "postgresql": True,
    "sqlserver": True,
    "sqlite": True,
    "hsqldb": False,
}


def is_async_supported(db_type: str) -> bool | None:
    """Indica si un motor soporta runtime async.

    Devuelve `None` para motores desconocidos.
    """
    return DB_ASYNC_CAPABILITIES.get(db_type.lower().strip())


@dataclass(frozen=True, slots=True)
class EngineCapabilities:
    """Qué operaciones de util_bbdd admite un motor (v4.6.0, G5 de util_bbdd_web).

    Es una tabla declarativa: ``core`` es Foundation y no importa los módulos que implementan cada operación.
    ``tests/unit/connection/test_engine_capability_matrix.py`` la contrasta con cada fuente (``MigrationPlanner``,
    ``EngineReadinessAdvisor``, el registro de dialectos de catálogo, ``dump`` y la fábrica de SQLAlchemy), así que un
    cambio de soporte que no se refleje aquí hace fallar los tests.

    Attributes:
        db_type: Tipo de motor de la librería (``"sqlserver"``, no ``"mssql"``).
        async_supported: ``AsyncDatabaseManager`` (:data:`DB_ASYNC_CAPABILITIES`).
        migrate_source: Origen de ``MigrationPlanner`` (``MigrationPlanner.supported_sources()``).
        migrate_target: Destino de ``MigrationPlanner`` (``MigrationPlanner.supported_targets()``).
        readiness: ``EngineReadinessAdvisor`` tiene comprobaciones del motor (``assess(...).supported``).
        documentation: ``DatabaseDocumentation`` (hay dialecto de catálogo).
        graphs: Grafos de relaciones de ``analysis`` (hay dialecto de catálogo).
        compare: ``SchemaComparator`` (compara ``Inspector`` de SQLAlchemy: hace falta dialecto de SQLAlchemy).
        dump: ``DumpOrchestrator`` como origen o destino (engines de SQLAlchemy).
        dump_constraints: El volcado desactiva y reactiva las constraints del destino (``DumpConfig``); en el resto
            de motores con ``dump`` carga sin tocarlas.
        bulk: ``BulkCrud`` y ``ParallelBulkLoader`` (engine de SQLAlchemy).
    """

    db_type: str
    async_supported: bool
    migrate_source: bool
    migrate_target: bool
    readiness: bool
    documentation: bool
    graphs: bool
    compare: bool
    dump: bool
    dump_constraints: bool
    bulk: bool


def _server(db_type: str, *, async_supported: bool = True, migrate: bool = True) -> EngineCapabilities:
    """Motor de servidor con dialecto de SQLAlchemy: todas las operaciones salvo las que se indiquen."""
    return EngineCapabilities(
        db_type=db_type,
        async_supported=async_supported,
        migrate_source=migrate,
        migrate_target=migrate,
        readiness=True,
        documentation=True,
        graphs=True,
        compare=True,
        dump=True,
        dump_constraints=True,
        bulk=True,
    )


#: Capacidades de cada motor soportado, en el orden de ``database_types.json``.
ENGINE_CAPABILITIES: Final = MappingProxyType(
    {
        "mariadb": _server("mariadb"),
        "mysql": _server("mysql"),
        "oracle": _server("oracle"),
        "postgresql": _server("postgresql"),
        "hsqldb": EngineCapabilities(
            db_type="hsqldb",
            async_supported=False,
            migrate_source=False,
            migrate_target=False,
            readiness=False,
            documentation=True,
            graphs=True,
            compare=False,  # sin dialecto de SQLAlchemy: conexión JDBC nativa
            dump=False,
            dump_constraints=False,
            bulk=False,
        ),
        "sqlserver": _server("sqlserver"),
        "sqlite": EngineCapabilities(
            db_type="sqlite",
            async_supported=True,
            migrate_source=False,
            migrate_target=False,
            readiness=True,
            documentation=True,
            graphs=True,
            compare=True,
            dump=True,
            dump_constraints=False,  # sin DDL para desactivar constraints: carga en orden de FK
            bulk=True,
        ),
    }
)


def get_engine_capabilities(db_type: str) -> EngineCapabilities | None:
    """Capacidades de ``db_type`` (G5 de util_bbdd_web); ``None`` para motores desconocidos, como :func:`is_async_supported`.

    Args:
        db_type: Tipo de motor de la librería, sin distinguir mayúsculas ni espacios alrededor.

    Example:
        >>> caps = get_engine_capabilities("sqlite")
        >>> (caps.bulk, caps.migrate_source)
        (True, False)
    """
    return ENGINE_CAPABILITIES.get(db_type.lower().strip())
