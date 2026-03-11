"""Pool async para MariaDB basado en aiomysql."""

from __future__ import annotations

import inspect
import logging

from typing import Any

from util_bbdd.database_exceptions import DatabaseConnectionError

from ...async_utils import maybe_await
from ..close import (
    FORCE_CLOSE_TIMEOUT_SECONDS,
    AsyncCloseMode,
    normalize_close_mode,
    parse_close_timeout,
    run_close_operation_async,
)
from ..params import ConnectionParamsManager


class AsyncMariaDBPool:
    """Pool de conexiones async para MariaDB."""

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, pool: Any, close_timeout_seconds: float | None):
        self._pool: Any = pool
        self._close_timeout_seconds: float | None = close_timeout_seconds
        self._closed: bool = False

    @staticmethod
    def _split_pool_kwargs(conn_params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Separa kwargs de conexión y de pool para aiomysql.create_pool."""
        pool_size: int = int(conn_params.get("pool_size", 5))

        # aiomysql usa "db" (no "database")
        conn_keys: set[str] = {
            "host",
            "port",
            "user",
            "password",
            "db",
            "unix_socket",
            "autocommit",
            "connect_timeout",
            "read_timeout",
            "write_timeout",
            "charset",
        }

        normalized_params: dict[str, Any] = dict(conn_params)
        if "database" in normalized_params and "db" not in normalized_params:
            normalized_params["db"] = normalized_params["database"]

        conn_kwargs: dict[str, Any] = {k: v for k, v in normalized_params.items() if k in conn_keys and v is not None}

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
            close_timeout_seconds: float | None = parse_close_timeout(conn_params.get("close_timeout", 10))

            # Filtrar kwargs no soportados por la versión instalada de aiomysql.connect
            connect_signature = inspect.signature(aiomysql.connect)
            supported_connect_args = set(connect_signature.parameters.keys())
            discarded_args: set[str] = set(conn_kwargs.keys()) - supported_connect_args
            if discarded_args:
                cls.logger.warning(f"⚠️  Parámetros descartados no soportados por aiomysql: {discarded_args}")
            conn_kwargs = {k: v for k, v in conn_kwargs.items() if k in supported_connect_args}

            cls.logger.debug(
                f"🔗 Creando pool MariaDB async (min={pool_kwargs['minsize']}, max={pool_kwargs['maxsize']})"
            )
            pool: Any = await aiomysql.create_pool(**conn_kwargs, **pool_kwargs)
            cls.logger.info("✅ Pool MariaDB async creado")
            return cls(pool, close_timeout_seconds=close_timeout_seconds)
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
                await run_close_operation(
                    maybe_await(wait_closed()),
                    FORCE_CLOSE_TIMEOUT_SECONDS,
                    self.logger,
                    "espera tras cierre inmediato pool MariaDB async",
                )

        if close_mode == "immediate":
            await _force_close()
            return

        async def _graceful_close() -> None:
            self._pool.close()
            await maybe_await(self._pool.wait_closed())

        closed = await run_close_operation(
            _graceful_close(),
            self._close_timeout_seconds,
            self.logger,
            "cierre pool MariaDB async",
        )
        if closed:
            return

        await _force_close()
