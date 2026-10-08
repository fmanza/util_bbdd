"""Conexión async para Oracle basada en python-oracledb."""

from __future__ import annotations

import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ..params import ConnectionParamsManager
from . import _thick_mode
from ._dsn import build_oracle_dsn


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

        dsn_value: str = build_oracle_dsn(oracledb_module, conn_params)

        connect_params["dsn"] = dsn_value
        return connect_params

    @staticmethod
    async def connect(conn_params: dict[str, Any]) -> Any:
        """Establece conexión async a Oracle.

        Nota: Las conexiones asincrónicas siempre usan el modo thin de oracledb, que solo conecta
        con Oracle 12.1+. Para Oracle 11g, use sincrónicas con oracle_thick_mode=True.
        """
        try:
            import oracledb

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "oracle",
                conn_params,
            )

            # Validar que no se intente usar thick mode con async
            if _thick_mode.ORACLE_THICK_MODE_INITIALIZED:
                raise ConnectionError(
                    "El modo asincrónico de Oracle no es compatible con thick mode en el mismo proceso. "
                    "Thick mode siempre usa thin, que no soporta Oracle 11g. "
                    "Use conexiones sincrónicas para Oracle 11g.",
                    db_type="oracle",
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
            raise ConnectionError("Módulo oracledb no disponible", db_type="oracle", details=str(err)) from err
        except Exception as err:
            AsyncOracleConnection.logger.error(f"❌ Error conectando a Oracle async: {err}")
            raise ConnectionError(
                f"Error conectando a Oracle async: {str(err)}",
                db_type="oracle",
                details=str(err),
            ) from err
