"""Conexión async para PostgreSQL basada en asyncpg."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ..params import ConnectionParamsManager
from ._server_settings import build_server_settings


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
        # asyncpg llama ``timeout`` al connect_timeout de libpq
        if "timeout" not in mapped and conn_params.get("connect_timeout") is not None:
            mapped["timeout"] = conn_params["connect_timeout"]

        sslmode: Any = conn_params.get("sslmode")
        if "ssl" not in mapped and sslmode is not None:
            # asyncpg acepta el sslmode de libpq como cadena; un booleano perdía prefer/allow/verify-*
            mapped["ssl"] = str(sslmode).lower()

        server_settings: dict[str, str] = build_server_settings(conn_params)
        if server_settings:
            mapped["server_settings"] = server_settings

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
            raise ConnectionError("Módulo asyncpg no disponible", db_type="postgresql", details=str(err)) from err
        except Exception as err:
            AsyncPostgreSQLConnection.logger.exception(f"❌ Error conectando a PostgreSQL async: {err}")
            raise ConnectionError(
                f"Error conectando a PostgreSQL async: {str(err)}",
                db_type="postgresql",
                details=str(err),
            ) from err
