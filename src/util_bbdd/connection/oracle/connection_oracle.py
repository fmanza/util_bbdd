"""Conexión raw al driver Oracle."""

import logging

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ..params import ConnectionParamsManager
from ._dsn import build_oracle_dsn
from ._thick_mode import init_oracle_thick_mode


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
            ConnectionError: Si hay error en la conexión.
        """
        try:
            import oracledb

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "oracle",
                conn_params,
            )

            oracle_thick_mode: bool = sanitized_conn_params.get("oracle_thick_mode", False)
            oracle_client_path: str | None = sanitized_conn_params.get("oracle_client_path")

            if oracle_thick_mode:
                if not oracle_client_path:
                    raise ValueError(
                        "Para usar oracle_thick_mode=True es obligatorio especificar oracle_client_path "
                        "(ruta del Oracle Instant Client 19+, p.ej. C:\\oracle\\instantclient_19_32)"
                    )
                init_oracle_thick_mode(oracle_client_path)
            elif oracle_client_path and db_validator:
                # Modo legacy: solo inicializar si se pasa oracle_client_path sin oracle_thick_mode=True
                # (backwards compatibility)
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

            dsn_value: str = build_oracle_dsn(oracledb, sanitized_conn_params)

            connect_params["dsn"] = dsn_value

            OracleConnection.logger.debug("🔗 Conectando a Oracle con DSN resuelto")
            conn: Any = oracledb.connect(**connect_params)
            OracleConnection.logger.info("✅ Conexión Oracle establecida")
            return conn
        except ImportError as e:
            OracleConnection.logger.error("❌ Error: módulo oracledb no disponible")
            raise ConnectionError("Módulo oracledb no disponible", db_type="oracle", details=str(e)) from e
        except Exception as e:
            OracleConnection.logger.exception(f"❌ Error conectando a Oracle: {e}")
            raise ConnectionError(f"Error conectando a Oracle: {str(e)}", db_type="oracle", details=str(e)) from e
