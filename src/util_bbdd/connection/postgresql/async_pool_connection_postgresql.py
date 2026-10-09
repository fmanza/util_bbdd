"""Pool async para PostgreSQL basado en asyncpg."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ...async_utils import maybe_await
from ..close import (
    FORCE_CLOSE_TIMEOUT_SECONDS,
    AsyncCloseMode,
    normalize_close_mode,
    run_close_operation_async,
)
from ..params import ConnectionParamsManager
from ._server_settings import build_server_settings


class AsyncPostgreSQLPool:
    """Pool de conexiones async para PostgreSQL."""

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, pool: Any, close_timeout_seconds: float | None):
        self._pool: Any = pool
        self._close_timeout_seconds: float | None = close_timeout_seconds
        self._closed: bool = False

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
            # asyncpg acepta el sslmode de libpq como cadena; un booleano perdía prefer/allow/verify-*
            conn_kwargs["ssl"] = str(sslmode).lower()

        server_settings: dict[str, str] = build_server_settings(conn_params)
        if server_settings:
            conn_kwargs["server_settings"] = server_settings

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
            close_timeout_seconds: float | None = pool_config.close_timeout

            cls.logger.debug(
                f"🔗 Creando pool PostgreSQL async (min={pool_kwargs['min_size']}, max={pool_kwargs['max_size']})"
            )
            pool: Any = await asyncpg.create_pool(**conn_kwargs, **pool_kwargs)
            cls.logger.info("✅ Pool PostgreSQL async creado")
            return cls(pool, close_timeout_seconds=close_timeout_seconds)
        except ImportError as err:
            cls.logger.error("❌ Error: módulo asyncpg no disponible")
            raise ConnectionError("Módulo asyncpg no disponible", db_type="postgresql", details=str(err)) from err
        except Exception as err:
            cls.logger.error(f"❌ Error creando pool PostgreSQL async: {err}")
            raise ConnectionError(
                f"Error creando pool PostgreSQL async: {str(err)}",
                db_type="postgresql",
                details=str(err),
            ) from err

    async def acquire(self) -> Any:
        """Obtiene conexión del pool."""
        return await self._pool.acquire()

    async def release(self, connection: Any) -> None:
        """Devuelve conexión al pool."""
        await self._pool.release(connection)

    async def close(self, mode: AsyncCloseMode | str = "immediate") -> None:
        """Cierra el pool en modo inmediato o graceful."""
        if self._closed:
            return
        self._closed = True
        close_mode: AsyncCloseMode = normalize_close_mode(mode)

        async def _force_close() -> None:
            terminate = getattr(self._pool, "terminate", None)
            if callable(terminate):
                await run_close_operation_async(
                    maybe_await(terminate()),
                    FORCE_CLOSE_TIMEOUT_SECONDS,
                    "terminación inmediata pool PostgreSQL async",
                    "postgresql",
                )
                return

            await run_close_operation_async(
                maybe_await(self._pool.close()),
                FORCE_CLOSE_TIMEOUT_SECONDS,
                "cierre inmediato pool PostgreSQL async sin terminate()",
                "postgresql",
            )

        if close_mode == "immediate":
            await _force_close()
            return

        closed: bool = await run_close_operation_async(
            maybe_await(self._pool.close()),
            self._close_timeout_seconds,
            "cierre pool PostgreSQL async",
            "postgresql",
        )
        if closed:
            return

        await _force_close()
