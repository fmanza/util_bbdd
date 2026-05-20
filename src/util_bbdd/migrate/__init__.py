"""Módulo migrate: migración DDL entre motores de base de datos.

Flujo principal (Oracle → MariaDB):
    planner = MigrationPlanner(
        source_engine="oracle",
        target_engine="mariadb",
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
    )
    plan = planner.plan(connection=oracle_manager, schema="MY_SCHEMA")
    ddl = plan.emit_ddl()                               # script .sql
    plan.execute(target_connection=mariadb_manager)     # ejecución directa

Flujo principal (Oracle → SQL Server):
    planner = MigrationPlanner(
        source_engine="oracle",
        target_engine="sqlserver",
        sql_server_collation="SQL_Latin1_General_CP1_CI_AS",  # opcional
    )
    plan = planner.plan(connection=oracle_manager, schema="MY_SCHEMA")
    ddl = plan.emit_ddl()

Flujo principal (Oracle → PostgreSQL):
    planner = MigrationPlanner(
        source_engine="oracle",
        target_engine="postgresql",
        pg_schema="mi_schema",  # opcional; emite SET search_path
    )
    plan = planner.plan(connection=oracle_manager, schema="MY_SCHEMA")
    ddl = plan.emit_ddl()

Soportado: Oracle → MariaDB, Oracle → SQL Server, Oracle → PostgreSQL.
"""

from .charset import DEFAULT_CHARSET, DEFAULT_COLLATION, validate_charset, validate_collation
from .emitters.mariadb import MariaDBDDLEmitter
from .emitters.postgresql import PostgreSQLDDLEmitter
from .emitters.sqlserver import SQLServerDDLEmitter
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
from .transformers.oracle_to_postgresql import OracleToPostgreSQLTransformer
from .transformers.oracle_to_sqlserver import OracleToSQLServerTransformer

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
    # Capas individuales Oracle → MariaDB (uso avanzado)
    "OracleSchemaExtractor",
    "OracleToMariaDBTransformer",
    "MariaDBDDLEmitter",
    # Capas individuales Oracle → SQL Server (uso avanzado)
    "OracleToSQLServerTransformer",
    "SQLServerDDLEmitter",
    # Capas individuales Oracle → PostgreSQL (uso avanzado)
    "OracleToPostgreSQLTransformer",
    "PostgreSQLDDLEmitter",
    # Reporters
    "format_plan_text",
    "format_plan_markdown",
    # Charset (MariaDB)
    "DEFAULT_CHARSET",
    "DEFAULT_COLLATION",
    "validate_charset",
    "validate_collation",
]
