"""Conexión async para MySQL basada en aiomysql."""

from __future__ import annotations

import inspect
import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ..params import ConnectionParamsManager

logger: logging.Logger = logging.getLogger(__name__)


def build_aiomysql_connect_kwargs(driver_kwargs: dict[str, Any], connect: Any) -> dict[str, Any]:
    """Adapta los kwargs de ``MySQLConnectionConfig`` a la firma real de ``aiomysql.connect``.

    aiomysql llama ``db`` a la base de datos y no acepta ``read_timeout``/``write_timeout`` ni las claves TLS de
    PyMySQL: se descarta (con aviso) todo lo que su firma no admita. TLS en async requiere un ``ssl.SSLContext``,
    que esta capa no construye.

    Args:
        driver_kwargs: Salida de ``MySQLConnectionConfig.to_driver_kwargs()`` (o de la config de pool).
        connect: ``aiomysql.connect`` (se inspecciona su firma).
    """
    kwargs: dict[str, Any] = dict(driver_kwargs)
    if "database" in kwargs:
        kwargs["db"] = kwargs.pop("database")
    supported: set[str] = set(inspect.signature(connect).parameters)
    discarded: set[str] = set(kwargs) - supported
    if discarded:
        logger.debug(f"Parámetros no soportados por aiomysql.connect descartados: {sorted(discarded)}")
    return {key: value for key, value in kwargs.items() if key in supported and value is not None}


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
            AsyncMySQLConnection.logger.error(f"❌ Error conectando a MySQL async: {err}")
            raise ConnectionError(
                f"Error conectando a MySQL async: {str(err)}",
                db_type="mysql",
                details=str(err),
            ) from err
