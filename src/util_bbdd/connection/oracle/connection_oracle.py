"""Conexión raw al driver Oracle."""

import logging

from typing import Any

from oracledb.connection import Connection

from util_bbdd.database_exceptions import DatabaseConnectionError

from ..params import ConnectionParamsManager


class OracleConnection:
    """Maneja la conexión raw a Oracle."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def connect(
        conn_params: dict[str, Any],
        db_validator: Any = None,
    ) -> Any:
        """
        Establece conexión raw a Oracle.

        Args:
            conn_params: Parámetros de conexión validados.
            db_validator: Validador de tipos de BD.

        Returns:
            Conexión a Oracle.

        Raises:
            DatabaseConnectionError: Si hay error en la conexión.
        """
        try:
            import oracledb

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "oracle",
                conn_params,
            )

            oracle_client_path: str | None = sanitized_conn_params.get("oracle_client_path")
            if oracle_client_path and db_validator:
                driver_info = db_validator.get_db_type_driver_info("oracle")
                if driver_info.get("client_path_support"):
                    if hasattr(oracledb, "init_oracle_client"):
                        OracleConnection.logger.debug(f"🔧 Inicializando cliente Oracle desde {oracle_client_path}")
                        oracledb.init_oracle_client(oracle_client_path)

            # Construir parámetros efectivos para oracledb.connect
            connect_params: dict[str, Any] = {
                "user": sanitized_conn_params.get("user"),
                "password": sanitized_conn_params.get("password"),
            }

            dsn_value: str | None = sanitized_conn_params.get("dsn")
            if not dsn_value:
                host: str = sanitized_conn_params.get("host", "localhost")
                port: int = int(sanitized_conn_params.get("port", 1521))
                service_name: str | None = sanitized_conn_params.get("service_name")
                sid: str | None = sanitized_conn_params.get("sid")
                database: str | None = sanitized_conn_params.get("database")

                if service_name:
                    dsn_value = oracledb.makedsn(host=host, port=port, service_name=service_name)
                elif sid:
                    dsn_value = oracledb.makedsn(host=host, port=port, sid=sid)
                elif database:
                    dsn_value = oracledb.makedsn(host=host, port=port, service_name=database)
                else:
                    raise ValueError(
                        "Para Oracle debe proporcionar 'dsn' o bien 'service_name'/'sid' (también se acepta 'database' como alias de service_name)."
                    )

            connect_params["dsn"] = dsn_value

            OracleConnection.logger.debug("🔗 Conectando a Oracle con DSN resuelto")
            conn: Connection = oracledb.connect(**connect_params)
            OracleConnection.logger.info("✅ Conexión Oracle establecida")
            return conn
        except ImportError as e:
            OracleConnection.logger.error("❌ Error: módulo oracledb no disponible")
            raise DatabaseConnectionError("Módulo oracledb no disponible", "oracle", str(e)) from e
        except Exception as e:
            OracleConnection.logger.error(f"❌ Error conectando a Oracle: {e}")
            raise DatabaseConnectionError(f"Error conectando a Oracle: {str(e)}", "oracle", str(e)) from e
