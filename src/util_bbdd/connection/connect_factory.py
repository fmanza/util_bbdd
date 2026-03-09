"""Factory para crear conexiones según driver nativo."""

import inspect
import logging

from collections.abc import Callable
from typing import Any

from ..connection.hsqldb.connection_hsqldb import HSQLDBConnection
from ..connection.mariadb.connection_mariadb import MariaDBConnection
from ..connection.oracle.connection_oracle import OracleConnection
from ..connection.postgresql.connection_postgresql import PostgreSQLConnection
from ..connection.sqlite.connection_sqlite import SQLiteConnection
from ..connection.sqlserver.connection_sqlserver import SQLServerConnection
from ..core.capabilities import is_async_supported


class ConnectFactory:
    """Factory para crear conexiones según driver nativo."""

    logger: logging.Logger = logging.getLogger(__name__)
    _async_connection_builders: dict[str, Callable[..., Any]] = {}

    @staticmethod
    def register_async_connection(db_type: str, builder: Callable[..., Any]) -> None:
        """Registra constructor async para un motor."""
        ConnectFactory._async_connection_builders[db_type.lower().strip()] = builder

    @staticmethod
    async def create_async_connection(
        db_type: str,
        conn_params: dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        """Crea conexión async con constructor registrado por motor."""
        normalized_type: str = db_type.lower().strip()
        builder: Callable[..., Any] | None = ConnectFactory._async_connection_builders.get(normalized_type)
        if builder is None and normalized_type == "postgresql":
            from ..connection.postgresql.async_connection_postgresql import AsyncPostgreSQLConnection

            ConnectFactory.register_async_connection("postgresql", AsyncPostgreSQLConnection.connect)
            builder = ConnectFactory._async_connection_builders.get(normalized_type)

        if builder is None and normalized_type == "sqlite":
            from ..connection.sqlite.async_connection_sqlite import AsyncSQLiteConnection

            ConnectFactory.register_async_connection("sqlite", AsyncSQLiteConnection.connect)
            builder = ConnectFactory._async_connection_builders.get(normalized_type)

        if builder is None and normalized_type == "mariadb":
            from ..connection.mariadb.async_connection_mariadb import AsyncMariaDBConnection

            ConnectFactory.register_async_connection("mariadb", AsyncMariaDBConnection.connect)
            builder = ConnectFactory._async_connection_builders.get(normalized_type)

        if builder is None and normalized_type == "oracle":
            from ..connection.oracle.async_connection_oracle import AsyncOracleConnection

            ConnectFactory.register_async_connection("oracle", AsyncOracleConnection.connect)
            builder = ConnectFactory._async_connection_builders.get(normalized_type)

        if builder is None and normalized_type == "sqlserver":
            from ..connection.sqlserver.async_connection_sqlserver import AsyncSQLServerConnection

            ConnectFactory.register_async_connection("sqlserver", AsyncSQLServerConnection.connect)
            builder = ConnectFactory._async_connection_builders.get(normalized_type)

        async_supported = is_async_supported(normalized_type)
        if builder is None and async_supported is False:
            raise NotImplementedError(f"Conexión async no soportada para '{normalized_type}'.")

        if builder is None:
            raise NotImplementedError(
                f"Conexión async no soportada para '{db_type}'. Registre builder con register_async_connection()."
            )

        result: Any = builder(conn_params, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

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

                raise DatabaseConnectionError(f"Tipo de base de datos no soportado: {db_type}", db_type)

        except Exception as e:
            ConnectFactory.logger.error(f"❌ Error al crear conexión para BD tipo '{db_type}': {str(e)}")
            raise
