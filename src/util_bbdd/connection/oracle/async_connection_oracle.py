"""Conexión async para Oracle basada en python-oracledb."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd.database_exceptions import DatabaseConnectionError

from ..params import ConnectionParamsManager


class AsyncOracleConnection:
    """Maneja la conexión async a Oracle."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def _build_connect_params(oracledb_module: Any, conn_params: dict[str, Any]) -> dict[str, Any]:
        """Construye parámetros efectivos de conexión para Oracle async."""
        connect_params: dict[str, Any] = {
            "user": conn_params.get("user"),
            "password": conn_params.get("password"),
        }

        dsn_value: str | None = conn_params.get("dsn")
        if not dsn_value:
            host: str = str(conn_params.get("host", "localhost"))
            port: int = int(conn_params.get("port", 1521))
            service_name: str | None = conn_params.get("service_name")
            sid: str | None = conn_params.get("sid")
            database: str | None = conn_params.get("database")

            if service_name:
                dsn_value = oracledb_module.makedsn(host=host, port=port, service_name=service_name)
            elif sid:
                dsn_value = oracledb_module.makedsn(host=host, port=port, sid=sid)
            elif database:
                dsn_value = oracledb_module.makedsn(host=host, port=port, service_name=database)
            else:
                raise ValueError(
                    "Para Oracle debe proporcionar 'dsn' o bien 'service_name'/'sid' (también se acepta 'database' como alias de service_name)."
                )

        connect_params["dsn"] = dsn_value
        return connect_params

    @staticmethod
    async def connect(conn_params: dict[str, Any]) -> Any:
        """Establece conexión async a Oracle."""
        try:
            import oracledb

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "oracle",
                conn_params,
            )

            connect_params: dict[str, Any] = AsyncOracleConnection._build_connect_params(
                oracledb,
                sanitized_conn_params,
            )

            connect_async = getattr(oracledb, "connect_async", None)
            if connect_async is None:
                raise RuntimeError(
                    "La versión instalada de oracledb no expone connect_async. "
                    "Actualice python-oracledb para usar modo async."
                )

            AsyncOracleConnection.logger.debug("🔗 Conectando a Oracle async con DSN resuelto")
            conn: Any = await connect_async(**connect_params)
            AsyncOracleConnection.logger.info("✅ Conexión Oracle async establecida")
            return conn
        except ImportError as err:
            AsyncOracleConnection.logger.error("❌ Error: módulo oracledb no disponible")
            raise DatabaseConnectionError("Módulo oracledb no disponible", "oracle", str(err)) from err
        except Exception as err:
            AsyncOracleConnection.logger.error(f"❌ Error conectando a Oracle async: {err}")
            raise DatabaseConnectionError(
                f"Error conectando a Oracle async: {str(err)}",
                "oracle",
                str(err),
            ) from err
