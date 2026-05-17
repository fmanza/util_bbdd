"""Módulo migrate: migración DDL entre motores de base de datos.

Flujo principal:
    planner = MigrationPlanner(
        source_engine="oracle",
        target_engine="mariadb",
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
    )
    plan = planner.plan(connection=oracle_manager, schema="MY_SCHEMA")
    ddl = plan.emit_ddl()                               # script .sql
    plan.execute(target_connection=mariadb_manager)     # ejecución directa

Soportado actualmente: Oracle → MariaDB.
"""

from .charset import DEFAULT_CHARSET, DEFAULT_COLLATION, validate_charset, validate_collation
from .emitters.mariadb import MariaDBDDLEmitter
from .extractors.oracle import OracleSchemaExtractor
from .ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    MigrationPlan,
    MigrationWarning,
)
from .planner import MigrationPlanner
from .reporters.markdown import format_plan_markdown
from .reporters.text import format_plan_text
from .transformers.oracle_to_mariadb import OracleToMariaDBTransformer

__all__: list[str] = [
    # Orquestador
    "MigrationPlanner",
    # IR
    "MigrationPlan",
    "MigrationWarning",
    "CanonicalTable",
    "CanonicalColumn",
    "CanonicalIndex",
    "CanonicalFK",
    # Capas individuales (uso avanzado)
    "OracleSchemaExtractor",
    "OracleToMariaDBTransformer",
    "MariaDBDDLEmitter",
    # Reporters
    "format_plan_text",
    "format_plan_markdown",
    # Charset
    "DEFAULT_CHARSET",
    "DEFAULT_COLLATION",
    "validate_charset",
    "validate_collation",
]
