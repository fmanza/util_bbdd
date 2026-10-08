"""Pool async para MariaDB basado en aiomysql."""

from __future__ import annotations

import inspect
import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ...async_utils import maybe_await
from .._aiomysql import build_aiomysql_connect_kwargs
from ..close import (
    FORCE_CLOSE_TIMEOUT_SECONDS,
    AsyncCloseMode,
    normalize_close_mode,
    parse_close_timeout,
    run_close_operation_async,
)
from ..params import ConnectionParamsManager
from .async_connection_mariadb import MARIADB_AIOMYSQL_EXCLUDE


class AsyncMariaDBPool:
    """Pool de conexiones async para MariaDB."""

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, pool: Any, close_timeout_seconds: float | None):
        self._pool: Any = pool
        self._close_timeout_seconds: float | None = close_timeout_seconds
        self._closed: bool = False

    @classmethod
    async def create(cls, conn_params: dict[str, Any]) -> AsyncMariaDBPool:
        """Crea un pool async de MariaDB."""
        try:
            import aiomysql

            pool_config = ConnectionParamsManager.get_pool_config("mariadb", conn_params)
            conn_kwargs: dict[str, Any] = build_aiomysql_connect_kwargs(
                pool_config.connection.to_driver_kwargs(),
                aiomysql.connect,
                exclude=MARIADB_AIOMYSQL_EXCLUDE,
            )
            close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))

            cls.logger.debug(f"🔗 Creando pool MariaDB async (min=max={pool_config.pool_size})")
            # Sin pool_recycle, las conexiones ociosas más allá de wait_timeout se entregaban muertas.
            pool: Any = await aiomysql.create_pool(
                minsize=pool_config.pool_size,
                maxsize=pool_config.pool_size,
                pool_recycle=pool_config.pool_recycle,
                **conn_kwargs,
            )
            cls.logger.info("✅ Pool MariaDB async creado")
            return cls(pool, close_timeout_seconds=close_timeout_seconds)
        except ImportError as err:
            cls.logger.error("❌ Error: módulo aiomysql no disponible")
            raise ConnectionError("Módulo aiomysql no disponible", db_type="mariadb", details=str(err)) from err
        except Exception as err:
            cls.logger.error(f"❌ Error creando pool MariaDB async: {err}")
            raise ConnectionError(
                f"Error creando pool MariaDB async: {str(err)}",
                db_type="mariadb",
                details=str(err),
            ) from err

    async def acquire(self) -> Any:
        """Obtiene conexión del pool."""
        return await self._pool.acquire()

    async def release(self, connection: Any) -> None:
        """Devuelve conexión al pool."""
        result = self._pool.release(connection)
        if inspect.isawaitable(result):
            await result

    async def close(self, mode: AsyncCloseMode | str = "immediate") -> None:
        """Cierra el pool en modo inmediato o graceful."""
        if self._closed:
            return
        self._closed = True
        close_mode: AsyncCloseMode = normalize_close_mode(mode)

        async def _force_close() -> None:
            terminate = getattr(self._pool, "terminate", None)
            if callable(terminate):
                terminate()
            else:
                self.logger.warning("⚠️ Pool MariaDB async no expone terminate(); reintentando close()")
                self._pool.close()

            wait_closed = getattr(self._pool, "wait_closed", None)
            if callable(wait_closed):
                await run_close_operation_async(
                    maybe_await(wait_closed()),
                    FORCE_CLOSE_TIMEOUT_SECONDS,
                    "espera tras cierre inmediato pool MariaDB async",
                    "mariadb",
                )

        if close_mode == "immediate":
            await _force_close()
            return

        async def _graceful_close() -> None:
            self._pool.close()
            await maybe_await(self._pool.wait_closed())

        closed = await run_close_operation_async(
            _graceful_close(),
            self._close_timeout_seconds,
            "cierre pool MariaDB async",
            "mariadb",
        )
        if closed:
            return

        await _force_close()
