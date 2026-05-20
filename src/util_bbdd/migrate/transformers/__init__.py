"""Transformadores de esquemas para el módulo migrate."""

from .base import SchemaTransformer
from .mariadb_to_oracle import MariaDBToOracleTransformer
from .mariadb_to_postgresql import MariaDBToPostgreSQLTransformer
from .mariadb_to_sqlserver import MariaDBToSQLServerTransformer
from .oracle_to_mariadb import OracleToMariaDBTransformer
from .oracle_to_postgresql import OracleToPostgreSQLTransformer
from .oracle_to_sqlserver import OracleToSQLServerTransformer
from .postgresql_to_mariadb import PostgreSQLToMariaDBTransformer
from .postgresql_to_oracle import PostgreSQLToOracleTransformer
from .postgresql_to_sqlserver import PostgreSQLToSQLServerTransformer
from .sqlserver_to_mariadb import SQLServerToMariaDBTransformer
from .sqlserver_to_oracle import SQLServerToOracleTransformer
from .sqlserver_to_postgresql import SQLServerToPostgreSQLTransformer

__all__: list[str] = [
    "SchemaTransformer",
    "OracleToMariaDBTransformer",
    "OracleToSQLServerTransformer",
    "OracleToPostgreSQLTransformer",
    "MariaDBToOracleTransformer",
    "MariaDBToSQLServerTransformer",
    "MariaDBToPostgreSQLTransformer",
    "SQLServerToOracleTransformer",
    "SQLServerToMariaDBTransformer",
    "SQLServerToPostgreSQLTransformer",
    "PostgreSQLToOracleTransformer",
    "PostgreSQLToMariaDBTransformer",
    "PostgreSQLToSQLServerTransformer",
]
