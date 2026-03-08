"""Pool async para Oracle basado en python-oracledb."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd.database_exceptions import DatabaseConnectionError

from ..connection_params_manager import ConnectionParamsManager


class AsyncOraclePool:
    """Pool de conexiones async para Oracle."""

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, pool: Any):
        self._pool: Any = pool

    @staticmethod
    def _build_pool_params(oracledb_module: Any, conn_params: dict[str, Any]) -> dict[str, Any]:
        """Construye parámetros efectivos para create_pool_async."""
        pool_size: int = int(conn_params.get("pool_size", 5))
        max_lifetime: int = int(conn_params.get("max_lifetime", 3600))

        dsn_value: str | None = conn_params.get("dsn")
        if not dsn_value:
            host: str = str(conn_params.get("host", "localhost"))
            port: int = int(conn_params.get("port", 1521))
            service_name: str | None = conn_params.get("service_name")
            sid: str | None = conn_params.get("sid")
            database: str | None = conn_params.get("database")

            if service_name:
                dsn_value = oracledb_module.makedsn(host=host, port=port, service_name=service_name)
            elif sid:
                dsn_value = oracledb_module.makedsn(host=host, port=port, sid=sid)
            elif database:
                dsn_value = oracledb_module.makedsn(host=host, port=port, service_name=database)
            else:
                raise ValueError(
                    "Para Oracle debe proporcionar 'dsn' o bien 'service_name'/'sid' (también se acepta 'database' como alias de service_name)."
                )

        return {
            "user": conn_params.get("user"),
            "password": conn_params.get("password"),
            "dsn": dsn_value,
            "min": 1,
            "max": pool_size,
            "increment": 1,
            "getmode": getattr(oracledb_module, "POOL_GETMODE_WAIT", None),
            "max_lifetime_session": max_lifetime,
        }

    @classmethod
    async def create(cls, conn_params: dict[str, Any]) -> AsyncOraclePool:
        """Crea un pool async de Oracle."""
        try:
            import oracledb

            pool_config = ConnectionParamsManager.get_pool_config("oracle", conn_params)
            sanitized_pool_params: dict[str, Any] = pool_config.to_driver_kwargs()
            create_params: dict[str, Any] = cls._build_pool_params(oracledb, sanitized_pool_params)

            create_pool_async = getattr(oracledb, "create_pool_async", None)
            if create_pool_async is None:
                raise RuntimeError(
                    "La versión instalada de oracledb no expone create_pool_async. "
                    "Actualice python-oracledb para usar modo async."
                )

            cls.logger.debug("🔗 Creando pool Oracle async")
            pool: Any = await create_pool_async(**create_params)
            cls.logger.info("✅ Pool Oracle async creado")
            return cls(pool)
        except ImportError as err:
            cls.logger.error("❌ Error: módulo oracledb no disponible")
            raise DatabaseConnectionError("Módulo oracledb no disponible", "oracle", str(err)) from err
        except Exception as err:
            cls.logger.error(f"❌ Error creando pool Oracle async: {err}")
            raise DatabaseConnectionError(
                f"Error creando pool Oracle async: {str(err)}",
                "oracle",
                str(err),
            ) from err

    async def acquire(self) -> Any:
        """Obtiene conexión del pool."""
        return await self._pool.acquire()

    async def release(self, connection: Any) -> None:
        """Devuelve conexión al pool."""
        await self._pool.release(connection)

    async def aclose(self) -> None:
        """Cierra pool async."""
        await self._pool.close()
