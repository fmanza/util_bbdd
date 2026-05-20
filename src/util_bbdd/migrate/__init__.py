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

Flujo principal (MariaDB → Oracle):
    planner = MigrationPlanner(
        source_engine="mariadb",
        target_engine="oracle",
    )
    plan = planner.plan(connection=mariadb_manager, schema="mi_db")
    ddl = plan.emit_ddl()

Flujo principal (MariaDB → SQL Server):
    planner = MigrationPlanner(
        source_engine="mariadb",
        target_engine="sqlserver",
        sql_server_collation="SQL_Latin1_General_CP1_CI_AS",  # opcional
    )
    plan = planner.plan(connection=mariadb_manager, schema="mi_db")
    ddl = plan.emit_ddl()

Flujo principal (MariaDB → PostgreSQL):
    planner = MigrationPlanner(
        source_engine="mariadb",
        target_engine="postgresql",
        pg_schema="mi_schema",  # opcional
    )
    plan = planner.plan(connection=mariadb_manager, schema="mi_db")
    ddl = plan.emit_ddl()

Flujo principal (SQL Server → Oracle):
    planner = MigrationPlanner(
        source_engine="sqlserver",
        target_engine="oracle",
    )
    plan = planner.plan(connection=sqlserver_manager, schema="dbo")
    ddl = plan.emit_ddl()

Flujo principal (SQL Server → MariaDB):
    planner = MigrationPlanner(
        source_engine="sqlserver",
        target_engine="mariadb",
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
    )
    plan = planner.plan(connection=sqlserver_manager, schema="dbo")
    ddl = plan.emit_ddl()

Flujo principal (SQL Server → PostgreSQL):
    planner = MigrationPlanner(
        source_engine="sqlserver",
        target_engine="postgresql",
        pg_schema="mi_schema",  # opcional
    )
    plan = planner.plan(connection=sqlserver_manager, schema="dbo")
    ddl = plan.emit_ddl()

Soportado: Oracle      → MariaDB / SQL Server / PostgreSQL
           MariaDB     → Oracle  / SQL Server / PostgreSQL
           SQL Server  → Oracle  / MariaDB    / PostgreSQL
"""

from .charset import DEFAULT_CHARSET, DEFAULT_COLLATION, validate_charset, validate_collation
from .emitters.mariadb import MariaDBDDLEmitter
from .emitters.oracle import OracleDDLEmitter
from .emitters.postgresql import PostgreSQLDDLEmitter
from .emitters.sqlserver import SQLServerDDLEmitter
from .extractors.mariadb import MariaDBSchemaExtractor
from .extractors.oracle import OracleSchemaExtractor
from .extractors.sqlserver import SQLServerSchemaExtractor
from .ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    CanonicalView,
    MigrationPlan,
    MigrationWarning,
)
from .planner import MigrationPlanner
from .reporters.markdown import format_plan_markdown
from .reporters.text import format_plan_text
from .transformers.mariadb_to_oracle import MariaDBToOracleTransformer
from .transformers.mariadb_to_postgresql import MariaDBToPostgreSQLTransformer
from .transformers.mariadb_to_sqlserver import MariaDBToSQLServerTransformer
from .transformers.oracle_to_mariadb import OracleToMariaDBTransformer
from .transformers.oracle_to_postgresql import OracleToPostgreSQLTransformer
from .transformers.oracle_to_sqlserver import OracleToSQLServerTransformer
from .transformers.sqlserver_to_mariadb import SQLServerToMariaDBTransformer
from .transformers.sqlserver_to_oracle import SQLServerToOracleTransformer
from .transformers.sqlserver_to_postgresql import SQLServerToPostgreSQLTransformer

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
    "CanonicalView",
    # Capas individuales Oracle → MariaDB
    "OracleSchemaExtractor",
    "OracleToMariaDBTransformer",
    "MariaDBDDLEmitter",
    # Capas individuales Oracle → SQL Server
    "OracleToSQLServerTransformer",
    "SQLServerDDLEmitter",
    # Capas individuales Oracle → PostgreSQL
    "OracleToPostgreSQLTransformer",
    "PostgreSQLDDLEmitter",
    # Capas individuales MariaDB → Oracle
    "MariaDBSchemaExtractor",
    "MariaDBToOracleTransformer",
    "OracleDDLEmitter",
    # Capas individuales MariaDB → SQL Server
    "MariaDBToSQLServerTransformer",
    # Capas individuales MariaDB → PostgreSQL
    "MariaDBToPostgreSQLTransformer",
    # Capas individuales SQL Server → Oracle
    "SQLServerSchemaExtractor",
    "SQLServerToOracleTransformer",
    # Capas individuales SQL Server → MariaDB
    "SQLServerToMariaDBTransformer",
    # Capas individuales SQL Server → PostgreSQL
    "SQLServerToPostgreSQLTransformer",
    # Reporters
    "format_plan_text",
    "format_plan_markdown",
    # Charset (MariaDB)
    "DEFAULT_CHARSET",
    "DEFAULT_COLLATION",
    "validate_charset",
    "validate_collation",
]
