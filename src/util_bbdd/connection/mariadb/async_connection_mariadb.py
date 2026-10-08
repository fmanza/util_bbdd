"""Conexión async para MariaDB basada en aiomysql."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ..params import ConnectionParamsManager


class AsyncMariaDBConnection:
    """Maneja la conexión async a MariaDB."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def _map_connect_kwargs(conn_params: dict[str, Any]) -> dict[str, Any]:
        """Mapea conn_params al contrato de aiomysql.connect.

        aiomysql llama ``db`` a la base de datos y no acepta ``read_timeout`` ni ``write_timeout`` (como en
        ``AsyncMariaDBPool._split_pool_kwargs``); pasarlos lanzaba ``TypeError`` en toda conexión directa.
        """
        allowed_keys: set[str] = {
            "host",
            "port",
            "user",
            "password",
            "db",
            "unix_socket",
            "autocommit",
            "connect_timeout",
            "charset",
        }
        normalized: dict[str, Any] = dict(conn_params)
        if "database" in normalized and "db" not in normalized:
            normalized["db"] = normalized.pop("database")
        return {k: v for k, v in normalized.items() if k in allowed_keys}

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
