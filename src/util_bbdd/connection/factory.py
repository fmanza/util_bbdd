"""Factory para crear y gestionar conexiones según driver específico.

Proporciona métodos de fábrica para crear conexiones sync y async
usando los drivers nativos correspondientes.
"""

import inspect
import logging

from collections.abc import Callable
from typing import Any

from .._core import ConnectionError as CoreConnectionError
from .._core.capabilities import is_async_supported

logger: logging.Logger = logging.getLogger(__name__)


class ConnectionFactory:
    """Factory centralizado para crear conexiones sync y async.

    Maneja:
    - Registro de builders async por motor
    - Creación de conexiones nativas sync
    - Creación de conexiones async con lazy loading
    """

    _async_connection_builders: dict[str, Callable[..., Any]] = {}

    @staticmethod
    def register_async_connection(db_type: str, builder: Callable[..., Any]) -> None:
        """Registra constructor async para un motor.

        Args:
            db_type: Tipo de base de datos (case-insensitive)
            builder: Callable que retorna corrutina de conexión
        """
        key = db_type.lower().strip()
        ConnectionFactory._async_connection_builders[key] = builder
        logger.debug(f"Async connection builder registrado para: {db_type}")

    @staticmethod
    async def create_async_connection(
        db_type: str,
        conn_params: dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        """Crea una conexión async con lazy loading de builders.

        Args:
            db_type: Tipo de base de datos
            conn_params: Parámetros de conexión
            **kwargs: Argumentos adicionales

        Returns:
            Conexión async del driver específico

        Raises:
            NotImplementedError: Si async no está soportado
            ValueError: Si conexión async no proporciona builder
        """
        normalized_type = db_type.lower().strip()
        builder = ConnectionFactory._async_connection_builders.get(normalized_type)

        # Lazy load builders si no están registrados
        if builder is None:
            _register_lazy_async_builders(normalized_type)
            builder = ConnectionFactory._async_connection_builders.get(normalized_type)

        # Validar soporte async
        async_supported = is_async_supported(normalized_type)
        if builder is None and not async_supported:
            raise NotImplementedError(f"Conexión async no soportada para '{normalized_type}'.")

        if builder is None:
            raise ValueError(f"Builder async no disponible para '{db_type}'. Registre con register_async_connection().")

        # Ejecutar builder (puede ser corrutina)
        result = builder(conn_params, **kwargs)
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
        """Crea una conexión sincrónica nativa según tipo de BD.

        Args:
            db_type: Tipo de BD ('mariadb', 'oracle', 'postgresql',
                    'hsqldb', 'sqlserver', 'sqlite')
            conn_params: Parámetros de conexión filtrados
            db_validator: Validador de tipos de BD (opcional)
            sql_server_driver: Driver SQL Server a usar ('pymssql' o 'pyodbc')

        Returns:
            Conexión del driver específico

        Raises:
            CoreConnectionError: Si hay error en la creación

        Example:
            >>> conn = ConnectionFactory.create_connection(
            ...     "mariadb",
            ...     {"host": "localhost", "user": "root",
            ...      "password": "pass", "database": "test"}
            ... )
        """
        try:
            normalized_type = db_type.lower().strip()

            # Importar lazy para evitar dependencias circulares
            if normalized_type == "mariadb":
                from .mariadb.connection_mariadb import MariaDBConnection

                connection = MariaDBConnection.connect(conn_params)
                logger.info("🔗 MariaDB conexión creada (nativo)")
                return connection

            elif normalized_type == "oracle":
                from .oracle.connection_oracle import OracleConnection

                connection = OracleConnection.connect(conn_params, db_validator)
                logger.info("🔗 Oracle conexión creada (nativo)")
                return connection

            elif normalized_type == "postgresql":
                from .postgresql.connection_postgresql import PostgreSQLConnection

                connection = PostgreSQLConnection.connect(conn_params)
                logger.info("🔗 PostgreSQL conexión creada (psycopg3)")
                return connection

            elif normalized_type == "hsqldb":
                from .hsqldb.connection_hsqldb import HSQLDBConnection

                connection = HSQLDBConnection.connect(conn_params)
                logger.info("🔗 HSQLDB conexión creada (JayDeBeApi)")
                return connection

            elif normalized_type == "sqlserver":
                from .sqlserver.connection_sqlserver import SQLServerConnection

                connection = SQLServerConnection.connect(conn_params, driver=sql_server_driver)
                logger.info(f"🔗 SQL Server conexión creada ({sql_server_driver})")
                return connection

            elif normalized_type == "sqlite":
                from .sqlite.connection_sqlite import SQLiteConnection

                connection = SQLiteConnection.connect(conn_params)
                logger.info("🔗 SQLite conexión creada")
                return connection

            else:
                raise CoreConnectionError(
                    message=f"Tipo de base de datos no soportado: {db_type}",
                    operation="CREATE_CONNECTION",
                    db_type=db_type,
                )

        except Exception as e:
            logger.error(f"❌ Error al crear conexión para BD '{db_type}': {str(e)}")
            raise


def _register_lazy_async_builders(normalized_type: str) -> None:
    """Registra builders async de forma lazy (lazy loading).

    Evita importar todos los drivers al iniciar la aplicación.
    Se llama cuando se necesita un builder específico.

    Args:
        normalized_type: Tipo de BD normalizado (lowercase)
    """
    try:
        if normalized_type == "postgresql":
            from .postgresql.async_connection_postgresql import (
                AsyncPostgreSQLConnection,
            )

            ConnectionFactory.register_async_connection("postgresql", AsyncPostgreSQLConnection.connect)

        elif normalized_type == "sqlite":
            from .sqlite.async_connection_sqlite import AsyncSQLiteConnection

            ConnectionFactory.register_async_connection("sqlite", AsyncSQLiteConnection.connect)

        elif normalized_type == "mariadb":
            from .mariadb.async_connection_mariadb import AsyncMariaDBConnection

            ConnectionFactory.register_async_connection("mariadb", AsyncMariaDBConnection.connect)

        elif normalized_type == "oracle":
            from .oracle.async_connection_oracle import AsyncOracleConnection

            ConnectionFactory.register_async_connection("oracle", AsyncOracleConnection.connect)

        elif normalized_type == "sqlserver":
            from .sqlserver.async_connection_sqlserver import (
                AsyncSQLServerConnection,
            )

            ConnectionFactory.register_async_connection("sqlserver", AsyncSQLServerConnection.connect)

    except ImportError as e:
        logger.debug(f"No async builder available for {normalized_type}: {e}")
