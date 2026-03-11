"""Conexión async para MariaDB basada en aiomysql."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd.database_exceptions import DatabaseConnectionError

from ..params import ConnectionParamsManager


class AsyncMariaDBConnection:
    """Maneja la conexión async a MariaDB."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def _map_connect_kwargs(conn_params: dict[str, Any]) -> dict[str, Any]:
        """Mapea conn_params al contrato de aiomysql.connect."""
        allowed_keys: set[str] = {
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
        return {k: v for k, v in conn_params.items() if k in allowed_keys}

    @staticmethod
    async def connect(conn_params: dict[str, Any]) -> Any:
        """Establece conexión async a MariaDB."""
        try:
            import aiomysql

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "mariadb",
                conn_params,
            )
            connect_kwargs: dict[str, Any] = AsyncMariaDBConnection._map_connect_kwargs(sanitized_conn_params)

            AsyncMariaDBConnection.logger.debug(
                f"🔗 Conectando a MariaDB async con parámetros: {list(connect_kwargs.keys())}"
            )
            conn: Any = await aiomysql.connect(**connect_kwargs)
            AsyncMariaDBConnection.logger.info("✅ Conexión MariaDB async establecida")
            return conn
        except ImportError as err:
            AsyncMariaDBConnection.logger.error("❌ Error: módulo aiomysql no disponible")
            raise DatabaseConnectionError("Módulo aiomysql no disponible", "mariadb", str(err)) from err
        except Exception as err:
            AsyncMariaDBConnection.logger.error(f"❌ Error conectando a MariaDB async: {err}")
            raise DatabaseConnectionError(
                f"Error conectando a MariaDB async: {str(err)}",
                "mariadb",
                str(err),
            ) from err
