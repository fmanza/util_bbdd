"""Pool async para MariaDB basado en aiomysql."""

from __future__ import annotations

import inspect
import logging

from typing import Any

from util_bbdd.database_exceptions import DatabaseConnectionError

from ..connection_params_manager import ConnectionParamsManager


class AsyncMariaDBPool:
    """Pool de conexiones async para MariaDB."""

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, pool: Any):
        self._pool: Any = pool

    @staticmethod
    def _split_pool_kwargs(conn_params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Separa kwargs de conexión y de pool para aiomysql.create_pool."""
        pool_size: int = int(conn_params.get("pool_size", 5))

        conn_keys: set[str] = {
            "host",
            "port",
            "user",
            "password",
            "database",
            "unix_socket",
            "autocommit",
            "connect_timeout",
            "read_timeout",
            "write_timeout",
            "charset",
        }
        conn_kwargs: dict[str, Any] = {k: v for k, v in conn_params.items() if k in conn_keys}
        pool_kwargs: dict[str, Any] = {
            "minsize": pool_size,
            "maxsize": pool_size,
        }
        return conn_kwargs, pool_kwargs

    @classmethod
    async def create(cls, conn_params: dict[str, Any]) -> AsyncMariaDBPool:
        """Crea un pool async de MariaDB."""
        try:
            import aiomysql

            pool_config = ConnectionParamsManager.get_pool_config("mariadb", conn_params)
            sanitized_pool_params: dict[str, Any] = pool_config.to_driver_kwargs()
            conn_kwargs, pool_kwargs = cls._split_pool_kwargs(sanitized_pool_params)

            cls.logger.debug(
                f"🔗 Creando pool MariaDB async (min={pool_kwargs['minsize']}, max={pool_kwargs['maxsize']})"
            )
            pool: Any = await aiomysql.create_pool(**conn_kwargs, **pool_kwargs)
            cls.logger.info("✅ Pool MariaDB async creado")
            return cls(pool)
        except ImportError as err:
            cls.logger.error("❌ Error: módulo aiomysql no disponible")
            raise DatabaseConnectionError("Módulo aiomysql no disponible", "mariadb", str(err)) from err
        except Exception as err:
            cls.logger.error(f"❌ Error creando pool MariaDB async: {err}")
            raise DatabaseConnectionError(
                f"Error creando pool MariaDB async: {str(err)}",
                "mariadb",
                str(err),
            ) from err

    async def acquire(self) -> Any:
        """Obtiene conexión del pool."""
        return await self._pool.acquire()

    async def release(self, connection: Any) -> None:
        """Devuelve conexión al pool."""
        result = self._pool.release(connection)
        if inspect.isawaitable(result):
            await result

    async def aclose(self) -> None:
        """Cierra el pool."""
        self._pool.close()
        await self._pool.wait_closed()
