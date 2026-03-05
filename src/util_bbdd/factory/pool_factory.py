"""Factory para crear pool de conexiones según driver nativo.

Los parámetros del pool deben incluirse en conn_params:
- pool_size: Tamaño del pool (default: 5)
- max_overflow: Conexiones adicionales permitidas (default: 10)
- pool_timeout: Timeout de conexión en segundos (default: 30)
"""

import logging
from typing import Any

from ..connection.mariadb.pool_connection_mariadb import (
    PoolConnection as MariaDBPool,
)
from ..connection.oracle.pool_connection_oracle import (
    PoolConnection as OraclePool,
)
from ..connection.pool_protocol import ConnectionPoolProtocol
from ..connection.postgresql.pool_connection_postgresql import (
    PoolConnection as PostgreSQLPool,
)
from ..connection.sqlite.pool_connection_sqlite import (
    PoolConnection as SQLitePool,
)
from ..connection.sqlserver.pool_connection_sqlserver import (
    PoolConnection as SQLServerPool,
)


class PoolFactory:
    """Factory para crear pool de conexiones según driver nativo.

    Los parámetros del pool se obtienen desde conn_params:
    - pool_size (default: 5)
    - max_overflow (default: 10)
    - pool_timeout (default: 30)
    """

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def create_pool(
        db_type: str,
        conn_params: dict[str, Any],
    ) -> ConnectionPoolProtocol:
        """Crea pool nativo según tipo de BD.

        Args:
            db_type: Tipo de BD ('mariadb', 'sqlserver', 'oracle', 'postgresql', 'sqlite').
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
                pool = MariaDBPool(conn_params)
                PoolFactory.logger.info("🔗 MariaDB pool creado (nativo)")
                return pool

            elif db_type == "sqlserver":
                pool = SQLServerPool(conn_params)
                PoolFactory.logger.info("🔗 SQL Server pool creado")
                return pool

            elif db_type == "oracle":
                pool = OraclePool(conn_params)
                PoolFactory.logger.info("🔗 Oracle pool creado (nativo)")
                return pool

            elif db_type == "postgresql":
                pool = PostgreSQLPool(conn_params)
                PoolFactory.logger.info("🔗 PostgreSQL pool creado (psycopg3)")
                return pool

            elif db_type == "sqlite":
                pool = SQLitePool(conn_params)
                PoolFactory.logger.info("🔗 SQLite pool creado (simple wrapper)")
                return pool

            else:
                raise ValueError(f"Pool no soportado para {db_type}. Use: mariadb, sqlserver, oracle, postgresql, sqlite")

        except Exception as e:
            PoolFactory.logger.error(f"❌ Error creando pool para {db_type}: {e}")
            raise
