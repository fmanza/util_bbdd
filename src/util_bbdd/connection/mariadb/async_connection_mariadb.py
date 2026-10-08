"""Conexión async para MariaDB basada en aiomysql."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from .._aiomysql import build_aiomysql_connect_kwargs
from ..params import ConnectionParamsManager

#: MariaDB async no envía ``init_command``: el ``SET NAMES utf8mb4`` por defecto es del conector sync y pisaría ``charset``.
MARIADB_AIOMYSQL_EXCLUDE: frozenset[str] = frozenset({"init_command"})


class AsyncMariaDBConnection:
    """Maneja la conexión async a MariaDB."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def _map_connect_kwargs(conn_params: dict[str, Any]) -> dict[str, Any]:
        """kwargs de ``aiomysql.connect`` para MariaDB (sin ``init_command``: ver ``build_aiomysql_connect_kwargs``)."""
        import aiomysql

        return build_aiomysql_connect_kwargs(conn_params, aiomysql.connect, exclude=MARIADB_AIOMYSQL_EXCLUDE)

    @staticmethod
    async def connect(conn_params: dict[str, Any], found_rows: bool = False) -> Any:
        """Establece conexión async a MariaDB.

        ``found_rows`` activa ``CLIENT.FOUND_ROWS`` como hace SQLAlchemy (``async_creator`` de los AsyncEngine).
        """
        try:
            import aiomysql

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "mariadb",
                conn_params,
            )
            connect_kwargs: dict[str, Any] = AsyncMariaDBConnection._map_connect_kwargs(sanitized_conn_params)
            if found_rows:
                from pymysql.constants import CLIENT

                connect_kwargs["client_flag"] = CLIENT.FOUND_ROWS

            AsyncMariaDBConnection.logger.debug(
                f"🔗 Conectando a MariaDB async con parámetros: {list(connect_kwargs.keys())}"
            )
            conn: Any = await aiomysql.connect(**connect_kwargs)
            AsyncMariaDBConnection.logger.info("✅ Conexión MariaDB async establecida")
            return conn
        except ImportError as err:
            AsyncMariaDBConnection.logger.error("❌ Error: módulo aiomysql no disponible")
            raise ConnectionError("Módulo aiomysql no disponible", db_type="mariadb", details=str(err)) from err
        except Exception as err:
            AsyncMariaDBConnection.logger.error(f"❌ Error conectando a MariaDB async: {err}")
            raise ConnectionError(
                f"Error conectando a MariaDB async: {str(err)}",
                db_type="mariadb",
                details=str(err),
            ) from err
