"""Pool async para PostgreSQL basado en asyncpg."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd.database_exceptions import DatabaseConnectionError

from ..connection_params_manager import ConnectionParamsManager


class AsyncPostgreSQLPool:
    """Pool de conexiones async para PostgreSQL."""

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, pool: Any):
        self._pool: Any = pool

    @staticmethod
    def _split_pool_kwargs(conn_params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Separa kwargs de conexión y kwargs de pool para asyncpg.create_pool."""
        pool_size: int = int(conn_params.get("pool_size", 5))
        pool_timeout: int = int(conn_params.get("pool_timeout", 30))
        max_idle: int = int(conn_params.get("max_idle", 300))

        conn_keys: set[str] = {
            "host",
            "port",
            "user",
            "password",
            "database",
            "timeout",
            "command_timeout",
            "ssl",
            "sslmode",
        }
        conn_kwargs: dict[str, Any] = {k: v for k, v in conn_params.items() if k in conn_keys}

        sslmode: Any = conn_kwargs.pop("sslmode", None)
        if "ssl" not in conn_kwargs and sslmode is not None:
            conn_kwargs["ssl"] = str(sslmode).lower() not in {"disable", "false", "0"}

        pool_kwargs: dict[str, Any] = {
            "min_size": pool_size,
            "max_size": pool_size,
            "timeout": pool_timeout,
            "max_inactive_connection_lifetime": max_idle,
        }
        return conn_kwargs, pool_kwargs

    @classmethod
    async def create(cls, conn_params: dict[str, Any]) -> AsyncPostgreSQLPool:
        """Crea un pool async de PostgreSQL."""
        try:
            import asyncpg

            pool_config = ConnectionParamsManager.get_pool_config("postgresql", conn_params)
            sanitized_pool_params: dict[str, Any] = pool_config.to_driver_kwargs()
            conn_kwargs, pool_kwargs = cls._split_pool_kwargs(sanitized_pool_params)

            cls.logger.debug(
                f"🔗 Creando pool PostgreSQL async (min={pool_kwargs['min_size']}, max={pool_kwargs['max_size']})"
            )
            pool: Any = await asyncpg.create_pool(**conn_kwargs, **pool_kwargs)
            cls.logger.info("✅ Pool PostgreSQL async creado")
            return cls(pool)
        except ImportError as err:
            cls.logger.error("❌ Error: módulo asyncpg no disponible")
            raise DatabaseConnectionError("Módulo asyncpg no disponible", "postgresql", str(err)) from err
        except Exception as err:
            cls.logger.error(f"❌ Error creando pool PostgreSQL async: {err}")
            raise DatabaseConnectionError(
                f"Error creando pool PostgreSQL async: {str(err)}",
                "postgresql",
                str(err),
            ) from err

    async def acquire(self) -> Any:
        """Obtiene conexión del pool."""
        return await self._pool.acquire()

    async def release(self, connection: Any) -> None:
        """Devuelve conexión al pool."""
        await self._pool.release(connection)

    async def aclose(self) -> None:
        """Cierra el pool."""
        await self._pool.close()
