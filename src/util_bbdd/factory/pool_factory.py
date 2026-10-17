"""Factory para crear pool de conexiones según driver nativo.

Los parámetros del pool deben incluirse en conn_params:
- pool_size: Tamaño del pool (default: 5)
- max_overflow: Conexiones adicionales permitidas (default: 10)
- pool_timeout: Timeout de conexión en segundos (default: 30)
"""

import inspect
import logging

from collections.abc import Callable
from typing import Any, ClassVar

from ..connection.protocols import ConnectionPoolProtocol
from ..core.capabilities import is_async_supported


class PoolFactory:
    """Factory para crear pool de conexiones según driver nativo.

    Los parámetros del pool se obtienen desde conn_params:
    - pool_size (default: 5)
    - max_overflow (default: 10)
    - pool_timeout (default: 30)
    """

    logger: logging.Logger = logging.getLogger(__name__)

    #: Motores con pool nativo en :meth:`create_pool`; el resto (HSQLDB) usa conexión única en los managers.
    SUPPORTED_POOL_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"mariadb", "mysql", "oracle", "postgresql", "sqlserver", "sqlite"}
    )
    _async_pool_builders: dict[str, Callable[..., Any]] = {}

    @staticmethod
    def register_async_pool(db_type: str, builder: Callable[..., Any]) -> None:
        """Registra constructor async de pool para un motor (sustituye al que hubiera; efecto global en el proceso).

        Args:
            db_type: Tipo de motor; se normaliza a minúsculas.
            builder: Callable que recibe ``conn_params`` y ``**kwargs`` y devuelve el pool o una corrutina.
        """
        PoolFactory._async_pool_builders[db_type.lower().strip()] = builder

    @staticmethod
    def _builtin_async_builder(normalized_type: str) -> Callable[..., Any] | None:
        """Importa y registra el pool async integrado de ``normalized_type``; ``None`` si no hay ninguno.

        Imports diferidos (cada pool arrastra su driver) pero estáticos: los mide ``scripts/gen_arquitectura_capas.py``.
        """
        pool_class: Any
        if normalized_type == "postgresql":
            from ..connection.postgresql.async_pool_connection_postgresql import AsyncPostgreSQLPool as pool_class
        elif normalized_type == "sqlite":
            from ..connection.sqlite.async_pool_connection_sqlite import AsyncSQLitePool as pool_class
        elif normalized_type == "mariadb":
            from ..connection.mariadb.async_pool_connection_mariadb import AsyncMariaDBPool as pool_class
        elif normalized_type == "mysql":
            from ..connection.mysql.async_pool_connection_mysql import AsyncMySQLPool as pool_class
        elif normalized_type == "oracle":
            from ..connection.oracle.async_pool_connection_oracle import AsyncOraclePool as pool_class
        elif normalized_type == "sqlserver":
            from ..connection.sqlserver.async_pool_connection_sqlserver import AsyncSQLServerPool as pool_class
        else:
            return None
        builder: Callable[..., Any] = pool_class.create
        PoolFactory.register_async_pool(normalized_type, builder)
        return builder

    @staticmethod
    async def create_async_pool(
        db_type: str,
        conn_params: dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        """Crea pool async con constructor registrado por motor (o el integrado de la librería).

        Args:
            db_type: Tipo de motor; se normaliza a minúsculas.
            conn_params: Parámetros de conexión y de pool.
            **kwargs: Argumentos adicionales para el constructor.

        Returns:
            El pool async del driver.

        Raises:
            NotImplementedError: Si el motor no tiene pool async (HSQLDB) ni constructor registrado.
        """
        normalized_type: str = db_type.lower().strip()
        builder: Callable[..., Any] | None = PoolFactory._async_pool_builders.get(normalized_type)
        if builder is None:
            builder = PoolFactory._builtin_async_builder(normalized_type)

        async_supported = is_async_supported(normalized_type)
        if builder is None and async_supported is False:
            raise NotImplementedError(f"Pool async no soportado para '{normalized_type}'.")

        if builder is None:
            raise NotImplementedError(
                f"Pool async no soportado para '{db_type}'. Registre builder con register_async_pool()."
            )

        result: Any = builder(conn_params, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    @staticmethod
    def create_pool(
        db_type: str,
        conn_params: dict[str, Any],
    ) -> ConnectionPoolProtocol:
        """Crea pool nativo según tipo de BD.

        Args:
            db_type: Tipo de BD ('mariadb', 'mysql', 'sqlserver', 'oracle', 'postgresql', 'sqlite').
            conn_params: Parámetros de conexión incluyendo config del pool:
                - Parámetros de conexión específicos del driver
                - pool_size (int, default: 5): Tamaño del pool
                - max_overflow (int, default: 10): Conexiones adicionales permitidas
                - pool_timeout (int, default: 30): Timeout en segundos

        Returns:
            Pool object del driver específico.

        Raises:
            ValueError: Si db_type no soporta pool nativo.
            Exception: Si la creación del pool falla.

        Example:
            ```python
            conn_params = {
                "host": "localhost",
                "user": "user",
                "password": "pass",
                "database": "mydb",
                "port": 5432,
                "pool_size": 20,
                "max_overflow": 10,
                "pool_timeout": 30
            }
            pool = PoolFactory.create_pool("postgresql", conn_params)
            ```
        """
        try:
            if db_type == "mariadb":
                from ..connection.mariadb.pool_connection_mariadb import (
                    PoolConnection as MariaDBPool,
                )

                pool: ConnectionPoolProtocol = MariaDBPool(conn_params)
                PoolFactory.logger.info("🔗 MariaDB pool creado (nativo)")
                return pool

            elif db_type == "mysql":
                from ..connection.mysql.pool_connection_mysql import (
                    PoolConnection as MySQLPool,
                )

                pool = MySQLPool(conn_params)
                PoolFactory.logger.info("🔗 MySQL pool creado (QueuePool de SQLAlchemy sobre PyMySQL)")
                return pool

            elif db_type == "sqlserver":
                from ..connection.sqlserver.pool_connection_sqlserver import (
                    PoolConnection as SQLServerPool,
                )

                pool = SQLServerPool(conn_params)
                PoolFactory.logger.info("🔗 SQL Server pool creado")
                return pool

            elif db_type == "oracle":
                from ..connection.oracle.pool_connection_oracle import (
                    PoolConnection as OraclePool,
                )

                pool = OraclePool(conn_params)
                PoolFactory.logger.info("🔗 Oracle pool creado (nativo)")
                return pool

            elif db_type == "postgresql":
                from ..connection.postgresql.pool_connection_postgresql import (
                    PoolConnection as PostgreSQLPool,
                )

                pool = PostgreSQLPool(conn_params)
                PoolFactory.logger.info("🔗 PostgreSQL pool creado (psycopg3)")
                return pool

            elif db_type == "sqlite":
                from ..connection.sqlite.pool_connection_sqlite import (
                    PoolConnection as SQLitePool,
                )

                pool = SQLitePool(conn_params)
                PoolFactory.logger.info("🔗 SQLite pool creado (simple wrapper)")
                return pool

            else:
                raise ValueError(
                    f"Pool no soportado para {db_type}. Use: mariadb, mysql, sqlserver, oracle, postgresql, sqlite"
                )

        except Exception as e:
            PoolFactory.logger.error(f"❌ Error creando pool para {db_type}: {e}")
            raise
