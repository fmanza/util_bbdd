"""Pool async para MySQL basado en aiomysql.

Hereda de ``AsyncMariaDBPool`` la adquisición, devolución y cierre (mismo driver); solo la creación es propia:
valida con la configuración de MySQL, adapta los kwargs a ``aiomysql.connect`` y etiqueta errores como ``mysql``.
"""

from __future__ import annotations

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ..mariadb.async_pool_connection_mariadb import AsyncMariaDBPool
from ..params import ConnectionParamsManager
from .async_connection_mysql import build_aiomysql_connect_kwargs


class AsyncMySQLPool(AsyncMariaDBPool):
    """Pool de conexiones async para MySQL."""

    @classmethod
    async def create(cls, conn_params: dict[str, Any]) -> AsyncMySQLPool:
        """Crea un pool async de MySQL (``minsize = maxsize = pool_size``)."""
        try:
            import aiomysql

            pool_config = ConnectionParamsManager.get_pool_config("mysql", conn_params)
            conn_kwargs: dict[str, Any] = build_aiomysql_connect_kwargs(
                pool_config.connection.to_driver_kwargs(),
                aiomysql.connect,
            )
            close_timeout_seconds: float | None = pool_config.close_timeout

            cls.logger.debug(f"🔗 Creando pool MySQL async (min=max={pool_config.pool_size})")
            pool: Any = await aiomysql.create_pool(
                minsize=pool_config.pool_size,
                maxsize=pool_config.pool_size,
                pool_recycle=pool_config.pool_recycle,
                **conn_kwargs,
            )
            cls.logger.info("✅ Pool MySQL async creado")
            return cls(pool, close_timeout_seconds=close_timeout_seconds)
        except ImportError as err:
            cls.logger.error("❌ Error: módulo aiomysql no disponible")
            raise ConnectionError("Módulo aiomysql no disponible", db_type="mysql", details=str(err)) from err
        except Exception as err:
            cls.logger.error(f"❌ Error creando pool MySQL async: {err}")
            raise ConnectionError(
                f"Error creando pool MySQL async: {str(err)}",
                db_type="mysql",
                details=str(err),
            ) from err
