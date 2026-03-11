"""Conexión raw al driver MariaDB."""

import logging

from typing import Any

from util_bbdd.database_exceptions import DatabaseConnectionError

from ..params import ConnectionParamsManager


class MariaDBConnection:
    """Maneja la conexión raw a MariaDB."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def connect(conn_params: dict[str, Any]) -> Any:
        """
        Establece conexión raw a MariaDB.

        Args:
            conn_params: Parámetros de conexión validados.

        Returns:
            Conexión a MariaDB.

        Raises:
            DatabaseConnectionError: Si hay error en la conexión.
        """
        try:
            import mariadb

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "mariadb",
                conn_params,
            )

            MariaDBConnection.logger.debug(
                f"🔗 Conectando a MariaDB con parámetros: {list(sanitized_conn_params.keys())}"
            )
            conn = mariadb.connect(**sanitized_conn_params)
            MariaDBConnection.logger.info("✅ Conexión MariaDB establecida")
            return conn
        except ImportError as e:
            MariaDBConnection.logger.error("❌ Error: módulo mariadb no disponible")
            raise DatabaseConnectionError("Módulo mariadb no disponible", "mariadb", str(e)) from e
        except Exception as e:
            MariaDBConnection.logger.error(f"❌ Error conectando a MariaDB: {e}")
            raise DatabaseConnectionError(f"Error conectando a MariaDB: {str(e)}", "mariadb", str(e)) from e
