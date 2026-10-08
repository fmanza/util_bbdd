"""Pool async para Oracle basado en python-oracledb."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ...async_utils import maybe_await
from ..close import (
    FORCE_CLOSE_TIMEOUT_SECONDS,
    AsyncCloseMode,
    normalize_close_mode,
    parse_close_timeout,
    run_close_operation_async,
)
from ..params import ConnectionParamsManager
from ._dsn import build_oracle_dsn


class AsyncOraclePool:
    """Pool de conexiones async para Oracle."""

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, pool: Any, close_timeout_seconds: float | None):
        self._pool: Any = pool
        self._close_timeout_seconds: float | None = close_timeout_seconds
        self._closed: bool = False

    @staticmethod
    def _build_pool_params(oracledb_module: Any, conn_params: dict[str, Any]) -> dict[str, Any]:
        """Construye parámetros efectivos para create_pool_async."""
        pool_size: int = int(conn_params.get("pool_size", 5))
        max_lifetime: int = int(conn_params.get("max_lifetime", 3600))

        dsn_value: str = build_oracle_dsn(oracledb_module, conn_params)

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
            close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))

            create_pool_async = getattr(oracledb, "create_pool_async", None)
            if create_pool_async is None:
                raise RuntimeError(
                    "La versión instalada de oracledb no expone create_pool_async. "
                    "Actualice python-oracledb para usar modo async."
                )

            cls.logger.debug("🔗 Creando pool Oracle async")
            pool: Any = await create_pool_async(**create_params)
            cls.logger.info("✅ Pool Oracle async creado")
            return cls(pool, close_timeout_seconds=close_timeout_seconds)
        except ImportError as err:
            cls.logger.error("❌ Error: módulo oracledb no disponible")
            raise ConnectionError("Módulo oracledb no disponible", db_type="oracle", details=str(err)) from err
        except Exception as err:
            cls.logger.error(f"❌ Error creando pool Oracle async: {err}")
            raise ConnectionError(
                f"Error creando pool Oracle async: {str(err)}",
                db_type="oracle",
                details=str(err),
            ) from err

    async def acquire(self) -> Any:
        """Obtiene conexión del pool."""
        return await self._pool.acquire()

    async def release(self, connection: Any) -> None:
        """Devuelve conexión al pool."""
        await self._pool.release(connection)

    async def close(self, mode: AsyncCloseMode | str = "immediate") -> None:
        """Cierra pool async en modo inmediato o graceful."""
        if self._closed:
            return
        self._closed = True
        close_mode: AsyncCloseMode = normalize_close_mode(mode)

        async def _force_close() -> None:
            try:
                await maybe_await(self._pool.close(force=True))
            except TypeError:
                self.logger.warning("⚠️ Pool Oracle async no soporta force=True; reintentando close()")
                await maybe_await(self._pool.close())

        if close_mode == "immediate":
            await run_close_operation_async(
                _force_close(),
                FORCE_CLOSE_TIMEOUT_SECONDS,
                "cierre inmediato pool Oracle async",
                "oracle",
            )
            return

        closed: bool = await run_close_operation_async(
            maybe_await(self._pool.close()),
            self._close_timeout_seconds,
            "cierre pool Oracle async",
            "oracle",
        )
        if closed:
            return

        await run_close_operation_async(
            _force_close(),
            FORCE_CLOSE_TIMEOUT_SECONDS,
            "cierre forzado pool Oracle async",
            "oracle",
        )
