"""Conexión raw a MySQL con PyMySQL."""

import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ..params import ConnectionParamsManager


def build_pymysql_connect_kwargs(driver_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Traduce los kwargs de ``MySQLConnectionConfig`` al contrato de ``pymysql.connect``.

    PyMySQL agrupa los parámetros TLS en ``ssl`` (``ca``, ``cert``, ``key``) y recibe la verificación aparte
    (``ssl_verify_cert``, ``ssl_verify_identity``); el resto de claves coincide con su firma.
    """
    kwargs: dict[str, Any] = dict(driver_kwargs)
    ssl: dict[str, str] = {}
    for key, ssl_key in (("ssl_ca", "ca"), ("ssl_cert", "cert"), ("ssl_key", "key")):
        value: Any = kwargs.pop(key, None)
        if value:
            ssl[ssl_key] = str(value)
    if ssl:
        kwargs["ssl"] = ssl
    return kwargs


class MySQLConnection:
    """Maneja la conexión raw a MySQL (PyMySQL)."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def connect(conn_params: dict[str, Any], found_rows: bool = False) -> Any:
        """
        Establece conexión raw a MySQL.

        Args:
            conn_params: Parámetros de conexión validados.
            found_rows: Activa ``CLIENT.FOUND_ROWS`` (``rowcount`` = filas encontradas, no cambiadas), como hace
                SQLAlchemy al conectar; lo usa el ``creator`` de ``SQLAlchemyEngineFactory``. No se lee de
                ``conn_params``: ``client_flag`` sigue fuera de la lista blanca.

        Returns:
            Conexión PyMySQL.

        Raises:
            ConnectionError: Si hay error en la conexión.
        """
        try:
            import pymysql

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "mysql",
                conn_params,
            )
            connect_kwargs: dict[str, Any] = build_pymysql_connect_kwargs(sanitized_conn_params)
            if found_rows:
                from pymysql.constants import CLIENT

                connect_kwargs["client_flag"] = CLIENT.FOUND_ROWS

            MySQLConnection.logger.debug(f"🔗 Conectando a MySQL con parámetros: {list(connect_kwargs.keys())}")
            conn = pymysql.connect(**connect_kwargs)
            MySQLConnection.logger.info("✅ Conexión MySQL establecida")
            return conn
        except ImportError as e:
            MySQLConnection.logger.error("❌ Error: módulo pymysql no disponible")
            raise ConnectionError("Módulo pymysql no disponible", db_type="mysql", details=str(e)) from e
        except Exception as e:
            MySQLConnection.logger.error(f"❌ Error conectando a MySQL: {e}")
            raise ConnectionError(f"Error conectando a MySQL: {str(e)}", db_type="mysql", details=str(e)) from e
