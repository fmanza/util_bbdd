"""Factory para crear conexiones según driver nativo."""

import logging

from typing import Any

from ..connection.hsqldb.connection_hsqldb import HSQLDBConnection
from ..connection.mariadb.connection_mariadb import MariaDBConnection
from ..connection.oracle.connection_oracle import OracleConnection
from ..connection.postgresql.connection_postgresql import PostgreSQLConnection
from ..connection.sqlite.connection_sqlite import SQLiteConnection
from ..connection.sqlserver.connection_sqlserver import SQLServerConnection


class ConnectFactory:
    """Factory para crear conexiones según driver nativo."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def create_connection(
        db_type: str,
        conn_params: dict[str, Any],
        db_validator: Any = None,
        sql_server_driver: str = "pymssql",
    ) -> Any:
        """Crea conexión nativa según tipo de BD.

        Args:
            db_type: Tipo de BD ('mariadb', 'oracle', 'postgresql', 'hsqldb', 'sqlserver', 'sqlite').
            conn_params: Parámetros de conexión filtrados.
            db_validator: Validador de tipos de BD.
            sql_server_driver: Driver SQL Server a usar ('pymssql' o 'pyodbc').

        Returns:
            Conexión del driver específico.

        Raises:
            DatabaseConnectionError: Si hay error en la conexión.

        Example:
            ```python
            conn = ConnectFactory.create_connection(
                "sqlserver",
                {"host": "localhost", "user": "sa", "password": "pass", "database": "master"},
                sql_server_driver="pyodbc"
            )
            ```
        """
        try:
            if db_type == "mariadb":
                connection = MariaDBConnection.connect(conn_params)
                ConnectFactory.logger.info("🔗 MariaDB conexión creada (nativo)")
                return connection

            elif db_type == "oracle":
                connection = OracleConnection.connect(conn_params, db_validator)
                ConnectFactory.logger.info("🔗 Oracle conexión creada (nativo)")
                return connection

            elif db_type == "postgresql":
                connection = PostgreSQLConnection.connect(conn_params)
                ConnectFactory.logger.info("🔗 PostgreSQL conexión creada (psycopg3)")
                return connection

            elif db_type == "hsqldb":
                connection = HSQLDBConnection.connect(conn_params)
                ConnectFactory.logger.info("🔗 HSQLDB conexión creada (JayDeBeApi)")
                return connection

            elif db_type == "sqlserver":
                connection = SQLServerConnection.connect(conn_params, driver=sql_server_driver)
                ConnectFactory.logger.info(f"🔗 SQL Server conexión creada ({sql_server_driver})")
                return connection

            elif db_type == "sqlite":
                connection = SQLiteConnection.connect(conn_params)
                ConnectFactory.logger.info("🔗 SQLite conexión creada")
                return connection

            else:
                from util_bbdd.database_exceptions import DatabaseConnectionError

                raise DatabaseConnectionError(
                    f"Tipo de base de datos no soportado: {db_type}", db_type
                )

        except Exception as e:
            ConnectFactory.logger.error(
                f"❌ Error al crear conexión para BD tipo '{db_type}': {str(e)}"
            )
            raise
