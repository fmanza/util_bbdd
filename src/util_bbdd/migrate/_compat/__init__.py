"""Tablas de compatibilidad entre motores de bases de datos."""

from .identifier_rules import check_identifier, truncate_identifier
from .type_map import TypeMapping, resolve_number_type, resolve_oracle_type
from .type_map_postgresql_to_mariadb import (
    POSTGRESQL_TO_MARIADB,
    TypeMappingPostgreSQLToMariaDB,
    resolve_postgresql_type_mariadb,
)
from .type_map_postgresql_to_oracle import (
    POSTGRESQL_TO_ORACLE,
    TypeMappingPostgreSQLToOracle,
    resolve_postgresql_type_oracle,
)
from .type_map_postgresql_to_sqlserver import (
    POSTGRESQL_TO_SQLSERVER,
    TypeMappingPostgreSQLToSQLServer,
    resolve_postgresql_type_sqlserver,
)
from .type_map_sqlserver_to_mariadb import (
    SQLSERVER_TO_MARIADB,
    TypeMappingSQLServerToMariaDB,
    resolve_sqlserver_type_mariadb,
)
from .type_map_sqlserver_to_oracle import (
    SQLSERVER_TO_ORACLE,
    TypeMappingSQLServerToOracle,
    resolve_sqlserver_type_oracle,
)
from .type_map_sqlserver_to_postgresql import (
    SQLSERVER_TO_POSTGRESQL,
    TypeMappingSQLServerToPostgreSQL,
    resolve_sqlserver_type_postgresql,
)

__all__: list[str] = [
    "TypeMapping",
    "resolve_oracle_type",
    "resolve_number_type",
    "truncate_identifier",
    "check_identifier",
    "TypeMappingSQLServerToOracle",
    "SQLSERVER_TO_ORACLE",
    "resolve_sqlserver_type_oracle",
    "TypeMappingSQLServerToMariaDB",
    "SQLSERVER_TO_MARIADB",
    "resolve_sqlserver_type_mariadb",
    "TypeMappingSQLServerToPostgreSQL",
    "SQLSERVER_TO_POSTGRESQL",
    "resolve_sqlserver_type_postgresql",
    "TypeMappingPostgreSQLToOracle",
    "POSTGRESQL_TO_ORACLE",
    "resolve_postgresql_type_oracle",
    "TypeMappingPostgreSQLToMariaDB",
    "POSTGRESQL_TO_MARIADB",
    "resolve_postgresql_type_mariadb",
    "TypeMappingPostgreSQLToSQLServer",
    "POSTGRESQL_TO_SQLSERVER",
    "resolve_postgresql_type_sqlserver",
]
