"""Conexión async para PostgreSQL basada en asyncpg."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd.database_exceptions import DatabaseConnectionError

from ..connection_params_manager import ConnectionParamsManager


class AsyncPostgreSQLConnection:
    """Maneja la conexión async a PostgreSQL."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def _map_connect_kwargs(conn_params: dict[str, Any]) -> dict[str, Any]:
        """Mapea parámetros saneados al contrato de asyncpg.connect."""
        allowed_keys: set[str] = {
            "host",
            "port",
            "user",
            "password",
            "database",
            "timeout",
            "command_timeout",
            "ssl",
        }
        mapped: dict[str, Any] = {k: v for k, v in conn_params.items() if k in allowed_keys}

        sslmode: Any = conn_params.get("sslmode")
        if "ssl" not in mapped and sslmode is not None:
            mapped["ssl"] = str(sslmode).lower() not in {"disable", "false", "0"}

        return mapped

    @staticmethod
    async def connect(conn_params: dict[str, Any]) -> Any:
        """Establece una conexión async a PostgreSQL."""
        try:
            import asyncpg

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "postgresql",
                conn_params,
            )
            connect_kwargs: dict[str, Any] = AsyncPostgreSQLConnection._map_connect_kwargs(sanitized_conn_params)

            AsyncPostgreSQLConnection.logger.debug(
                f"🔗 Conectando a PostgreSQL async con parámetros: {list(connect_kwargs.keys())}"
            )
            conn: Any = await asyncpg.connect(**connect_kwargs)
            AsyncPostgreSQLConnection.logger.info("✅ Conexión PostgreSQL async establecida")
            return conn
        except ImportError as err:
            AsyncPostgreSQLConnection.logger.error("❌ Error: módulo asyncpg no disponible")
            raise DatabaseConnectionError("Módulo asyncpg no disponible", "postgresql", str(err)) from err
        except Exception as err:
            AsyncPostgreSQLConnection.logger.error(f"❌ Error conectando a PostgreSQL async: {err}")
            raise DatabaseConnectionError(
                f"Error conectando a PostgreSQL async: {str(err)}",
                "postgresql",
                str(err),
            ) from err
