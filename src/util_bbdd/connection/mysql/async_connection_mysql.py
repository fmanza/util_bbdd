"""Conexión async para MySQL basada en aiomysql."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from .._aiomysql import build_aiomysql_connect_kwargs
from ..params import ConnectionParamsManager

logger: logging.Logger = logging.getLogger(__name__)

__all__ = ["AsyncMySQLConnection", "build_aiomysql_connect_kwargs"]


class AsyncMySQLConnection:
    """Maneja la conexión async a MySQL."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    async def connect(conn_params: dict[str, Any], found_rows: bool = False) -> Any:
        """Establece conexión async a MySQL.

        ``found_rows`` activa ``CLIENT.FOUND_ROWS`` como hace SQLAlchemy (``async_creator`` de los AsyncEngine).
        """
        try:
            import aiomysql

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "mysql",
                conn_params,
            )
            connect_kwargs: dict[str, Any] = build_aiomysql_connect_kwargs(sanitized_conn_params, aiomysql.connect)
            if found_rows:
                from pymysql.constants import CLIENT

                connect_kwargs["client_flag"] = CLIENT.FOUND_ROWS

            AsyncMySQLConnection.logger.debug(
                f"🔗 Conectando a MySQL async con parámetros: {list(connect_kwargs.keys())}"
            )
            conn: Any = await aiomysql.connect(**connect_kwargs)
            AsyncMySQLConnection.logger.info("✅ Conexión MySQL async establecida")
            return conn
        except ImportError as err:
            AsyncMySQLConnection.logger.error("❌ Error: módulo aiomysql no disponible")
            raise ConnectionError("Módulo aiomysql no disponible", db_type="mysql", details=str(err)) from err
        except Exception as err:
            AsyncMySQLConnection.logger.exception(f"❌ Error conectando a MySQL async: {err}")
            raise ConnectionError(
                f"Error conectando a MySQL async: {str(err)}",
                db_type="mysql",
                details=str(err),
            ) from err
