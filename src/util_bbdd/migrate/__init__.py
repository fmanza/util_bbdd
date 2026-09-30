"""Módulo migrate: migración DDL entre motores de base de datos.

Flujo principal (Oracle → MariaDB):
    planner = MigrationPlanner(
        source_engine="oracle",
        target_engine="mariadb",
        charset="utf8mb4",
        collation="utf8mb4_uca1400_ai_ci",
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
        collation="utf8mb4_uca1400_ai_ci",
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

Flujo principal (PostgreSQL → Oracle):
    planner = MigrationPlanner(
        source_engine="postgresql",
        target_engine="oracle",
    )
    plan = planner.plan(connection=pg_manager, schema="public")
    ddl = plan.emit_ddl()

Flujo principal (PostgreSQL → MariaDB):
    planner = MigrationPlanner(
        source_engine="postgresql",
        target_engine="mariadb",
        charset="utf8mb4",
        collation="utf8mb4_uca1400_ai_ci",
    )
    plan = planner.plan(connection=pg_manager, schema="public")
    ddl = plan.emit_ddl()

Flujo principal (PostgreSQL → SQL Server):
    planner = MigrationPlanner(
        source_engine="postgresql",
        target_engine="sqlserver",
        sql_server_collation="SQL_Latin1_General_CP1_CI_AS",  # opcional
    )
    plan = planner.plan(connection=pg_manager, schema="public")
    ddl = plan.emit_ddl()

Soportado: Oracle      → MariaDB / MySQL      / SQL Server / PostgreSQL
           MariaDB     → Oracle  / MySQL      / SQL Server / PostgreSQL
           MySQL       → Oracle  / MariaDB    / SQL Server / PostgreSQL
           SQL Server  → Oracle  / MariaDB    / MySQL      / PostgreSQL
           PostgreSQL  → Oracle  / MariaDB    / MySQL      / SQL Server
"""

from .charset import (
    DEFAULT_CHARSET,
    DEFAULT_COLLATION,
    DEFAULT_COLLATION_MYSQL,
    validate_charset,
    validate_collation,
    validate_mysql_collation,
)
from .emitters.mariadb import MariaDBDDLEmitter
from .emitters.mysql import MySQLDDLEmitter
from .emitters.oracle import OracleDDLEmitter
from .emitters.postgresql import PostgreSQLDDLEmitter
from .emitters.sqlserver import SQLServerDDLEmitter
from .extractors.mariadb import MariaDBSchemaExtractor
from .extractors.mysql import MariaDBFullTypeSchemaExtractor, MySQLSchemaExtractor
from .extractors.oracle import OracleSchemaExtractor
from .extractors.postgresql import PostgreSQLSchemaExtractor
from .extractors.sqlserver import SQLServerSchemaExtractor
from .ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalRoutine,
    CanonicalTable,
    CanonicalView,
    MigrationPlan,
    MigrationWarning,
    WarningCategory,
)
from .planner import MigrationPlanner
from .reporters.markdown import format_plan_markdown
from .reporters.text import format_plan_text
from .transformers.mariadb_to_mysql import MariaDBToMySQLTransformer
from .transformers.mariadb_to_oracle import MariaDBToOracleTransformer
from .transformers.mariadb_to_postgresql import MariaDBToPostgreSQLTransformer
from .transformers.mariadb_to_sqlserver import MariaDBToSQLServerTransformer
from .transformers.mysql_to_mariadb import MySQLToMariaDBTransformer
from .transformers.oracle_to_mariadb import OracleToMariaDBTransformer
from .transformers.oracle_to_postgresql import OracleToPostgreSQLTransformer
from .transformers.oracle_to_sqlserver import OracleToSQLServerTransformer
from .transformers.postgresql_to_mariadb import PostgreSQLToMariaDBTransformer
from .transformers.postgresql_to_oracle import PostgreSQLToOracleTransformer
from .transformers.postgresql_to_sqlserver import PostgreSQLToSQLServerTransformer
from .transformers.sqlserver_to_mariadb import SQLServerToMariaDBTransformer
from .transformers.sqlserver_to_oracle import SQLServerToOracleTransformer
from .transformers.sqlserver_to_postgresql import SQLServerToPostgreSQLTransformer
from .views import ViewStrategy, ViewValidationResult

__all__: list[str] = [
    # Orquestador
    "MigrationPlanner",
    # IR
    "MigrationPlan",
    "MigrationWarning",
    "WarningCategory",
    "CanonicalTable",
    "CanonicalColumn",
    "CanonicalIndex",
    "CanonicalFK",
    "CanonicalView",
    "CanonicalRoutine",
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
    # Capas individuales PostgreSQL → Oracle
    "PostgreSQLSchemaExtractor",
    "PostgreSQLToOracleTransformer",
    # Capas individuales PostgreSQL → MariaDB
    "PostgreSQLToMariaDBTransformer",
    # Capas individuales PostgreSQL → SQL Server
    "PostgreSQLToSQLServerTransformer",
    # Capas individuales MySQL (origen: transformers MariaDB → X; destino: transformers X → MariaDB)
    "MySQLSchemaExtractor",
    "MySQLDDLEmitter",
    "MySQLToMariaDBTransformer",
    "MariaDBToMySQLTransformer",
    "MariaDBFullTypeSchemaExtractor",
    # Vistas (view_strategy, validate_views)
    "ViewStrategy",
    "ViewValidationResult",
    # Reporters
    "format_plan_text",
    "format_plan_markdown",
    # Charset (MariaDB / MySQL)
    "DEFAULT_CHARSET",
    "DEFAULT_COLLATION",
    "DEFAULT_COLLATION_MYSQL",
    "validate_charset",
    "validate_collation",
    "validate_mysql_collation",
]
